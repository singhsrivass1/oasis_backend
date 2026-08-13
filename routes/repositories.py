from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from schemas.common import DataEnvelope
from schemas.repository import Repository, RepositoryCreateRequest, RepositoryDetail
from services import repositories as repo_service
from services.auth import CurrentUser, get_current_user
from services.supabase_client import get_supabase

router = APIRouter(prefix="/api/v1/repositories", tags=["repositories"])


@router.get("", response_model=DataEnvelope[list[Repository]])
async def list_repositories(
    user: CurrentUser = Depends(get_current_user), supabase=Depends(get_supabase)
) -> dict:
    return {"data": repo_service.list_repositories(supabase, user.id)}


@router.post("", response_model=DataEnvelope[Repository], status_code=status.HTTP_201_CREATED)
async def create_repository(
    body: RepositoryCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_supabase),
) -> dict:
    """Registers a repository with Oasis.

    Documented limitation (task section 18): this ONLY creates the local
    `repositories` row. It does NOT install a GitHub webhook on the
    user's repo -- there is no GitHub App / OAuth flow in this backend to
    do that programmatically yet. The Flutter UI must present this as
    "repository registered" and separately instruct the user to add the
    webhook manually (or wait for that flow to ship), never as
    "GitHub webhook installed".
    """
    created = repo_service.create_repository(supabase, user.id, body)
    return {"data": created}


@router.get("/{repo_id}", response_model=DataEnvelope[RepositoryDetail])
async def get_repository(
    repo_id: str, user: CurrentUser = Depends(get_current_user), supabase=Depends(get_supabase)
) -> dict:
    repository = repo_service.get_repository_or_404(supabase, user.id, repo_id)

    findings = (
        supabase.table("findings")
        .select("*")
        .eq("owner_id", user.id)
        .eq("repo_id", repo_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
                                                                              
                                                                              
                                                                            
                                                                         
                                                                            
    activity = (
        supabase.table("activity")
        .select("*")
        .eq("owner_id", user.id)
        .ilike("meta", f"{repository['full_name']}%")
        .order("created_at", desc=True)
        .limit(25)
        .execute()
        .data
        or []
    )
    return {"data": {"repository": repository, "findings": findings, "activity": activity}}


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: str, user: CurrentUser = Depends(get_current_user), supabase=Depends(get_supabase)
) -> Response:
    repo_service.delete_repository(supabase, user.id, repo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
