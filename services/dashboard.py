from __future__ import annotations

from supabase import Client

RECENT_ACTIVITY_LIMIT = 10


def build_dashboard(supabase: Client, owner_id: str) -> dict:
    repos_result = supabase.table("repositories").select("*").eq("owner_id", owner_id).execute()
    repositories = repos_result.data or []

    protected_repositories = len(repositories)

                                                                            
                                                                          
                                                            
    security_score = (
        round(sum(r["score"] for r in repositories) / protected_repositories, 1)
        if protected_repositories
        else None
    )

    open_issues_result = (
        supabase.table("findings")
        .select("id", count="exact")
        .eq("owner_id", owner_id)
        .in_("status", ["open", "awaiting_approval"])
        .execute()
    )
    open_issues = open_issues_result.count or 0

    prs_reviewed = sum(r.get("prs_reviewed", 0) or 0 for r in repositories)

    attention_required = [r for r in repositories if r.get("status") == "attention"]

    recent_activity_result = (
        supabase.table("activity")
        .select("*")
        .eq("owner_id", owner_id)
        .order("created_at", desc=True)
        .limit(RECENT_ACTIVITY_LIMIT)
        .execute()
    )

    return {
        "metrics": {
            "protected_repositories": protected_repositories,
            "security_score": security_score,
            "open_issues": open_issues,
            "prs_reviewed": prs_reviewed,
        },
        "repositories": repositories,
        "attention_required": attention_required,
        "recent_activity": recent_activity_result.data or [],
    }
