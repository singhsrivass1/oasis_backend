from __future__ import annotations

from fastapi import HTTPException
from supabase import Client

from services.validators import require_valid_uuid


def _attach_authors(supabase: Client, owner_id: str, findings: list[dict]) -> list[dict]:
    """Best-effort join against oasis_findings to recover pr_author, since
    `findings` has no author column. Matches on (repo_name, pr_number).
    See schemas/review.py docstring for why `author` may still be None.
    """
    pr_numbers = [f["patch_pr_number"] for f in findings if f.get("patch_pr_number") is not None]
    if not pr_numbers:
        return findings

    oasis_rows = (
        supabase.table("oasis_findings")
        .select("repo_name, pr_number, pr_author")
        .eq("owner_id", owner_id)
        .in_("pr_number", pr_numbers)
        .execute()
    )
    author_by_key = {
        (row["repo_name"], row["pr_number"]): row.get("pr_author") for row in (oasis_rows.data or [])
    }

    for f in findings:
        key = (f.get("repo_name"), f.get("patch_pr_number"))
        f["_author"] = author_by_key.get(key)
    return findings


def list_reviews(supabase: Client, owner_id: str, *, page: int, limit: int) -> tuple[list[dict], int]:
    start = (page - 1) * limit
    end = start + limit - 1
    result = (
        supabase.table("findings")
        .select("*", count="exact")
        .eq("owner_id", owner_id)
        .order("created_at", desc=True)
        .range(start, end)
        .execute()
    )
    findings = _attach_authors(supabase, owner_id, result.data or [])
    total = result.count if result.count is not None else len(findings)
    return findings, total


def get_review_or_404(supabase: Client, owner_id: str, review_id: str) -> dict:
    require_valid_uuid(review_id, not_found_message="Review not found.")
    result = (
        supabase.table("findings")
        .select("*")
        .eq("id", review_id)
        .eq("owner_id", owner_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Review not found."})
    return _attach_authors(supabase, owner_id, result.data)[0]


def to_review_item(finding: dict) -> dict:
    return {
        "id": finding["id"],
        "repository": finding.get("repo_name"),
        "pr_number": finding.get("patch_pr_number"),
        "pr_title": finding.get("patch_pr_title") or "",
        "pr_branch": finding.get("patch_pr_branch") or "",
        "author": finding.get("_author"),
        "status": finding.get("status"),
        "severity": finding.get("severity"),
        "created_at": finding.get("created_at"),
    }