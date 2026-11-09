from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from supabase import Client

from app.agent.prompts import get_system_prompt_for_role
from app.agent.tools import (
    DRAFT_OUTREACH_TOOL_NAME,
    SEARCH_DATA_LAKE_TOOL_NAME,
    UPSERT_CONTACT_TOOL_NAME,
    UPSERT_RECORD_TOOL_NAME,
    WEB_SEARCH_ENRICH_TOOL_NAME,
    get_tools_for_role,
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
    RecordRef,
)
from app.models.db import ProfileRole, UserProfile
from app.search.data_lake import search_data_lake
from app.search.dedupe import upsert_contact
from app.search.extract_contacts import (
    CandidateContact,
    validate_full_name,
    validate_recruiter_candidate,
)
from app.search.outreach import create_outreach_draft
from app.search.providers.extract import is_data_broker
from app.search.web import format_web_content_block, web_search_enrich

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

        system_prompt = get_system_prompt_for_role(user.role, student_data=student_data, missing_fields=missing_fields)
        history = load_recent_events(user.id, limit=50, client=sb)
        contents = build_gemini_contents_from_history(history, message)

        tools = get_tools_for_role(user.role)

        reply_text = ""
        iteration = 0
        lake_found = 0
        web_found = 0
        added_new = 0
        merged = 0
        used_search = False
        lake_contacts_found: List[Dict[str, Any]] = []
        last_web_content = ""

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
                        used_search = True
                        q = fc_args.get("query", "")
                        tool_result = web_search_enrich(
                            client=sb,
                            query=q,
                            actor_id=user.id,
                        )
                        last_web_content = format_web_content_block(tool_result.get("results", []))
                        tool_result["web_content"] = last_web_content
                        web_found += len(tool_result.get("results", []))
                    elif fc_name == UPSERT_CONTACT_TOOL_NAME:
                        used_search = True
                        source = fc_args.get("source", "user_said")
                        source_url = fc_args.get("source_url")

                        # Item 2 Guard: Web-derived contacts must pass the ingestion pipeline
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
                                    eval_text = (
                                        fc_args.get("snippet") or fc_args.get("matched_rule") or last_web_content or ""
                                    )
                                    target_comp = fc_args.get("company") or fc_args.get("company_name") or ""
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
                                            source=source,
                                            source_url=source_url,
                                        )
                                        tool_result = {
                                            "table": "contacts",
                                            "id": upsert_res["contact_id"],
                                            "op": upsert_res["op"],
                                        }
                                        if upsert_res["op"] == "created":
                                            added_new += 1
                                        elif upsert_res["op"] in ("updated", "merged"):
                                            merged += 1
                        else:
                            # user_said: allowed only for facts the user states themselves
                            upsert_res = upsert_contact(
                                sb,
                                fc_args,
                                user,
                                source="user_said",
                                source_url=source_url,
                            )
                            tool_result = {
                                "table": "contacts",
                                "id": upsert_res["contact_id"],
                                "op": upsert_res["op"],
                            }
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

        if not reply_text:
            if used_search or lake_contacts_found:
                if lake_contacts_found:
                    lines = ["Here are the recruiter contacts found:"]
                    for c in lake_contacts_found:
                        c_name = c.get("name") or c.get("full_name") or "Contact"
                        c_title = c.get("title") or "Recruiter"
                        c_comp = c.get("company_name") or c.get("company") or "Company"
                        c_loc = c.get("location") or "Location not stated"
                        c_src = c.get("source") or "web"
                        c_date = c.get("source_published_date") or "N/A"
                        lines.append(
                            f"- {c_name}, {c_title} at {c_comp} (Location: {c_loc}, Source: {c_src}, As of: {c_date})"
                        )
                    reply_text = "\n".join(lines)
                else:
                    reply_text = (
                        "No verified recruiter contacts were found in the data lake or web search for your query."
                    )
            else:
                reply_text = "I've recorded your details successfully. Let me know if you need anything else!"
        elif (used_search or lake_contacts_found) and "recorded your details" in reply_text.lower():
            if lake_contacts_found:
                lines = ["Here are the recruiter contacts found:"]
                for c in lake_contacts_found:
                    c_name = c.get("name") or c.get("full_name") or "Contact"
                    c_title = c.get("title") or "Recruiter"
                    c_comp = c.get("company_name") or c.get("company") or "Company"
                    c_loc = c.get("location") or "Location not stated"
                    c_src = c.get("source") or "web"
                    c_date = c.get("source_published_date") or "N/A"
                    lines.append(
                        f"- {c_name}, {c_title} at {c_comp} (Location: {c_loc}, Source: {c_src}, As of: {c_date})"
                    )
                reply_text = "\n".join(lines)
            else:
                reply_text = "No verified recruiter contacts were found in the data lake or web search for your query."

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
