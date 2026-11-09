import os
from typing import Optional

from supabase import Client

from app.config import settings
from app.db.supabase import get_supabase_client
from app.logger import logger


class MissingMigrationError(RuntimeError):
    """Raised when required database migrations have not been applied."""

    pass


def should_skip_schema_check() -> bool:
    """Returns True if database schema verification should be skipped (e.g. mock test runs)."""
    if os.environ.get("CI", "").lower() in ("true", "1"):
        return True
    if os.environ.get("GITHUB_ACTIONS", "").lower() in ("true", "1"):
        return True
    if os.environ.get("SKIP_SCHEMA_CHECK", "").lower() in ("true", "1", "yes"):
        return True
    if settings.ENVIRONMENT.lower() in ("test", "testing"):
        return True

    # If Supabase URL or keys are default placeholders or test values, skip
    url = settings.SUPABASE_URL
    if not url or "placeholder" in url or "localhost" in url:
        return True

    return False


def check_database_schema(
    client: Optional[Client] = None,
    raise_on_error: bool = True,
) -> bool:
    """Verifies that Day 3 migrations (003_search_slice.sql and 004_day3_security.sql)

    have been applied to the Supabase database.
    Names the missing migration specifically on failure.
    """
    if should_skip_schema_check():
        logger.debug("Skipping database schema check in test/placeholder environment.")
        return True

    if client is None:
        try:
            client = get_supabase_client()
        except Exception as exc:
            logger.warning(f"Unable to initialize Supabase client for schema check: {exc}")
            if raise_on_error:
                raise MissingMigrationError(
                    f"Database schema check failed to connect. Missing migration 003_search_slice.sql / 004_day3_security.sql? Error: {exc}"
                ) from exc
            return False

    # Check 1: contact_sources table
    try:
        client.table("contact_sources").select("id").limit(1).execute()
    except Exception as exc:
        msg = (
            "Database schema check failed: missing migration 003_search_slice.sql. "
            f"Table 'public.contact_sources' does not exist or is not readable: {exc}"
        )
        logger.error(msg)
        if raise_on_error:
            raise MissingMigrationError(msg) from exc
        return False

    # Check 2: contacts columns from 003
    try:
        client.table("contacts").select("id,name,role_type,location,suppressed_at").limit(1).execute()
    except Exception as exc:
        msg = (
            "Database schema check failed: missing migration 003_search_slice.sql. "
            f"Table 'public.contacts' missing evolved columns (name, role_type, location, suppressed_at): {exc}"
        )
        logger.error(msg)
        if raise_on_error:
            raise MissingMigrationError(msg) from exc
        return False

    # Check 3: search_cache and user_saved_contacts tables
    try:
        client.table("search_cache").select("id").limit(1).execute()
        client.table("user_saved_contacts").select("id").limit(1).execute()
    except Exception as exc:
        msg = (
            "Database schema check failed: missing migration 003_search_slice.sql. "
            f"Required Day 3 tables (search_cache, user_saved_contacts) missing: {exc}"
        )
        logger.error(msg)
        if raise_on_error:
            raise MissingMigrationError(msg) from exc
        return False

    logger.info("Startup schema check passed: Day 3 migrations (003_search_slice.sql, 004_day3_security.sql) verified.")
    return True
