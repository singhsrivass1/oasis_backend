from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query

from schemas.common import ListEnvelope, DataEnvelope, pagination_params
from schemas.review import ReviewItem
from services import reviews as reviews_service
from services.auth import CurrentUser, get_current_user
from services.supabase_client import get_supabase

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.get("", response_model=ListEnvelope[ReviewItem])
async def list_reviews(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_supabase),
) -> dict:
    page, limit = pagination_params(page, limit)
    findings, total = reviews_service.list_reviews(supabase, user.id, page=page, limit=limit)
    data = [reviews_service.to_review_item(f) for f in findings]
    return {
        "data": data,
        "pagination": {"page": page, "limit": limit, "total": total, "pages": math.ceil(total / limit) if total else 0},
    }


@router.get("/{review_id}", response_model=DataEnvelope[ReviewItem])
async def get_review(
    review_id: str, user: CurrentUser = Depends(get_current_user), supabase=Depends(get_supabase)
) -> dict:
    finding = reviews_service.get_review_or_404(supabase, user.id, review_id)
    return {"data": reviews_service.to_review_item(finding)}
