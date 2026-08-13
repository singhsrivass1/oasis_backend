from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError

from schemas.webhook import GitHubWebhookPayload
from services import analysis as analysis_service
from services import github as github_service
from services import github_app
from services import webhook as webhook_service
from services.supabase_client import get_supabase

logger = logging.getLogger("oasis.webhook")

router = APIRouter(tags=["webhook"])

SUPPORTED_PR_ACTIONS = {"opened", "synchronize"}


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
    supabase=Depends(get_supabase),
) -> dict:
    raw_payload = await request.body()

    if not webhook_service.verify_signature(raw_payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    json_data = await request.json()

    if x_github_event == "installation":
        return await _handle_installation_event(supabase, json_data)
    if x_github_event == "installation_repositories":
        return await _handle_installation_repositories_event(supabase, json_data)
    if x_github_event == "pull_request":
        return await _handle_pull_request_event(supabase, json_data)

    return {"status": "ignored"}


async def _handle_installation_event(supabase, json_data: dict) -> dict:
    """Fired when a user installs, uninstalls, suspends, or unsuspends the
    App. On "created", GitHub includes the initially-selected repo list --
    used here as a second sync path alongside the /callback route, so the
    installation is correct even if this webhook arrives before (or
    instead of, in an edge case) the browser redirect completes.
    """
    action = json_data.get("action")
    installation = json_data.get("installation", {})
    installation_id = installation.get("id")
    account = installation.get("account", {})

    if installation_id is None:
        return {"status": "ignored"}

    if action in ("created", "unsuspend"):
                                                                        
                                                                        
                                                     
        existing_owner = github_app.get_installation_owner(supabase, installation_id)
        github_app.upsert_installation_record(
            supabase,
            installation_id=installation_id,
            owner_id=existing_owner,
            account_login=account.get("login", ""),
            account_type=account.get("type", "User"),
        )
        if existing_owner:
            await github_app.sync_installation(supabase, owner_id=existing_owner, installation_id=installation_id)
        else:
            logger.info(
                "installation %s created with no resolvable owner yet; "
                "will sync once /callback or a later webhook resolves it.",
                installation_id,
            )
    elif action in ("deleted", "suspend"):
        supabase.table("repositories").update({"installation_id": None}).eq(
            "installation_id", installation_id
        ).execute()
        if action == "deleted":
            supabase.table("github_installations").delete().eq("installation_id", installation_id).execute()

    return {"status": "processed"}


async def _handle_installation_repositories_event(supabase, json_data: dict) -> dict:
    """Fired when repos are added to or removed from an EXISTING
    installation via GitHub's own 'Configure' UI -- this is the actual
    mechanism that makes 'no manual add' true going forward: a user can
    grant Oasis access to a new repo entirely from GitHub's side, and it
    appears in Oasis without ever touching the Oasis UI.
    """
    installation_id = json_data.get("installation", {}).get("id")
    if installation_id is None:
        return {"status": "ignored"}

    owner_id = github_app.get_installation_owner(supabase, installation_id)
    if not owner_id:
        logger.warning("installation_repositories event for unresolved installation_id=%s", installation_id)
        return {"status": "ignored"}

    for repo in json_data.get("repositories_added", []):
        github_app.upsert_repository(supabase, owner_id=owner_id, installation_id=installation_id, gh_repo=repo)

    for repo in json_data.get("repositories_removed", []):
        github_app.detach_repository(supabase, installation_id=installation_id, full_name=repo["full_name"])

    return {"status": "processed"}


async def _handle_pull_request_event(supabase, json_data: dict) -> dict:
    try:
        payload = GitHubWebhookPayload(**json_data)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Malformed webhook payload") from exc

    if payload.action not in SUPPORTED_PR_ACTIONS:
        return {"status": "ignored"}

    repo_name = payload.repository.get("full_name")
    pr_number = payload.number
    author = (payload.pull_request.get("user") or {}).get("login", "unknown")
    patch_url = payload.pull_request.get("patch_url")
    pr_branch = (payload.pull_request.get("head") or {}).get("ref", "")
    pr_title = payload.pull_request.get("title", "")

    if not repo_name or not patch_url:
        raise HTTPException(status_code=422, detail="Malformed webhook payload: missing repository/patch_url")

    repo_row = webhook_service.resolve_repo(supabase, repo_name)
    installation_id = repo_row.get("installation_id") if repo_row else None

    diff_token = None
    if installation_id:
        diff_token = await github_app.get_installation_token(installation_id)

    diff_text = await webhook_service.fetch_patch(patch_url, token=diff_token)
    if not diff_text.strip():
        diff_text = "No trackable code lines modified in this pull request."

    oasis_finding_id = webhook_service.create_pending_record(
        supabase, repo_name=repo_name, repo_row=repo_row, pr_number=pr_number, author=author, diff_text=diff_text
    )
    logger.info("[1/3] Pending oasis_findings row created. id=%s", oasis_finding_id)

    finding_id = None
    if repo_row:
        finding_id = webhook_service.create_pending_finding(
            supabase,
            repo_row=repo_row,
            repo_name=repo_name,
            pr_number=pr_number,
            pr_branch=pr_branch,
            pr_title=pr_title,
            diff_text=diff_text,
        )
    else:
        logger.info("Repo '%s' is not registered with Oasis; skipping findings/activity sync.", repo_name)

    try:
        analysis = analysis_service.analyze_diff(diff_text)

        webhook_service.apply_analysis(
            supabase,
            oasis_finding_id=oasis_finding_id,
            finding_id=finding_id,
            repo_row=repo_row,
            repo_name=repo_name,
            pr_number=pr_number,
            analysis=analysis,
        )
        logger.info("[2/3] Analysis complete and database updated.")

        comment_body = (
            f"## Oasis Automated DevSecOps Audit\n\n"
            f"| Metric | Assessment |\n"
            f"| :--- | :--- |\n"
            f"| **Risk Level** | `{analysis.severity.upper()}` |\n"
            f"| **Target Asset** | `{analysis.file_path}` (Line {analysis.line_number}) |\n\n"
            f"### Threat Intelligence Report\n{analysis.description}\n\n"
            f"### Verified Remediation Patch\n```\n{analysis.suggested_patch}\n```\n\n"
            f"---\n*Analysis generated by Oasis Infrastructure Engine*"
        )
        posted = await github_service.post_pr_comment(
            repo_name, pr_number, comment_body, installation_id=installation_id
        )
        logger.info("[3/3] PR comment posted: %s", posted)

    except Exception:
        webhook_service.mark_failed(supabase, oasis_finding_id=oasis_finding_id, finding_id=finding_id)
        logger.exception("Analysis pipeline failed for oasis_findings id=%s", oasis_finding_id)
        raise HTTPException(status_code=500, detail="Internal AI Processing Pipeline Failure")

    return {"status": "processing_complete", "finding_id": oasis_finding_id}
