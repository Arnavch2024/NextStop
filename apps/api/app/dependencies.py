from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.db.supabase import get_supabase_client, get_user_profile
from app.logger import logger
from app.models.db import UserProfile

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

        # If display_name is not set in DB profile, use metadata if available
        if not profile.display_name:
            user_metadata = getattr(auth_user, "user_metadata", {}) or {}
            profile.display_name = user_metadata.get("full_name") or getattr(auth_user, "email", None)

        logger.info(f"Authenticated user: id={user_id}, role={profile.role}")
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
