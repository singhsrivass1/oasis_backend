"""GitHub App authentication and installation management.

Three layers of GitHub API auth exist here, easy to mix up:
  1. App JWT       -- proves "I am the Oasis App itself", signed with the
                       App's private key (RS256), lives ~10 min. Only used
                       to mint installation tokens; never used to call the
                       API directly for repo data.
  2. Installation
     access token   -- proves "I am acting on behalf of installation X",
                       minted using the App JWT, lives ~1 hour. This is
                       what actually lists repos / posts comments / fetches
                       diffs for that installation's repos.
  3. Legacy
     GITHUB_TOKEN   -- a static personal token, kept only as a fallback for
                       repos connected before the App existed (see
                       services/github.py::post_pr_comment).

This module owns layers 1 and 2. Nothing outside this file should
construct a GitHub App JWT or call /app/installations/*/access_tokens
directly.
"""
from __future__ import annotations

import time

import httpx
import jwt
from fastapi import HTTPException
from supabase import Client

from config import settings

GITHUB_API = "https://api.github.com"


class GitHubAppNotConfiguredError(RuntimeError):
    pass


def _require_configured() -> None:
    if not settings.github_app_configured:
        raise GitHubAppNotConfiguredError(
            "GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY are not set. "
            "Register a GitHub App and configure these before using GitHub App features."
        )


def _private_key() -> str:
                                                                     
                                 
    return (settings.github_app_private_key or "").replace("\\n", "\n")


def build_app_jwt() -> str:
    """A ~10-minute JWT identifying the App itself, per GitHub's App auth spec."""
    _require_configured()
    now = int(time.time())
    payload = {
        "iat": now - 60,                         
        "exp": now + 600,
        "iss": settings.github_app_id,
    }
    return jwt.encode(payload, _private_key(), algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    """Mints a fresh, short-lived token scoped to one installation.

    Not cached across requests -- installation tokens are cheap to mint
    (no rate-limit concern at Oasis's current scale) and correctness here
    matters more than shaving one HTTP call.
    """
    app_jwt = build_app_jwt()
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers=headers,
        )
    if response.status_code != 201:
        raise HTTPException(
            status_code=502,
            detail=f"Could not obtain a GitHub installation token (status {response.status_code}).",
        )
    return response.json()["token"]


def build_install_url(state: str) -> str:
    _require_configured()
    if not settings.github_app_slug:
        raise GitHubAppNotConfiguredError("GITHUB_APP_SLUG is not set.")
    return f"https://github.com/apps/{settings.github_app_slug}/installations/new?state={state}"


async def list_installation_repositories(installation_id: int) -> list[dict]:
    """Every repo this installation currently has access to, per GitHub's
    /installation/repositories endpoint (paginated; Oasis installs are not
    expected to exceed a few hundred repos, so pagination is handled but
    not heavily optimized)."""
    token = await get_installation_token(installation_id)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repos: list[dict] = []
    url = f"{GITHUB_API}/installation/repositories?per_page=100"
    async with httpx.AsyncClient() as client:
        while url:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not list installation repositories (status {response.status_code}).",
                )
            data = response.json()
            repos.extend(data.get("repositories", []))
            url = response.links.get("next", {}).get("url")
    return repos


def upsert_repository(supabase: Client, *, owner_id: str, installation_id: int, gh_repo: dict) -> None:
    """Inserts a repository if Oasis doesn't already have it for this
    owner; otherwise just attaches the installation_id so it's known to be
    GitHub-App-managed (covers the case where it was previously added
    manually). Never overwrites status/score/prs_reviewed -- those are
    Oasis-owned fields, not GitHub's to set.
    """
    full_name = gh_repo["full_name"]
    existing = (
        supabase.table("repositories")
        .select("id")
        .eq("owner_id", owner_id)
        .eq("full_name", full_name)
        .limit(1)
        .execute()
    )
    if existing.data:
        supabase.table("repositories").update({"installation_id": installation_id}).eq(
            "id", existing.data[0]["id"]
        ).execute()
        return

    supabase.table("repositories").insert(
        {
            "owner_id": owner_id,
            "installation_id": installation_id,
            "name": gh_repo.get("name", full_name.split("/")[-1]),
            "full_name": full_name,
            "language": gh_repo.get("language") or "Unknown",
            "status": "reviewing",
            "score": 0,
            "prs_reviewed": 0,
            "issues_open": 0,
        }
    ).execute()


def detach_repository(supabase: Client, *, installation_id: int, full_name: str) -> None:
    """Repo removed from the installation (uninstalled or deselected).
    Clears installation_id rather than deleting the row -- findings/activity
    history is preserved, same policy as manual repository deletion."""
    supabase.table("repositories").update({"installation_id": None}).eq(
        "installation_id", installation_id
    ).eq("full_name", full_name).execute()


async def sync_installation(supabase: Client, *, owner_id: str, installation_id: int) -> int:
    """Fetches the installation's current repo list from GitHub and
    upserts all of them. Returns the count synced. This is the function
    both the callback route and the `installation` webhook event call --
    single source of truth for "what does this installation have access to
    right now"."""
    repos = await list_installation_repositories(installation_id)
    for repo in repos:
        upsert_repository(supabase, owner_id=owner_id, installation_id=installation_id, gh_repo=repo)
    return len(repos)


def upsert_installation_record(
    supabase: Client, *, installation_id: int, owner_id: str | None, account_login: str, account_type: str
) -> dict:
    existing = (
        supabase.table("github_installations")
        .select("*")
        .eq("installation_id", installation_id)
        .limit(1)
        .execute()
    )
    payload = {
        "installation_id": installation_id,
        "account_login": account_login,
        "account_type": account_type,
    }
    if owner_id:
        payload["owner_id"] = owner_id

    if existing.data:
        result = (
            supabase.table("github_installations")
            .update(payload)
            .eq("installation_id", installation_id)
            .execute()
        )
        return result.data[0]

                                                                       
                                                                     
                                                               
    payload.setdefault("owner_id", None)
    result = supabase.table("github_installations").insert(payload).execute()
    return result.data[0]


def get_installation_owner(supabase: Client, installation_id: int) -> str | None:
    result = (
        supabase.table("github_installations")
        .select("owner_id")
        .eq("installation_id", installation_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0].get("owner_id")
    return None


def get_owner_installation(supabase: Client, owner_id: str) -> dict | None:
    result = (
        supabase.table("github_installations")
        .select("*")
        .eq("owner_id", owner_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
