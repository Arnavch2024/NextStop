from fastapi import APIRouter
from app.models.api import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns API service health status, version, and server timestamp.",
)
async def health_check() -> HealthResponse:
    """Returns ok status for uptime monitors."""
    return HealthResponse(status="ok", version="0.1.0")

