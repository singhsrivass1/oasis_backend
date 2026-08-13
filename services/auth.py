"""Authentication for the /api/v1 dashboard API.

IMPORTANT / DOCUMENTED LIMITATION
----------------------------------
The original backend (main.py) implemented NO authentication whatsoever
for anything other than the GitHub webhook's HMAC signature. There is no
login route, no session cookie, no JWT issuance, and no existing
dependency anywhere in the codebase that resolves "the current user".

Per the task brief: "If authentication is not currently implemented in
the backend, do not invent an insecure authentication mechanism... If the
existing application relies on Supabase Auth, use the authenticated
Supabase user/session context."

This project's `public.users` table (password_hash, google_id, github_id,
auth_provider) strongly suggests Supabase Auth is the intended identity
provider, with `public.users.id` mirroring `auth.users.id` -- this is the
standard Supabase pattern (a DB trigger copies new `auth.users` rows into
a public profile table). `oasis_findings.owner_id` even has an explicit
FK to `auth.users(id)`, which only makes sense under that assumption.

So: this dependency expects an `Authorization: Bearer <supabase_jwt>`
header, verifies it via Supabase Auth (`supabase.auth.get_user(token)`),
and then loads the matching `public.users` row by that same id.

WHAT IS NOT VERIFIED (could not be tested without a live Supabase
project + a real signed-up user in this environment):
  - That a DB trigger actually keeps public.users.id in sync with
    auth.users.id in this specific project.
  - That RLS policies on `users`/`repositories`/`findings`/`activity`
    exist and are correct (see services/supabase_client.py docstring and
    the final report's Security section).

If `public.users` turns out NOT to mirror `auth.users` in this project,
the fix is localized to `_load_profile()` below.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException
from supabase import Client

from services.supabase_client import get_supabase


@dataclass
class CurrentUser:
    id: str
    email: str | None
    profile: dict                        


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "MISSING_TOKEN", "message": "Authorization: Bearer <token> header is required."},
        )
    return authorization.split(" ", 1)[1].strip()


def _load_profile(supabase: Client, auth_user_id: str) -> dict:
    result = (
        supabase.table("users")
        .select("*")
        .eq("id", auth_user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PROFILE_NOT_FOUND",
                "message": (
                    "Authenticated with Supabase but no matching public.users row exists. "
                    "This backend assumes public.users.id mirrors auth.users.id; verify the "
                    "signup trigger is configured."
                ),
            },
        )
    return result.data[0]


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """FastAPI dependency: resolves the authenticated user from a Supabase JWT.

    Overridden in tests via app.dependency_overrides[get_current_user].
    """
    token = _extract_bearer_token(authorization)
    supabase = get_supabase()

    try:
        auth_response = supabase.auth.get_user(token)
    except Exception as exc:                                                      
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Could not validate Supabase session token."},
        ) from exc

    auth_user = getattr(auth_response, "user", None)
    if auth_user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Could not validate Supabase session token."},
        )

    profile = _load_profile(supabase, auth_user.id)
    return CurrentUser(id=auth_user.id, email=getattr(auth_user, "email", None), profile=profile)
