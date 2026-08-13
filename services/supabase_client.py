"""Lazily-constructed Supabase client.

Constructing supabase.create_client() at import time (as the original
main.py did) makes the whole app unimportable without real credentials,
which breaks `python -c "import main"` in CI/test environments and forces
every unit test to have live Supabase access. get_supabase() defers
construction until first use and caches the result, and routes depend on
it via FastAPI's dependency injection so tests can override it with a
fake/mock client.
"""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from config import settings


class SupabaseNotConfiguredError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_key:
        raise SupabaseNotConfiguredError(
            "SUPABASE_URL / SUPABASE_KEY are not set. Configure them in .env."
        )
    return create_client(settings.supabase_url, settings.supabase_key)
