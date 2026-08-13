from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query

from schemas.common import DataEnvelope, ListEnvelope, Pagination, pagination_params
from schemas.finding import Finding, FindingStatus, FindingStatusUpdateRequest, Severity
from services import findings as findings_service
from services import patch_apply
from services.auth import CurrentUser, get_current_user
from services.supabase_client import get_supabase

router = APIRouter(prefix="/api/v1/findings", tags=["findings"])


@router.get("", response_model=ListEnvelope[Finding])
async def list_findings(
    repo_id: str | None = None,
    severity: Severity | None = None,
    status: FindingStatus | None = None,
    pr_number: int | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_supabase),
) -> dict:
    page, limit = pagination_params(page, limit)
    data, total = findings_service.list_findings(
        supabase,
        user.id,
        repo_id=repo_id,
        severity=severity,
        status=status,
        pr_number=pr_number,
        page=page,
        limit=limit,
    )
    return {
        "data": data,
        "pagination": {"page": page, "limit": limit, "total": total, "pages": math.ceil(total / limit) if total else 0},
    }


@router.get("/{finding_id}", response_model=DataEnvelope[Finding])
async def get_finding(
    finding_id: str, user: CurrentUser = Depends(get_current_user), supabase=Depends(get_supabase)
) -> dict:
    return {"data": findings_service.get_finding_or_404(supabase, user.id, finding_id)}


@router.patch("/{finding_id}", response_model=DataEnvelope[Finding])
async def update_finding(
    finding_id: str,
    body: FindingStatusUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_supabase),
) -> dict:
    """Updates a finding's status per the state machine in schemas/finding.py.

    When the new status is "approved", this ALSO automatically attempts
    to open a fix pull request on the user's repo (see
    services/patch_apply.py) -- a new branch off the original PR's head
    branch, with the suggested patch committed, opened as a fresh PR.
    Oasis never merges anything itself; the PR is left for human review.

    This is a deliberate, confirmed product decision (previously the
    endpoint was status-only by design -- see git history / the original
    "Approving a finding does NOT deploy anything" note this docstring
    used to carry). If the fix-PR attempt fails for any reason (missing
    GitHub App permissions, unknown source branch, file changed since
    analysis, etc.), the approval itself still succeeds -- the failure is
    recorded on the finding (fix_status="failed", fix_error=<message>)
    and returned to the caller, never silently swallowed and never
    blocking the status transition.
    """
    updated = findings_service.update_finding_status(supabase, user.id, finding_id, body.status)

    if body.status == "approved":
        await patch_apply.apply_patch_and_open_pr(supabase, updated)
        updated = findings_service.get_finding_or_404(supabase, user.id, finding_id)

    return {"data": updated}
