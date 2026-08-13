from __future__ import annotations

from fastapi import APIRouter, Depends

from schemas.common import DataEnvelope
from schemas.dashboard import DashboardResponse
from services.auth import CurrentUser, get_current_user
from services.dashboard import build_dashboard
from services.supabase_client import get_supabase

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard", response_model=DataEnvelope[DashboardResponse])
async def get_dashboard(
    user: CurrentUser = Depends(get_current_user), supabase=Depends(get_supabase)
) -> dict:
    data = build_dashboard(supabase, user.id)
    return {"data": data}
