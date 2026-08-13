from __future__ import annotations

from fastapi import HTTPException
from supabase import Client

from schemas.repository import RepositoryCreateRequest
from services.validators import require_valid_uuid


def list_repositories(supabase: Client, owner_id: str) -> list[dict]:
    result = (
        supabase.table("repositories")
        .select("*")
        .eq("owner_id", owner_id)
        .order("name")
        .execute()
    )
    return result.data or []


def get_repository_or_404(supabase: Client, owner_id: str, repo_id: str) -> dict:
    require_valid_uuid(repo_id, not_found_message="Repository not found.")
    result = (
        supabase.table("repositories")
        .select("*")
        .eq("id", repo_id)
        .eq("owner_id", owner_id)                                                                
        .limit(1)
        .execute()
    )
    if not result.data:
                                                                           
                                                                       
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Repository not found."},
        )
    return result.data[0]


def create_repository(supabase: Client, owner_id: str, body: RepositoryCreateRequest) -> dict:
    existing = (
        supabase.table("repositories")
        .select("id")
        .eq("owner_id", owner_id)
        .eq("full_name", body.full_name)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_CONNECTED", "message": f"{body.full_name} is already connected."},
        )

    payload = {
        "owner_id": owner_id,
        "name": body.name,
        "full_name": body.full_name,
        "language": body.language,
        "status": "reviewing",                                            
        "score": 0,
        "prs_reviewed": 0,
        "issues_open": 0,
    }
    result = supabase.table("repositories").insert(payload).execute()
    return result.data[0]


def delete_repository(supabase: Client, owner_id: str, repo_id: str) -> None:
    """Deletes a repository record.

    Decision (documented per task section 19): findings/activity rows are
    NOT cascade-deleted. `findings.repo_id` and `oasis_findings.repo_id`
    are left as an orphaned reference (the FK in schema.sql has no
    ON DELETE clause specified, i.e. it defaults to NO ACTION/RESTRICT in
    Postgres). This preserves the audit trail -- a security finding
    shouldn't silently disappear just because a repo was disconnected --
    at the cost of `repo_id` on old findings pointing at a deleted repo.
    Frontend should treat findings.repo_id as "best effort" and always
    render repo_name (which is denormalized onto the finding) instead.

    If the underlying repositories_repo_id_fkey is genuinely RESTRICT,
    this call will surface a 409 from Postgres via supabase-py rather than
    silently failing -- that's caught and reported here.
    """
    get_repository_or_404(supabase, owner_id, repo_id)
    try:
        supabase.table("repositories").delete().eq("id", repo_id).eq("owner_id", owner_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DELETE_BLOCKED",
                "message": "Repository could not be deleted, likely due to referencing findings/activity rows.",
            },
        ) from exc