from __future__ import annotations

from fastapi import APIRouter, Depends

from schemas.common import DataEnvelope
from schemas.user import MeResponse
from services.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/me", response_model=DataEnvelope[MeResponse])
async def get_me(user: CurrentUser = Depends(get_current_user)) -> dict:
    profile = user.profile
    safe = {
        "id": profile["id"],
        "name": profile["name"],
        "email": profile["email"],
        "org": profile.get("org") or "",
        "plan": profile.get("plan") or "starter",
        "avatar": profile.get("avatar") or "",
        "auth_provider": profile.get("auth_provider") or "local",
        "github_username": profile.get("github_username") or "",
        "github_repos": profile.get("github_repos") or 0,
        "github_followers": profile.get("github_followers") or 0,
        "created_at": profile["created_at"],
    }
    return {"data": safe}
