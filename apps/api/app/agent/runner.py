from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from supabase import Client

from app.agent.prompts import get_system_prompt_for_role
from app.agent.tools import (
    UPSERT_RECORD_TOOL,
    UPSERT_RECORD_TOOL_NAME,
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
from app.logger import logger
from app.models.api import (
    AgentStep,
    AgentStepType,
    ChatResponse,
    RecordRef,
)
from app.models.db import ProfileRole, UserProfile

MAX_AGENT_ITERATIONS = 5

_gemini_client: Optional[genai.Client] = None


def get_gemini_client() -> genai.Client:
    """Returns the Gemini SDK client."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.effective_gemini_api_key)
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
) -> ChatResponse:
    """
    Executes the conversational agent loop:
    1. Records the incoming user message to raw_events.
    2. Initializes an agent_runs entry.
    3. Runs up to MAX_AGENT_ITERATIONS turns calling Gemini with tool use.
    4. Handles upsert_record invocations, writes events, and aggregates steps.
    5. Writes the final reply to raw_events and updates agent_runs to completed.
    """
    sb = supabase_client or get_supabase_client()
    gm = gemini_client or get_gemini_client()
    model = model_name or settings.GEMINI_MODEL

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

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[UPSERT_RECORD_TOOL],
            temperature=0.2,
        )

        reply_text = ""
        iteration = 0

        # 3. Multi-turn loop (max 5 iterations)
        while iteration < MAX_AGENT_ITERATIONS:
            iteration += 1
            logger.info(f"Agent turn iteration {iteration}/{MAX_AGENT_ITERATIONS} for user {user.id}")

            response = gm.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            # Check for candidate and function calls
            if not response.candidates:
                reply_text = "I'm sorry, I could not generate a response at this time."
                break

            candidate = response.candidates[0]
            function_calls = response.function_calls

            if function_calls:
                # Add model's turn to conversation history
                contents.append(candidate.content)

                fn_response_parts: List[types.Part] = []

                for fc in function_calls:
                    fc_name = fc.name
                    fc_args = fc.args or {}
                    logger.info(f"Tool call requested: {fc_name} on table {fc_args.get('table')}")

                    # Write tool_call raw_event
                    write_raw_event(
                        user.id,
                        source="tool_call",
                        payload={"tool": fc_name, "input": fc_args},
                        client=sb,
                    )

                    # Execute tool call
                    if fc_name == UPSERT_RECORD_TOOL_NAME:
                        table = fc_args.get("table", "")
                        data = fc_args.get("data", {})
                        upsert_result = handle_upsert(sb, user, table, data)
                    else:
                        upsert_result = {"error": f"Unknown tool: {fc_name}"}

                    # Write tool_result raw_event
                    write_raw_event(
                        user.id,
                        source="tool_result",
                        payload={"tool": fc_name, "result": upsert_result},
                        client=sb,
                    )

                    # Log step
                    step = AgentStep(
                        type=AgentStepType.TOOL_CALL,
                        tool=fc_name,
                        input=fc_args,
                        output=upsert_result,
                        at=datetime.now(timezone.utc),
                    )
                    steps.append(step)

                    # Track record created/updated
                    if "table" in upsert_result and "op" in upsert_result and "error" not in upsert_result:
                        records_created.append(
                            RecordRef(
                                table=upsert_result["table"],
                                id=upsert_result.get("id"),
                                op=upsert_result["op"],
                            )
                        )

                    # Prepare function response part for Gemini
                    fn_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=fc_name,
                                response=upsert_result,
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
            reply_text = "I've recorded your details successfully. Let me know if you need anything else!"

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

        # 5. Close agent run as completed
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
