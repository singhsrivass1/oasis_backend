"""Automated remediation: turns an approved finding's suggested_patch into
a real, reviewable pull request on the user's repo.

Design decisions (confirmed with the product owner before building):
  - Opens a NEW pull request containing only the fix -- never pushes
    directly to an existing branch. Same pattern as Dependabot/Renovate.
  - Triggered automatically the instant a finding transitions to
    "approved" (see routes/findings.py) -- not a separate manual step.
  - The fix branch is created off the ORIGINAL PR's head branch (not the
    repo's default branch), so the file content Oasis is patching against
    actually matches what's in the PR. This is why services/webhook.py
    was updated to actually capture patch_pr_branch, which previously
    existed as a column but was never populated.
  - A failure here (bad permissions, branch already exists, file changed
    since analysis, etc.) never blocks the approval itself -- the finding
    still moves to "approved", the failure is recorded on the finding
    (fix_status/fix_error) and surfaced to the frontend, not swallowed.
  - On success, a comment is posted back on the ORIGINAL pull request
    (patch_pr_number) pointing at the new fix branch/PR, so nobody has to
    go hunting for it -- see _comment_on_original_pr below.

Requires the GitHub App to have Contents: Read & write and
Pull requests: Read & write (both were Read-only when the App was first
registered -- see the README note this ships with).
"""
from __future__ import annotations

import base64
import logging

import httpx
from supabase import Client

from services import github as github_service
from services import github_app

logger = logging.getLogger("oasis.patch_apply")

GITHUB_API = github_app.GITHUB_API


class PatchApplyError(Exception):
    pass


async def _get_ref_sha(client: httpx.AsyncClient, headers: dict, repo_full_name: str, branch: str) -> str:
    resp = await client.get(f"{GITHUB_API}/repos/{repo_full_name}/git/ref/heads/{branch}", headers=headers)
    if resp.status_code != 200:
        raise PatchApplyError(f"Could not read branch '{branch}' (status {resp.status_code}).")
    return resp.json()["object"]["sha"]


async def _create_branch(
    client: httpx.AsyncClient, headers: dict, repo_full_name: str, new_branch: str, base_sha: str
) -> None:
    resp = await client.post(
        f"{GITHUB_API}/repos/{repo_full_name}/git/refs",
        headers=headers,
        json={"ref": f"refs/heads/{new_branch}", "sha": base_sha},
    )
    if resp.status_code == 422:
        raise PatchApplyError(f"Branch '{new_branch}' already exists.")
    if resp.status_code != 201:
        raise PatchApplyError(f"Could not create branch '{new_branch}' (status {resp.status_code}).")


async def _get_file_sha(
    client: httpx.AsyncClient, headers: dict, repo_full_name: str, path: str, branch: str
) -> str | None:
    resp = await client.get(
        f"{GITHUB_API}/repos/{repo_full_name}/contents/{path}", headers=headers, params={"ref": branch}
    )
    if resp.status_code == 200:
        return resp.json()["sha"]
    if resp.status_code == 404:
        return None                                                                
    raise PatchApplyError(f"Could not read file '{path}' (status {resp.status_code}).")


async def _commit_file(
    client: httpx.AsyncClient,
    headers: dict,
    repo_full_name: str,
    path: str,
    content: str,
    branch: str,
    message: str,
    existing_sha: str | None,
) -> None:
    body = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if existing_sha:
        body["sha"] = existing_sha
    resp = await client.put(f"{GITHUB_API}/repos/{repo_full_name}/contents/{path}", headers=headers, json=body)
    if resp.status_code not in (200, 201):
        raise PatchApplyError(f"Could not commit '{path}' (status {resp.status_code}): {resp.text[:300]}")


async def _open_pull_request(
    client: httpx.AsyncClient, headers: dict, repo_full_name: str, head: str, base: str, title: str, body: str
) -> dict:
    resp = await client.post(
        f"{GITHUB_API}/repos/{repo_full_name}/pulls",
        headers=headers,
        json={"title": title, "head": head, "base": base, "body": body},
    )
    if resp.status_code != 201:
        raise PatchApplyError(f"Could not open pull request (status {resp.status_code}): {resp.text[:300]}")
    return resp.json()


async def apply_patch_and_open_pr(supabase: Client, finding: dict) -> dict:
    """Orchestrates the whole flow. Always returns a dict describing the
    outcome; never raises -- callers should check result["status"].
    Also persists the outcome onto the finding row (fix_status, fix_error,
    fix_pr_number, fix_pr_url, fix_branch) so it survives a page refresh.
    """
    finding_id = finding["id"]
    repo_name = finding.get("repo_name")
    base_branch = finding.get("patch_pr_branch") or ""
    file_path = finding.get("patch_filename") or ""
    patch_content = finding.get("patch_diff") or ""
    title = finding.get("title") or "Security finding"

    def _fail(message: str) -> dict:
        logger.warning("Patch apply failed for finding %s: %s", finding_id, message)
        supabase.table("findings").update({"fix_status": "failed", "fix_error": message}).eq(
            "id", finding_id
        ).execute()
        return {"status": "failed", "error": message}

    if not base_branch:
        return _fail("Source PR branch is unknown for this finding; cannot safely apply the patch.")
    if not file_path:
        return _fail("No target file path recorded for this finding.")
    if not patch_content:
        return _fail("No suggested patch content available for this finding.")

    repo_result = (
        supabase.table("repositories").select("installation_id").eq("id", finding["repo_id"]).limit(1).execute()
    )
    installation_id = repo_result.data[0]["installation_id"] if repo_result.data else None
    if not installation_id:
        return _fail("This repository isn't connected via the Oasis GitHub App; cannot open a fix PR automatically.")

    supabase.table("findings").update({"fix_status": "opening"}).eq("id", finding_id).execute()

    try:
        token = await github_app.get_installation_token(installation_id)
    except Exception as exc:
        return _fail(f"Could not authenticate with GitHub: {exc}")

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    new_branch = f"oasis/fix-{finding_id[:8]}"

    try:
        async with httpx.AsyncClient() as client:
            base_sha = await _get_ref_sha(client, headers, repo_name, base_branch)
            await _create_branch(client, headers, repo_name, new_branch, base_sha)
            existing_sha = await _get_file_sha(client, headers, repo_name, file_path, new_branch)
            await _commit_file(
                client,
                headers,
                repo_name,
                file_path,
                patch_content,
                new_branch,
                message=f"Oasis: fix {title}",
                existing_sha=existing_sha,
            )
            pr = await _open_pull_request(
                client,
                headers,
                repo_name,
                head=new_branch,
                base=base_branch,
                title=f"Oasis fix: {title}",
                body=(
                    f"Automated remediation opened by Oasis for a security finding "
                    f"({finding.get('severity', 'unknown')} severity) in `{file_path}`.\n\n"
                    f"This PR was generated automatically after the finding was approved in Oasis. "
                    f"Please review the change before merging -- Oasis does not merge PRs itself."
                ),
            )
    except PatchApplyError as exc:
        return _fail(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error applying patch for finding %s", finding_id)
        return _fail(f"Unexpected error: {exc}")

    supabase.table("findings").update(
        {
            "fix_status": "opened",
            "fix_error": None,
            "fix_pr_number": pr["number"],
            "fix_pr_url": pr["html_url"],
            "fix_branch": new_branch,
        }
    ).eq("id", finding_id).execute()

    logger.info("Fix PR #%s opened for finding %s: %s", pr["number"], finding_id, pr["html_url"])

    original_pr_number = finding.get("patch_pr_number")
    if original_pr_number:
        comment_body = (
            f"### 🛠️ Oasis Automated Fix\n\n"
            f"A fix for this finding has been opened as **PR #{pr['number']}**, "
            f"on branch `{new_branch}`.\n\n"
            f"{pr['html_url']}\n\n"
            f"Oasis does not merge this automatically -- please review before merging."
        )
        try:
            await github_service.post_pr_comment(
                repo_name, original_pr_number, comment_body, installation_id=installation_id
            )
        except Exception:
                                                                            
                                                                          
                                         
            logger.exception(
                "Fix PR #%s opened successfully, but posting a comment on the original PR #%s failed.",
                pr["number"],
                original_pr_number,
            )

    return {"status": "opened", "pr_number": pr["number"], "pr_url": pr["html_url"]}