"""GitHub webhook processing pipeline.

This is main.py's existing logic, moved here unchanged in substance:

    signature check -> event/action filter -> fetch patch -> create
    pending oasis_findings row -> analyze -> update row -> comment on PR

ADDED (per task section 9 / 60 -- "if synchronization between
[oasis_findings and findings] is required for the dashboard to work,
implement it carefully and document it"):

`oasis_findings` is the raw ingestion/analysis record. It is NOT read by
any /api/v1 route, and the Flutter dashboard has no other data source for
"a PR was scanned" -- so without a sync step, the dashboard would always
be empty. This module therefore ALSO writes a matching row into
`findings` (product-facing model) and `activity` (for the activity feed),
using the same repo -> owner_id resolution main.py already performs via
the `repositories` table. If the repo isn't registered (no owner_id
resolvable), the oasis_findings audit record is still created -- nothing
about the original webhook contract is weakened -- but the findings/
activity sync is skipped, since findings.owner_id is NOT NULL and there's
no owner to attribute it to. That case is logged, not silently dropped.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone

import httpx
from supabase import Client

from config import settings
from schemas.webhook import OasisAnalysisResponse

logger = logging.getLogger("oasis.webhook")


def verify_signature(raw_payload: bytes, signature_header: str | None) -> None:
    """Raises via caller if invalid. Returns True/False.

    Preserves the exact original semantics: if either WEBHOOK_SECRET or
    the signature header is absent, verification is skipped (this matches
    main.py's current `if WEBHOOK_SECRET and x_hub_signature_256:` guard).
    That original behavior is intentionally NOT tightened here per
    "preserve the existing webhook contract unless absolutely necessary" --
    it is flagged instead in the final report's Security section, since a
    request with a missing signature header currently bypasses
    verification rather than being rejected.
    """
    if not (settings.github_webhook_secret and signature_header):
        return True
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(), raw_payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def fetch_patch(patch_url: str, *, token: str | None = None) -> str:
    """Fetches the PR diff. `token` (a GitHub App installation token, when
    the repo is connected via the App) is required for private repos --
    the unauthenticated path only works for public ones."""
    headers = {"Authorization": f"token {token}"} if token else {}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(patch_url, follow_redirects=True, headers=headers)
            if response.status_code == 200:
                return response.text
            logger.warning("GitHub blocked the diff download. status=%s", response.status_code)
    except Exception:
        logger.warning("Direct patch fetch failed.", exc_info=True)
    return ""


def resolve_repo(supabase: Client, repo_name: str) -> dict | None:
    result = (
        supabase.table("repositories")
        .select("id, owner_id, installation_id")
        .eq("full_name", repo_name)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def create_pending_record(
    supabase: Client,
    *,
    repo_name: str,
    repo_row: dict | None,
    pr_number: int,
    author: str,
    diff_text: str,
) -> str:
    payload = {
        "repo_name": repo_name,
        "repo_id": repo_row["id"] if repo_row else None,
        "owner_id": repo_row["owner_id"] if repo_row else None,
        "pr_number": pr_number,
        "pr_author": author,
        "status": "pending",
        "patch_content": diff_text,
    }
    result = supabase.table("oasis_findings").insert(payload).execute()
    return result.data[0]["id"]


def create_pending_finding(
    supabase: Client,
    *,
    repo_row: dict,
    repo_name: str,
    pr_number: int,
    pr_branch: str,
    pr_title: str,
    diff_text: str,
) -> str | None:
    """See module docstring. Returns the new findings.id, or None if it
    was skipped (repo not registered / owner unresolved).

    Captures the PR's head branch and title -- previously these columns
    existed but were never populated (they always rendered blank on the
    Reviews screen). This also becomes required data for the automated
    fix-PR flow (services/patch_apply.py): the fix branch is created off
    of this exact PR branch, so the patched file matches what's actually
    in the PR rather than the repo's default branch.
    """
    payload = {
        "owner_id": repo_row["owner_id"],
        "repo_id": repo_row["id"],
        "repo_name": repo_name,
        "title": "Pending scan...",
        "location": "",
        "severity": "advisory",
        "status": "open",
        "patch_diff": diff_text,
        "patch_pr_number": pr_number,
        "patch_pr_branch": pr_branch,
        "patch_pr_title": pr_title,
    }
    result = supabase.table("findings").insert(payload).execute()
    return result.data[0]["id"] if result.data else None


def apply_analysis(
    supabase: Client,
    *,
    oasis_finding_id: str,
    finding_id: str | None,
    repo_row: dict | None,
    repo_name: str,
    pr_number: int,
    analysis: OasisAnalysisResponse,
) -> None:
    supabase.table("oasis_findings").update(
        {
            "status": "analyzed",
            "severity": analysis.severity,
            "file_path": analysis.file_path,
            "line_number": analysis.line_number,
            "title": analysis.title,
            "description": analysis.description,
            "patch_content": analysis.suggested_patch,
        }
    ).eq("id", oasis_finding_id).execute()

    if finding_id:
        supabase.table("findings").update(
            {
                "status": "awaiting_approval",
                "severity": analysis.severity.lower(),
                "title": analysis.title,
                "location": f"{analysis.file_path}:{analysis.line_number}",
                "patch_diff": analysis.suggested_patch,
                "patch_filename": analysis.file_path,
            }
        ).eq("id", finding_id).execute()

    if repo_row:
        supabase.table("activity").insert(
            {
                "owner_id": repo_row["owner_id"],
                "title": f"Security scan completed: {analysis.title}",
                "meta": f"{repo_name} PR #{pr_number}",
                "color": "#fbbf24",
            }
        ).execute()


def mark_failed(supabase: Client, *, oasis_finding_id: str, finding_id: str | None) -> None:
    supabase.table("oasis_findings").update({"status": "failed"}).eq("id", oasis_finding_id).execute()
    if finding_id:
        supabase.table("findings").update({"status": "open"}).eq("id", finding_id).execute()
