from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from app.cache.llm_cache import get_llm_reply_cache

router = APIRouter(prefix="/v1/cache", tags=["Cache"])


class InvalidateRequest(BaseModel):
    reason: str = "manual_api_trigger"


@router.get(
    "/stats",
    summary="Get LLM reply cache diagnostics",
    description="Inspect hit rate, cached entries, lake version, and saved Gemini API calls.",
)
def get_cache_stats() -> Dict[str, Any]:
    cache = get_llm_reply_cache()
    return cache.get_stats()


@router.post(
    "/clear",
    summary="Clear LLM reply cache",
    description="Clears all cached Gemini responses and increments data lake version token.",
)
def clear_cache(body: InvalidateRequest = InvalidateRequest()) -> Dict[str, Any]:
    cache = get_llm_reply_cache()
    cache.invalidate(reason=body.reason)
    return {
        "success": True,
        "message": f"Cache cleared successfully. Reason: {body.reason}",
        "stats": cache.get_stats(),
    }
