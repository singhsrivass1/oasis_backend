from __future__ import annotations

from supabase import Client


def list_activity(supabase: Client, owner_id: str, *, page: int, limit: int) -> tuple[list[dict], int]:
    start = (page - 1) * limit
    end = start + limit - 1
    result = (
        supabase.table("activity")
        .select("*", count="exact")
        .eq("owner_id", owner_id)
        .order("created_at", desc=True)
        .range(start, end)
        .execute()
    )
    total = result.count if result.count is not None else len(result.data or [])
    return result.data or [], total
