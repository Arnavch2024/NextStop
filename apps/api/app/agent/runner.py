import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from google import genai
from google.genai import types
from supabase import Client

from app.agent.prompts import get_system_prompt_for_role
from app.agent.tools import (
    DRAFT_OUTREACH_TOOL_NAME,
    PROPOSE_REFERENCE_CHECK_TOOL_NAME,
    PROPOSE_REVOKE_REFERENCE_CHECK_TOOL_NAME,
    PROPOSE_VERIFY_TOOL_NAME,
    SEARCH_DATA_LAKE_TOOL_NAME,
    UPSERT_CONTACT_TOOL_NAME,
    UPSERT_RECORD_TOOL_NAME,
    WEB_SEARCH_ENRICH_TOOL_NAME,
    get_tools_for_role,
    handle_propose_reference_check,
    handle_propose_revoke_reference_check,
    handle_propose_verify,
    handle_upsert,
)
from app.config import settings
from app.db.supabase import (
    close_agent_run,
    create_agent_run,
    get_supabase_client,
    load_recent_events,
    write_raw_event,
)
from app.llm import GeminiLLMProvider, LLMProvider, get_llm_provider
from app.logger import logger
from app.models.api import (
    AgentStep,
    AgentStepType,
    ChatResponse,
    ContactCard,
    ContactSourceModel,
    RecordRef,
)
from app.models.db import ProfileRole, UserProfile
from app.search.data_lake import search_data_lake
from app.search.dedupe import classify_recruiter_role, upsert_contact
from app.search.extract_contacts import (
    CandidateContact,
    validate_full_name,
    validate_recruiter_candidate,
)
from app.search.outreach import create_outreach_draft
from app.search.providers.extract import is_data_broker
from app.search.web import web_search_enrich

MAX_AGENT_ITERATIONS = 5

_gemini_client: Optional[genai.Client] = None


def get_gemini_client() -> Optional[genai.Client]:
    """Returns the Gemini SDK client."""
    global _gemini_client
    if _gemini_client is None:
        if settings.raw_gemini_api_key:
            _gemini_client = genai.Client(api_key=settings.raw_gemini_api_key)
    return _gemini_client


def build_gemini_contents_from_history(
    history_events: List[Dict[str, Any]],
    current_message: str,
) -> List[types.Content]:
    """Converts chronological raw_events into Gemini types.Content objects."""
    contents: List[types.Content] = []

    for event in history_events:
        source = event.get("source")
        payload = event.get("payload") or {}

        if source == "user_message":
            msg_text = payload.get("message", "")
            if msg_text:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg_text)],
                    )
                )
        elif source == "agent_message":
            msg_text = payload.get("message", "")
            if msg_text:
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=msg_text)],
                    )
                )
        elif source == "tool_call":
            name = payload.get("name") or payload.get("tool") or UPSERT_RECORD_TOOL_NAME
            args = payload.get("args") or payload.get("input") or {}
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))],
                )
            )
        elif source == "tool_result":
            name = payload.get("name") or payload.get("tool") or UPSERT_RECORD_TOOL_NAME
            result = payload.get("result") or payload.get("output") or {}
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(name=name, response=result))],
                )
            )

    # If the current message is not the last user turn, append it
    if (
        not contents
        or contents[-1].role != "user"
        or (contents[-1].parts and getattr(contents[-1].parts[0], "text", None) != current_message)
    ):
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=current_message)],
            )
        )

    return contents


def run_agent_loop(
    user: UserProfile,
    message: str,
    supabase_client: Optional[Client] = None,
    gemini_client: Optional[genai.Client] = None,
    model_name: Optional[str] = None,
    llm_provider: Optional[LLMProvider] = None,
) -> ChatResponse:
    """
    Executes the conversational agent loop via LLMProvider:
    1. Records the incoming user message to raw_events.
    2. Initializes an agent_runs entry.
    3. Runs up to MAX_AGENT_ITERATIONS turns calling the LLM with tool use.
    4. Handles upsert_record invocations, writes events, and aggregates steps.
    5. Writes the final reply to raw_events and updates agent_runs to completed.
    """
    sb = supabase_client or get_supabase_client()
    gm = gemini_client or get_gemini_client()
    if llm_provider:
        provider = llm_provider
    elif gm is not None:
        provider = GeminiLLMProvider(client=gm)
    else:
        provider = get_llm_provider()

    model = model_name or settings.LLM_AGENT_MODEL

    # 1. Start agent run and record user message
    run_id = create_agent_run(user.id, sb)
    write_raw_event(user.id, source="user_message", payload={"message": message}, client=sb)

    steps: List[AgentStep] = []
    records_created: List[RecordRef] = []

    try:
        # 2. Build history and Gemini config
        student_data = None
        missing_fields = None

        if user.role == ProfileRole.STUDENT:
            try:
                stu_res = sb.table("students").select("*").eq("profile_id", user.id).execute()
                if stu_res.data and len(stu_res.data) > 0:
                    student_row = stu_res.data[0]
                    student_id = str(student_row["id"])
                    edu_rows = sb.table("education").select("*").eq("student_id", student_id).execute().data or []
                    intern_rows = sb.table("internships").select("*").eq("student_id", student_id).execute().data or []
                    job_rows = sb.table("jobs").select("*").eq("student_id", student_id).execute().data or []
                    skill_rows = sb.table("skills").select("*").eq("student_id", student_id).execute().data or []

                    student_data = {
                        "student": student_row,
                        "education": edu_rows,
                        "internships": intern_rows,
                        "jobs": job_rows,
                        "skills": skill_rows,
                    }
                    missing = []
                    if not student_row.get("college_id"):
                        missing.append("college")
                    if not student_row.get("degree"):
                        missing.append("degree")
                    if not student_row.get("batch_year"):
                        missing.append("batch_year")
                    if not any(e.get("level") in ("tenth", "twelfth") for e in edu_rows):
                        missing.append("high_school_score")
                    if not any(e.get("level") == "bachelors" for e in edu_rows):
                        missing.append("bachelors_score")
                    if not skill_rows:
                        missing.append("skills")
                    missing_fields = missing
            except Exception as e:
                logger.warning(f"Could not load student context for prompt: {e}")

        has_college = bool(user.college_id)
        system_prompt = get_system_prompt_for_role(
            user.role,
            student_data=student_data,
            missing_fields=missing_fields,
            has_college=has_college,
        )
        history = load_recent_events(user.id, limit=50, client=sb)
        contents = build_gemini_contents_from_history(history, message)

        tools = get_tools_for_role(user.role, is_demo=getattr(user, "is_demo", False))

        cards: List[Dict[str, Any]] = []
        reply_text = ""
        iteration = 0
        lake_found = 0
        web_found = 0
        added_new = 0
        merged = 0
        used_search = False
        lake_contacts_found: List[Dict[str, Any]] = []

        # 3. Multi-turn loop (max 5 iterations)
        while iteration < MAX_AGENT_ITERATIONS:
            iteration += 1
            logger.info(f"Agent turn iteration {iteration}/{MAX_AGENT_ITERATIONS} for user {user.id}")

            response = provider.generate(
                messages=contents,
                tools=tools,
                system_instruction=system_prompt,
                model=model,
                temperature=0.2,
            )

            function_calls = response.tool_calls

            if function_calls:
                # Add model's turn to conversation history
                if (
                    response.raw_response
                    and getattr(response.raw_response, "candidates", None)
                    and response.raw_response.candidates[0].content
                ):
                    contents.append(response.raw_response.candidates[0].content)
                else:
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[
                                types.Part(function_call=types.FunctionCall(name=tc.name, args=tc.args))
                                for tc in function_calls
                            ],
                        )
                    )

                fn_response_parts: List[types.Part] = []

                for fc in function_calls:
                    fc_name = fc.name
                    fc_args = fc.args or {}
                    logger.info(f"Tool call requested: {fc_name} with args {fc_args}")

                    # Write tool_call raw_event
                    write_raw_event(
                        user.id,
                        source="tool_call",
                        payload={"tool": fc_name, "input": fc_args},
                        client=sb,
                    )

                    # Execute tool call
                    tool_result: Dict[str, Any] = {}
                    if fc_name == UPSERT_RECORD_TOOL_NAME:
                        table = fc_args.get("table", "")
                        data = fc_args.get("data", {})
                        tool_result = handle_upsert(sb, user, table, data)
                        if table == "contacts":
                            used_search = True
                            if tool_result.get("op") == "created":
                                added_new += 1
                            elif tool_result.get("op") in ("updated", "merged"):
                                merged += 1
                    elif fc_name == SEARCH_DATA_LAKE_TOOL_NAME:
                        used_search = True
                        q = fc_args.get("query", "")
                        filters = fc_args.get("filters")
                        inc_sample = fc_args.get("include_sample")
                        tool_result = search_data_lake(
                            client=sb,
                            query=q,
                            filters=filters,
                            actor_id=user.id,
                            include_sample=inc_sample,
                        )
                        for c in tool_result.get("contacts", []):
                            lake_contacts_found.append(c)
                        lake_found += tool_result.get("found", 0)
                    elif fc_name == WEB_SEARCH_ENRICH_TOOL_NAME:
                        if getattr(user, "is_demo", False):
                            tool_result = {
                                "error": "demo_users_cannot_search_web",
                                "message": "Demo users search existing data lake only; live web search and ingestion are disabled for demo accounts.",
                                "results": 0,
                                "accepted": 0,
                                "contacts": [],
                            }
                        else:
                            used_search = True
                            q = fc_args.get("query", "")
                            tool_result = web_search_enrich(
                                client=sb,
                                query=q,
                                actor_id=user.id,
                                extract_and_ingest=True,
                                user=user,
                            )
                            for c in tool_result.get("contacts", []):
                                lake_contacts_found.append(c)
                                records_created.append(
                                    RecordRef(
                                        table="contacts",
                                        id=c["id"],
                                        op=c.get("op", "created"),
                                    )
                                )
                            web_found += tool_result.get("results", tool_result.get("accepted", 0))
                            added_new += tool_result.get("accepted", 0)
                    elif fc_name == UPSERT_CONTACT_TOOL_NAME:
                        used_search = True
                        source = fc_args.get("source", "user_said")
                        source_url = fc_args.get("source_url")

                        if source == "web":
                            if not source_url:
                                tool_result = {"error": "web_candidate_missing_source_url"}
                            elif is_data_broker(source_url):
                                tool_result = {"error": "data_broker_url_rejected"}
                            else:
                                is_valid_name, name_err = validate_full_name(fc_args.get("name"))
                                if not is_valid_name:
                                    tool_result = {"error": f"full_name_rule_failed: {name_err}"}
                                else:
                                    target_comp = fc_args.get("company") or fc_args.get("company_name") or ""
                                    eval_text = (
                                        fc_args.get("snippet")
                                        or fc_args.get("matched_rule")
                                        or f"{fc_args.get('name', '')} {fc_args.get('title', '')} at {target_comp}"
                                    )
                                    cand_obj = CandidateContact(
                                        name=fc_args.get("name"),
                                        title=fc_args.get("title"),
                                        company=target_comp,
                                        source_url=source_url,
                                    )
                                    val = validate_recruiter_candidate(
                                        cand_obj,
                                        eval_text,
                                        target_company=target_comp,
                                    )
                                    if not val.is_valid:
                                        tool_result = {"error": f"precision_rule_failed: {val.failed_rule}"}
                                    else:
                                        fc_args["unverified"] = True
                                        fc_args["source_url"] = source_url
                                        fc_args["matched_rule"] = val.matched_rule
                                        upsert_res = upsert_contact(
                                            sb,
                                            fc_args,
                                            user,
                                            source="web",
                                            source_url=source_url,
                                        )
                                        tool_result = {
                                            "table": "contacts",
                                            "id": upsert_res["contact_id"],
                                            "op": upsert_res["op"],
                                        }
                                        records_created.append(
                                            RecordRef(
                                                table="contacts",
                                                id=upsert_res["contact_id"],
                                                op=upsert_res["op"],
                                            )
                                        )
                                        lake_contacts_found.append(
                                            {
                                                "id": upsert_res["contact_id"],
                                                "name": fc_args.get("name"),
                                                "title": fc_args.get("title"),
                                                "company_name": target_comp,
                                                "location": fc_args.get("location"),
                                                "source": "web",
                                                "source_url": source_url,
                                                "source_published_date": fc_args.get("source_published_date"),
                                                "unverified": True,
                                            }
                                        )
                                        already_tracked = any(
                                            c.get("id") == upsert_res["contact_id"] for c in lake_contacts_found
                                        )
                                        if not already_tracked:
                                            if upsert_res["op"] == "created":
                                                added_new += 1
                                            elif upsert_res["op"] in ("updated", "merged"):
                                                merged += 1
                        else:
                            # user_said: allowed for facts the user states themselves
                            upsert_res = upsert_contact(
                                sb,
                                fc_args,
                                user,
                                source="user_said",
                                source_url=fc_args.get("source_url"),
                            )
                            tool_result = {
                                "table": "contacts",
                                "id": upsert_res["contact_id"],
                                "op": upsert_res["op"],
                            }
                            records_created.append(
                                RecordRef(
                                    table="contacts",
                                    id=upsert_res["contact_id"],
                                    op=upsert_res["op"],
                                )
                            )
                            lake_contacts_found.append(
                                {
                                    "id": upsert_res["contact_id"],
                                    "name": fc_args.get("name"),
                                    "title": fc_args.get("title"),
                                    "company_name": fc_args.get("company") or fc_args.get("company_name"),
                                    "location": fc_args.get("location"),
                                    "source": "user_said",
                                    "source_url": fc_args.get("source_url"),
                                    "source_published_date": fc_args.get("source_published_date"),
                                    "unverified": True,
                                }
                            )
                            if upsert_res["op"] == "created":
                                added_new += 1
                            elif upsert_res["op"] in ("updated", "merged"):
                                merged += 1
                    elif fc_name == DRAFT_OUTREACH_TOOL_NAME:
                        cid = fc_args.get("contact_id")
                        channel = fc_args.get("channel", "email")
                        s_ctx = fc_args.get("sender_context")
                        tool_result = create_outreach_draft(
                            client=sb,
                            user=user,
                            contact_id=cid,
                            channel=channel,
                            sender_context=s_ctx,
                        )
                    elif fc_name == PROPOSE_VERIFY_TOOL_NAME:
                        doc_type = fc_args.get("document_type")
                        tool_result = handle_propose_verify(document_type=doc_type)
                        if "card" in tool_result:
                            cards.append(tool_result["card"])
                    elif fc_name == PROPOSE_REFERENCE_CHECK_TOOL_NAME:
                        comp = fc_args.get("internship_company")
                        tool_result = handle_propose_reference_check(internship_company=comp)
                        if "card" in tool_result:
                            cards.append(tool_result["card"])
                    elif fc_name == PROPOSE_REVOKE_REFERENCE_CHECK_TOOL_NAME:
                        reason = fc_args.get("reason")
                        tool_result = handle_propose_revoke_reference_check(reason=reason)
                        if "card" in tool_result:
                            cards.append(tool_result["card"])
                    else:
                        tool_result = {"error": f"Unknown tool: {fc_name}"}

                    # Write tool_result raw_event
                    write_raw_event(
                        user.id,
                        source="tool_result",
                        payload={"tool": fc_name, "result": tool_result},
                        client=sb,
                    )

                    # Log step
                    step = AgentStep(
                        type=AgentStepType.TOOL_CALL,
                        tool=fc_name,
                        input=fc_args,
                        output=tool_result,
                        at=datetime.now(timezone.utc),
                    )
                    steps.append(step)

                    # Track record created/updated
                    if "table" in tool_result and "op" in tool_result and "error" not in tool_result:
                        records_created.append(
                            RecordRef(
                                table=tool_result["table"],
                                id=tool_result.get("id"),
                                op=tool_result["op"],
                            )
                        )

                    # Prepare function response part for Gemini
                    fn_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=fc_name,
                                response=tool_result,
                            )
                        )
                    )

                # Feed function responses back into contents
                contents.append(types.Content(role="user", parts=fn_response_parts))
                continue

            else:
                # Model produced final textual reply
                reply_text = response.text or ""
                break

        # Deduplicate accepted contacts by ID
        seen_ids = set()
        unique_lake_contacts: List[Dict[str, Any]] = []
        for c in lake_contacts_found:
            cid = str(c.get("id"))
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                unique_lake_contacts.append(c)

        response_contacts: List[ContactCard] = []
        for c in unique_lake_contacts:
            c_sources = c.get("sources") or []
            if not c_sources and c.get("source_url"):
                s_url = c["source_url"]
                domain = urlparse(s_url).netloc if s_url else None
                c_sources = [
                    ContactSourceModel(
                        source=c.get("source", "web"),
                        source_url=s_url,
                        domain=domain,
                        confidence=float(c.get("confidence", 0.6) or 0.6),
                    )
                ]
            r_type = c.get("role_type") or "other"
            if r_type == "other" or not r_type:
                r_type = classify_recruiter_role(c.get("title"))

            card = ContactCard(
                id=str(c["id"]),
                name=c.get("name") or c.get("full_name") or "",
                title=c.get("title"),
                company_id=str(c.get("company_id")) if c.get("company_id") else None,
                company_name=c.get("company_name"),
                college_id=str(c.get("college_id")) if c.get("college_id") else None,
                college_name=c.get("college_name"),
                role_type=r_type,
                email=c.get("email"),
                linkedin_url=c.get("linkedin_url"),
                location=c.get("location"),
                source=c.get("source") or "web",
                source_url=c.get("source_url"),
                source_published_date=c.get("source_published_date"),
                stale=c.get("stale"),
                confidence=float(c.get("confidence", 0.6) if c.get("confidence") is not None else 0.6),
                unverified=bool(c.get("unverified", True)),
                saved=bool(c.get("saved", False)),
                is_sample=bool(c.get("is_sample", False)),
                sources=c_sources,
                first_seen_at=c.get("first_seen_at"),
                last_verified_at=c.get("last_verified_at"),
            )
            response_contacts.append(card)

        if used_search or unique_lake_contacts:
            if unique_lake_contacts:
                contact_lines = []
                for c in unique_lake_contacts:
                    c_name = c.get("name") or c.get("full_name") or "Contact"
                    c_title = c.get("title") or "Recruiter"
                    c_comp = c.get("company_name") or c.get("company") or "Company"
                    c_loc = c.get("location")
                    c_url = c.get("source_url")
                    c_date = c.get("source_published_date")
                    is_unv = c.get("unverified", True)
                    badge = "Unverified, check the source" if is_unv else "Verified"

                    parts = [f"- **{c_name}**, {c_title} at {c_comp}"]
                    parts.append(f"  - Status: {badge}")
                    if c_url:
                        parts.append(f"  - Source: [{c_url}]({c_url})")
                    if c_date:
                        parts.append(f"  - As of: {str(c_date)[:10]}")
                    if c_loc:
                        parts.append(f"  - Location: {c_loc}")
                    contact_lines.append("\n".join(parts))

                contacts_block = "\n\n".join(contact_lines)

                comp_names = {c.get("company_name") for c in unique_lake_contacts if c.get("company_name")}
                comp_str = ", ".join(sorted(comp_names)) if comp_names else "the target companies"
                intro = f"Here are the recruiter contacts found for {comp_str}:"
                outro = "Would you like me to draft an outreach message or note for any of these recruiters?"

                if reply_text:
                    paragraphs = [p.strip() for p in reply_text.split("\n\n") if p.strip()]
                    for p in reversed(paragraphs):
                        p_low = p.lower()
                        if "recorded your details" in p_low:
                            continue
                        if any(
                            k in p_low
                            for k in ("draft", "outreach", "connect", "reach out", "would you like", "let me know")
                        ):
                            outro = p
                            break
                    for p in paragraphs:
                        p_low = p.lower()
                        if "recorded your details" in p_low or "###" in p or p.startswith("-"):
                            continue
                        if not any(k in p_low for k in ("draft", "outreach", "connect", "reach out", "would you like")):
                            intro = p
                            break

                reply_text = f"{intro}\n\n{contacts_block}\n\n{outro}".strip()
            elif not reply_text:
                reply_text = "No verified recruiter contacts were found in the data lake or web search for your query."
        elif not reply_text:
            reply_text = "I've recorded your details successfully. Let me know if you need anything else!"

        # Safety net: never allow the word "Verified" for unverified contacts
        if any(c.get("unverified", True) for c in unique_lake_contacts):
            reply_text = re.sub(
                r"\bVerified\b(?!,\s*check)", "Unverified, check the source", reply_text, flags=re.IGNORECASE
            )

        # 4. Save final reply
        write_raw_event(
            user.id,
            source="agent_message",
            payload={"message": reply_text},
            client=sb,
        )

        steps.append(
            AgentStep(
                type=AgentStepType.FINAL_REPLY,
                output={"message": reply_text},
                at=datetime.now(timezone.utc),
            )
        )

        # 5. Search summary step if search was used
        if used_search:
            summary_text = (
                f"searched data lake, found {lake_found}; "
                f"searched web, found {web_found}; "
                f"added {added_new} new, merged {merged}"
            )
            steps.append(
                AgentStep(
                    type=AgentStepType.SEARCH_SUMMARY,
                    summary=summary_text,
                    output={"summary": summary_text},
                    at=datetime.now(timezone.utc),
                )
            )

        # 6. Close agent run as completed
        close_agent_run(
            run_id,
            status="completed",
            steps=[s.model_dump(mode="json") for s in steps],
            client=sb,
        )

        return ChatResponse(
            reply=reply_text,
            steps=steps,
            records_created=records_created,
            contacts=response_contacts,
            cards=cards,
        )

    except Exception as exc:
        logger.error(f"Agent loop error for user {user.id}: {exc}")
        close_agent_run(
            run_id,
            status="failed",
            steps=[s.model_dump(mode="json") for s in steps],
            client=sb,
        )
        raise exc
