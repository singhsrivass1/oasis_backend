import hashlib
import hmac
import json

import pytest

from schemas.webhook import OasisAnalysisResponse

PR_PAYLOAD = {
    "action": "opened",
    "number": 184,
    "repository": {"full_name": "ada/oasis-backend"},
    "pull_request": {
        "user": {"login": "ada"},
        "patch_url": "https://github.com/ada/oasis-backend/pull/184.patch",
        "head": {"ref": "feature/fix-login"},
        "title": "Fix login bug",
    },
}


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_ignores_non_pull_request_event(client):
    r = client.post("/webhook", json=PR_PAYLOAD, headers={"X-GitHub-Event": "push"})
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}


def test_webhook_ignores_unsupported_action(client):
    payload = {**PR_PAYLOAD, "action": "closed"}
    r = client.post("/webhook", json=payload, headers={"X-GitHub-Event": "pull_request"})
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}


def test_webhook_malformed_payload_rejected(client):
    r = client.post("/webhook", json={"not": "a valid payload"}, headers={"X-GitHub-Event": "pull_request"})
    assert r.status_code == 422


def test_webhook_invalid_signature_rejected(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "github_webhook_secret", "test-secret")
    body = json.dumps(PR_PAYLOAD).encode()
    r = client.post(
        "/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401


def test_webhook_valid_signature_accepted_and_full_pipeline_runs(client, monkeypatch, fake_supabase):
    from config import settings
    import routes.webhook as webhook_route

    monkeypatch.setattr(settings, "github_webhook_secret", "test-secret")

    async def fake_fetch_patch(url, token=None):
        return "diff --git a/main.py b/main.py\n+os.system(user_input)"

    def fake_analyze(diff_text):
        return OasisAnalysisResponse(
            severity="high",
            file_path="main.py",
            line_number=42,
            title="Command injection via os.system",
            description="User input flows into os.system unsanitized.",
            suggested_patch="subprocess.run([...], check=True)",
        )

    async def fake_post_comment(repo_name, pr_number, body, installation_id=None):
        return True

    monkeypatch.setattr(webhook_route.webhook_service, "fetch_patch", fake_fetch_patch)
    monkeypatch.setattr(webhook_route.analysis_service, "analyze_diff", fake_analyze)
    monkeypatch.setattr(webhook_route.github_service, "post_pr_comment", fake_post_comment)

                                                                            
    fake_supabase.table("repositories").rows.append(
        {
            "id": "repo-1",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "full_name": "ada/oasis-backend",
            "name": "oasis-backend",
            "language": "Python",
            "status": "secure",
            "score": 90,
            "prs_reviewed": 0,
            "issues_open": 0,
        }
    )

    body = json.dumps(PR_PAYLOAD).encode()
    r = client.post(
        "/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign("test-secret", body),
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "processing_complete"

    oasis_rows = fake_supabase.table("oasis_findings").rows
    assert len(oasis_rows) == 1
    assert oasis_rows[0]["status"] == "analyzed"
    assert oasis_rows[0]["severity"] == "high"

    finding_rows = fake_supabase.table("findings").rows
    assert len(finding_rows) == 1
    assert finding_rows[0]["status"] == "awaiting_approval"
    assert finding_rows[0]["patch_pr_branch"] == "feature/fix-login"
    assert finding_rows[0]["patch_pr_title"] == "Fix login bug"

    activity_rows = fake_supabase.table("activity").rows
    assert len(activity_rows) == 1


def test_webhook_analysis_failure_marks_record_failed(client, monkeypatch, fake_supabase):
    import routes.webhook as webhook_route

    async def fake_fetch_patch(url, token=None):
        return "some diff"

    def fake_analyze_raises(diff_text):
        raise RuntimeError("Gemini API error")

    monkeypatch.setattr(webhook_route.webhook_service, "fetch_patch", fake_fetch_patch)
    monkeypatch.setattr(webhook_route.analysis_service, "analyze_diff", fake_analyze_raises)

    r = client.post("/webhook", json=PR_PAYLOAD, headers={"X-GitHub-Event": "pull_request"})
    assert r.status_code == 500

    oasis_rows = fake_supabase.table("oasis_findings").rows
    assert len(oasis_rows) == 1
    assert oasis_rows[0]["status"] == "failed"
