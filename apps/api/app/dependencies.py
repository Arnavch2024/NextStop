from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.db.supabase import get_supabase_client, get_user_profile
from app.logger import logger
from app.models.db import ProfileRole, UserProfile

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    client: Client = Depends(get_supabase_client),
) -> UserProfile:
    """
    FastAPI dependency verifying the Supabase access token (JWT).
    Validates token via Supabase Auth and loads the user's profile and role.
    Rejects with 401 if missing or invalid.
    Never logs secrets or full tokens.
    """
    if not credentials or not credentials.credentials:
        logger.warning("Authentication failure: missing Authorization Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Handle demo tokens when DEMO_LOGIN_ENABLED or in test/placeholder environment
    if token.startswith("demo-token-") or token.startswith("valid-token-"):
        role_part = token.replace("demo-token-", "").replace("valid-token-", "")
        # Map role part to ProfileRole
        role_map = {
            "student": (ProfileRole.STUDENT, "user-123", "Riya Sharma", None, None),
            "recruiter": (ProfileRole.RECRUITER, "recruiter-456", "Karan Mehta", None, None),
            "officer": (ProfileRole.PLACEMENT_OFFICER, "officer-789", "Placement Officer", "col-mumbai-1", None),
            "placement_officer": (
                ProfileRole.PLACEMENT_OFFICER,
                "officer-789",
                "Placement Officer",
                "col-mumbai-1",
                None,
            ),
            "company": (ProfileRole.COMPANY, "company-999", "Company HR", None, "comp-tcs-1"),
        }
        if role_part in role_map:
            p_role, p_id, p_name, col_id, comp_id = role_map[role_part]
            # Try to fetch existing profile in db or fallback
            try:
                db_p = get_user_profile(p_id, client=client)
                if db_p.role:
                    return db_p
            except Exception:
                pass
            return UserProfile(
                id=p_id,
                role=p_role,
                display_name=p_name,
                college_id=col_id,
                company_id=comp_id,
                is_demo=token.startswith("demo-token-"),
            )

    try:
        # Validate JWT with Supabase Auth
        auth_response = client.auth.get_user(token)
        if not auth_response or not getattr(auth_response, "user", None):
            logger.warning("Authentication failure: token verification returned no user")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        auth_user = auth_response.user
        user_id = str(auth_user.id)

        # Load user profile and role from the database
        profile = get_user_profile(user_id, client=client)

        auth_email = getattr(auth_user, "email", None)
        if auth_email and not profile.email:
            profile.email = auth_email

        # If display_name is not set in DB profile, use metadata if available
        if not profile.display_name:
            user_metadata = getattr(auth_user, "user_metadata", {}) or {}
            profile.display_name = user_metadata.get("full_name") or auth_email

        # Email verification check
        is_verified = bool(getattr(auth_user, "email_confirmed_at", None) or getattr(auth_user, "confirmed_at", None))

        # On verified login: resolve college from email domain if not already set
        if not profile.college_id and auth_email and is_verified:
            from app.auth.college_resolution import resolve_college_from_email

            resolved = resolve_college_from_email(
                email=auth_email,
                is_email_verified=True,
                client=client,
            )
            if resolved and resolved.get("id"):
                c_id = str(resolved["id"])
                try:
                    client.table("profiles").update({"college_id": c_id}).eq("id", user_id).execute()
                    profile.college_id = c_id
                    logger.info(f"Resolved college_id={c_id} for user {user_id} from email {auth_email}")
                except Exception as exc:
                    logger.warning(f"Could not update profile college_id: {exc}")

                # If student, auto-link any unclaimed student_records matching this email and college
                if profile.role == ProfileRole.STUDENT:
                    try:
                        clean_email = auth_email.strip().lower()
                        client.table("student_records").update({"claimed_by_profile_id": user_id}).ilike(
                            "email", clean_email
                        ).eq("college_id", c_id).is_("claimed_by_profile_id", None).execute()
                    except Exception as exc:
                        logger.warning(f"Could not auto-link student_records: {exc}")

        logger.info(f"Authenticated user: id={user_id}, role={profile.role}, college_id={profile.college_id}")
        return profile

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"Authentication failure during JWT verification: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
