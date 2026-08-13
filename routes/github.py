from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from config import settings
from schemas.common import DataEnvelope
from schemas.github import GitHubConnectResponse, GitHubRepositoriesResponse, GitHubStatusResponse
from services import github as github_service
from services import github_app
from services import state_token
from services.auth import CurrentUser, get_current_user
from services.supabase_client import get_supabase

logger = logging.getLogger("oasis.github")

router = APIRouter(prefix="/api/v1/github", tags=["github"])


@router.get("/status", response_model=DataEnvelope[GitHubStatusResponse])
async def github_status(
    user: CurrentUser = Depends(get_current_user), supabase=Depends(get_supabase)
) -> dict:
    return {"data": github_service.get_status(supabase, user.id)}


@router.get("/repositories", response_model=DataEnvelope[GitHubRepositoriesResponse])
async def github_repositories(
    user: CurrentUser = Depends(get_current_user), supabase=Depends(get_supabase)
) -> dict:
    return {"data": await github_service.discover_repositories(supabase, user.id)}


@router.get("/connect", response_model=DataEnvelope[GitHubConnectResponse])
async def github_connect(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Starts the GitHub App connect flow.

    Returns a JSON payload containing the install URL rather than issuing
    an HTTP redirect directly -- this endpoint requires a Bearer token
    (like every other /api/v1 route), and a browser navigating directly to
    a URL can't attach one. The frontend calls this via a normal
    authenticated fetch, then opens the returned `install_url` itself
    (e.g. via url_launcher in Flutter).
    """
    if not settings.github_app_configured or not settings.github_app_slug:
        raise HTTPException(
            status_code=503,
            detail="GitHub App is not configured on this backend yet.",
        )
    state = state_token.sign_state(user.id)
    install_url = github_app.build_install_url(state)
    return {"data": {"install_url": install_url}}


@router.get("/callback")
async def github_callback(
    installation_id: int = Query(...),
    state: str = Query(...),
    setup_action: str | None = Query(default=None),
    supabase=Depends(get_supabase),
):
    """Hit directly by the user's browser after they finish GitHub's
    install picker -- NOT an authenticated /api/v1 route (no Bearer token
    is available on a plain browser redirect). The `state` parameter is
    the proof of identity instead; see services/state_token.py.

    Always ends in a redirect back to the frontend, success or failure,
    so the user never gets stuck looking at a bare JSON error page.
    """
    try:
        owner_id = state_token.verify_state(state)
    except HTTPException:
        return RedirectResponse(f"{settings.frontend_url}/settings?github=error")

    try:
                                                                         
                                                                  
                                                                           
                                                                   
                                              
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{github_app.GITHUB_API}/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {github_app.build_app_jwt()}",
                    "Accept": "application/vnd.github+json",
                },
            )
        account = resp.json().get("account", {}) if resp.status_code == 200 else {}

        github_app.upsert_installation_record(
            supabase,
            installation_id=installation_id,
            owner_id=owner_id,
            account_login=account.get("login", ""),
            account_type=account.get("type", "User"),
        )
        await github_app.sync_installation(supabase, owner_id=owner_id, installation_id=installation_id)
    except Exception:
        logger.exception("GitHub App callback failed for installation_id=%s", installation_id)
        return RedirectResponse(f"{settings.frontend_url}/settings?github=error")

    return RedirectResponse(f"{settings.frontend_url}/settings?github=connected")
