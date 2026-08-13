from __future__ import annotations

import httpx
from supabase import Client

from config import settings
from services import github_app


def get_status(supabase: Client, owner_id: str) -> dict:
    """Connected means "has an active GitHub App installation on file",
    not just "has a github_username string somewhere" -- this now reflects
    a real, revocable connection (services/github_app.py's
    github_installations table), not a cosmetic profile field.
    """
    installation = github_app.get_owner_installation(supabase, owner_id)
    if not installation:
        return {"connected": False, "username": None}
    return {"connected": True, "username": installation.get("account_login")}


async def discover_repositories(supabase: Client, owner_id: str) -> dict:
    """Real repository discovery, via the user's GitHub App installation.

    Replaces the old permanently-unsupported stub -- this now actually
    calls the GitHub API (through services/github_app.py) and returns the
    live list of repos the installation has access to, when one exists.
    """
    installation = github_app.get_owner_installation(supabase, owner_id)
    if not installation or not installation.get("owner_id"):
        return {
            "supported": False,
            "repositories": [],
            "message": (
                "No GitHub App installation connected yet. "
                "Use GET /api/v1/github/connect to start the connect flow."
            ),
        }

    repos = await github_app.list_installation_repositories(installation["installation_id"])
    return {
        "supported": True,
        "repositories": [
            {"full_name": r["full_name"], "name": r["name"], "private": r.get("private", False)}
            for r in repos
        ],
        "message": "Repositories available through your connected GitHub App installation.",
    }


async def post_pr_comment(
    repo_name: str, pr_number: int, body: str, *, installation_id: int | None = None
) -> bool:
    """Posts the audit/remediation comment to the PR.

    Prefers a short-lived GitHub App installation token (works for any
    user's repos, least-privilege, auto-expires) over the legacy static
    GITHUB_TOKEN, which is now only a fallback for repos connected before
    the App existed.
    """
    if installation_id is not None:
        token = await github_app.get_installation_token(installation_id)
        auth_header = f"token {token}"
    elif settings.github_token:
        auth_header = f"Bearer {settings.github_token}"
    else:
        return False

    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"body": body})
    return response.status_code == 201
