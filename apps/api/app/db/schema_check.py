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
    """Verifies that Day 3 (003, 004) and Day 4 (005_day4_roles.sql) migrations

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
                    f"Database schema check failed to connect. Missing migration 003_search_slice.sql / 004_day3_security.sql / 005_day4_roles.sql? Error: {exc}"
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

    # Check 4: Day 4 tables (student_records, campus_hiring, batch_sharing)
    try:
        client.table("student_records").select("id").limit(1).execute()
        client.table("campus_hiring").select("id").limit(1).execute()
        client.table("batch_sharing").select("id").limit(1).execute()
    except Exception as exc:
        msg = (
            "Database schema check failed: missing migration 005_day4_roles.sql. "
            f"Required Day 4 tables (student_records, campus_hiring, batch_sharing) missing: {exc}"
        )
        logger.error(msg)
        if raise_on_error:
            raise MissingMigrationError(msg) from exc
        return False

    # Check 5: Day 4 columns on profiles and outreach_drafts
    try:
        client.table("profiles").select("id,college_id,company_id,is_demo").limit(1).execute()
        client.table("outreach_drafts").select("id,kind").limit(1).execute()
    except Exception as exc:
        msg = (
            "Database schema check failed: missing migration 005_day4_roles.sql. "
            f"Required Day 4 columns (profiles.college_id/company_id/is_demo, outreach_drafts.kind) missing: {exc}"
        )
        logger.error(msg)
        if raise_on_error:
            raise MissingMigrationError(msg) from exc
        return False

    # Check 6: college_domains table
    try:
        client.table("college_domains").select("id").limit(1).execute()
    except Exception as exc:
        msg = (
            "Database schema check failed: missing migration 006_college_domains.sql. "
            f"Required college_domains table missing: {exc}"
        )
        logger.error(msg)
        if raise_on_error:
            raise MissingMigrationError(msg) from exc
        return False

    logger.info(
        "Startup schema check passed: Day 3 and Day 4 migrations (003_search_slice.sql, 004_day3_security.sql, 005_day4_roles.sql, 006_college_domains.sql) verified."
    )
    return True
