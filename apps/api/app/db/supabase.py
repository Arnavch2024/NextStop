import uuid
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from app.config import settings
from app.logger import logger
from app.models.db import ProfileRole, UserProfile

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Returns a singleton Supabase client using the service role key."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_KEY,
        )
    return _supabase_client


def get_user_profile(user_id: str, client: Optional[Client] = None) -> UserProfile:
    """Loads a user's profile from the database, or initializes one if not present."""
    cli = client or get_supabase_client()
    try:
        response = cli.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            role = None
            if row.get("role"):
                try:
                    role = ProfileRole(row["role"])
                except ValueError:
                    role = None
            return UserProfile(
                id=str(row["id"]),
                role=role,
                display_name=row.get("display_name"),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )
    except Exception as exc:
        logger.warning(f"Error fetching profile for user {user_id}: {exc}")

    # Fallback default profile if not yet created in DB
    return UserProfile(id=user_id, role=None, display_name=None)


def create_agent_run(actor_id: str, client: Optional[Client] = None) -> str:
    """Creates a new agent_runs record with status 'running' and returns its ID."""
    cli = client or get_supabase_client()
    run_id = str(uuid.uuid4())
    try:
        cli.table("agent_runs").insert(
            {
                "id": run_id,
                "profile_id": actor_id,
                "status": "running",
                "steps": [],
            }
        ).execute()
    except Exception as exc:
        logger.warning(f"Could not write agent_runs record {run_id}: {exc}")
    return run_id


def close_agent_run(
    run_id: str,
    status: str,
    steps: List[Dict[str, Any]],
    client: Optional[Client] = None,
) -> None:
    """Updates an agent_runs record with final status and steps."""
    cli = client or get_supabase_client()
    try:
        cli.table("agent_runs").update(
            {
                "status": status,
                "steps": steps,
            }
        ).eq("id", run_id).execute()
    except Exception as exc:
        logger.warning(f"Could not update agent_runs {run_id}: {exc}")


def write_raw_event(
    actor_id: str,
    source: str,
    payload: Dict[str, Any],
    source_url: Optional[str] = None,
    client: Optional[Client] = None,
) -> str:
    """Writes an immutable raw_event and returns the created event ID."""
    cli = client or get_supabase_client()
    event_id = str(uuid.uuid4())
    try:
        cli.table("raw_events").insert(
            {
                "id": event_id,
                "actor_id": actor_id,
                "source": source,
                "payload": payload,
                "source_url": source_url,
            }
        ).execute()
    except Exception as exc:
        logger.warning(f"Could not write raw_event {source}: {exc}")
    return event_id


def load_recent_events(
    actor_id: str,
    limit: int = 50,
    client: Optional[Client] = None,
) -> List[Dict[str, Any]]:
    """Loads recent raw_events for the actor ordered chronologically."""
    cli = client or get_supabase_client()
    try:
        response = (
            cli.table("raw_events")
            .select("*")
            .eq("actor_id", actor_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        data = response.data or []
        # Return ascending order for chat context history
        return list(reversed(data))
    except Exception as exc:
        logger.warning(f"Error loading recent events for user {actor_id}: {exc}")
        return []
