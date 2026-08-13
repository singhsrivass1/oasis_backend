from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from supabase import Client

from schemas.finding import ALLOWED_TRANSITIONS
from services.validators import require_valid_uuid


def list_findings(
    supabase: Client,
    owner_id: str,
    *,
    repo_id: str | None,
    severity: str | None,
    status: str | None,
    pr_number: int | None,
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    query = supabase.table("findings").select("*", count="exact").eq("owner_id", owner_id)

    if repo_id:
        query = query.eq("repo_id", repo_id)
    if severity:
        query = query.eq("severity", severity)
    if status:
        query = query.eq("status", status)
    if pr_number is not None:
        query = query.eq("patch_pr_number", pr_number)

    start = (page - 1) * limit
    end = start + limit - 1
    result = query.order("created_at", desc=True).range(start, end).execute()
    total = result.count if result.count is not None else len(result.data or [])
    return result.data or [], total


def get_finding_or_404(supabase: Client, owner_id: str, finding_id: str) -> dict:
    require_valid_uuid(finding_id, not_found_message="Finding not found.")
    result = (
        supabase.table("findings")
        .select("*")
        .eq("id", finding_id)
        .eq("owner_id", owner_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Finding not found."})
    return result.data[0]


def update_finding_status(supabase: Client, owner_id: str, finding_id: str, new_status: str) -> dict:
    """Enforces schemas.finding.ALLOWED_TRANSITIONS and stamps the matching
    *_at timestamp. This does NOT touch GitHub or deploy anything -- see
    schemas/finding.py and the API docstring in routes/findings.py for why
    that's an explicit, documented non-goal of this endpoint.
    """
    current = get_finding_or_404(supabase, owner_id, finding_id)
    current_status = current["status"]

    if new_status == current_status:
        return current                                  

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_TRANSITION",
                "message": f"Cannot transition finding from '{current_status}' to '{new_status}'.",
            },
        )

    update_payload: dict = {"status": new_status}
    now = datetime.now(timezone.utc).isoformat()
    if new_status == "approved":
        update_payload["approved_at"] = now
    elif new_status == "dismissed":
        update_payload["dismissed_at"] = now
    elif new_status == "resolved":
        update_payload["resolved_at"] = now

    result = (
        supabase.table("findings")
        .update(update_payload)
        .eq("id", finding_id)
        .eq("owner_id", owner_id)
        .execute()
    )
    return result.data[0]