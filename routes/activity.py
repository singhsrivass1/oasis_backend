from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query

from schemas.activity import ActivityItem
from schemas.common import ListEnvelope, pagination_params
from services import activity as activity_service
from services.auth import CurrentUser, get_current_user
from services.supabase_client import get_supabase

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


@router.get("", response_model=ListEnvelope[ActivityItem])
async def list_activity(
    limit: int = Query(default=25, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_supabase),
) -> dict:
    page, limit = pagination_params(page, limit)
    data, total = activity_service.list_activity(supabase, user.id, page=page, limit=limit)
    return {
        "data": data,
        "pagination": {"page": page, "limit": limit, "total": total, "pages": math.ceil(total / limit) if total else 0},
    }
