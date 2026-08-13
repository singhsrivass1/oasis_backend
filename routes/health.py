from __future__ import annotations

from fastapi import APIRouter

from config import settings
from services.supabase_client import get_supabase

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict:
                                                                  
    return {"status": "Oasis Backend Online", "version": "3.1"}


@router.get("/health")
async def health_check() -> dict:
    """Real dependency check, not a hardcoded 'healthy'.

    Actually queries Supabase with a trivial call. Does NOT call Gemini or
    GitHub on every health check (that would be wasteful/rate-limit-risky
    for a liveness probe) -- it reports whether those integrations are
    *configured*, which is the honest thing a health check can say without
    making an external call per request.
    """
    database_ok = False
    database_detail = "not configured"
    if settings.supabase_url and settings.supabase_key:
        try:
            get_supabase().table("users").select("id").limit(1).execute()
            database_ok = True
            database_detail = "connected"
        except Exception as exc:                                              
            database_detail = f"error: {exc.__class__.__name__}"

    return {
        "status": "healthy" if database_ok else "degraded",
        "service": "oasis-backend",
        "checks": {
            "database": database_detail,
            "gemini_configured": bool(settings.gemini_api_key),
            "github_configured": bool(settings.github_token),
        },
    }
