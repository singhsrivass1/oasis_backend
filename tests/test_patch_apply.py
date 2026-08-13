from tests.conftest import USER_A


def _seed_repo_and_finding(fake_supabase, *, installation_id=555, patch_pr_branch="feature/x", patch_filename="app.py"):
    fake_supabase.table("repositories").rows.append(
        {
            "id": "55555555-5555-5555-5555-555555555555",
            "owner_id": USER_A,
            "installation_id": installation_id,
            "full_name": "acme/widgets",
            "name": "widgets",
            "language": "Python",
            "status": "reviewing",
            "score": 0,
            "prs_reviewed": 0,
            "issues_open": 0,
        }
    )
    fake_supabase.table("findings").rows.append(
        {
            "id": "66666666-6666-6666-6666-666666666666",
            "owner_id": USER_A,
            "repo_id": "55555555-5555-5555-5555-555555555555",
            "repo_name": "acme/widgets",
            "title": "Hardcoded secret",
            "location": f"{patch_filename}:3",
            "severity": "critical",
            "status": "awaiting_approval",
            "patch_filename": patch_filename,
            "patch_diff": "print('fixed')\n",
            "patch_pr_number": 42,
            "patch_pr_title": "Add feature",
            "patch_pr_branch": patch_pr_branch,
            "created_at": "2026-01-01T00:00:00Z",
            "approved_at": None,
            "dismissed_at": None,
            "resolved_at": None,
        }
    )
    return fake_supabase.table("findings").rows[0]


async def _run_apply(fake_supabase, monkeypatch, *, responses):
    """responses: ordered list of (status_code, json_body) tuples returned
    by successive httpx calls, in the order patch_apply makes them:
    get_ref_sha, create_branch, get_file_sha, commit_file, open_pr.
    get_installation_token is mocked separately.
    """
    import httpx

    from services import patch_apply

    async def fake_get_token(installation_id):
        return "fake-token"

    monkeypatch.setattr(patch_apply.github_app, "get_installation_token", fake_get_token)

    call_log = []

    class FakeResponse:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self._body = body
            self.text = str(body)

        def json(self):
            return self._body

    async def fake_get(self, url, headers=None, params=None):
        call_log.append(("GET", url))
        status_code, body = responses[len(call_log) - 1]
        return FakeResponse(status_code, body)

    async def fake_post(self, url, headers=None, json=None):
        call_log.append(("POST", url))
        status_code, body = responses[len(call_log) - 1]
        return FakeResponse(status_code, body)

    async def fake_put(self, url, headers=None, json=None):
        call_log.append(("PUT", url))
        status_code, body = responses[len(call_log) - 1]
        return FakeResponse(status_code, body)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(httpx.AsyncClient, "put", fake_put)

    finding = fake_supabase.table("findings").rows[0]
    return await patch_apply.apply_patch_and_open_pr(fake_supabase, finding)


async def test_full_success_path_opens_pr(fake_supabase, monkeypatch):
    _seed_repo_and_finding(fake_supabase)

    result = await _run_apply(
        fake_supabase,
        monkeypatch,
        responses=[
            (200, {"object": {"sha": "base-sha"}}),               
            (201, {}),                 
            (404, {}),                            
            (201, {}),               
            (201, {"number": 7, "html_url": "https://github.com/acme/widgets/pull/7"}),           
        ],
    )

    assert result["status"] == "opened"
    assert result["pr_number"] == 7

    finding = fake_supabase.table("findings").rows[0]
    assert finding["fix_status"] == "opened"
    assert finding["fix_pr_number"] == 7
    assert finding["fix_pr_url"] == "https://github.com/acme/widgets/pull/7"
    assert finding["fix_branch"].startswith("oasis/fix-")
    assert finding["fix_error"] is None


async def test_missing_source_branch_fails_gracefully(fake_supabase, monkeypatch):
    _seed_repo_and_finding(fake_supabase, patch_pr_branch="")

    from services import patch_apply

    finding = fake_supabase.table("findings").rows[0]
    result = await patch_apply.apply_patch_and_open_pr(fake_supabase, finding)

    assert result["status"] == "failed"
    assert "branch" in result["error"].lower()
    assert fake_supabase.table("findings").rows[0]["fix_status"] == "failed"


async def test_no_installation_fails_gracefully(fake_supabase, monkeypatch):
    _seed_repo_and_finding(fake_supabase, installation_id=None)

    from services import patch_apply

    finding = fake_supabase.table("findings").rows[0]
    result = await patch_apply.apply_patch_and_open_pr(fake_supabase, finding)

    assert result["status"] == "failed"
    assert "github app" in result["error"].lower()


async def test_branch_creation_conflict_fails_gracefully(fake_supabase, monkeypatch):
    _seed_repo_and_finding(fake_supabase)

    result = await _run_apply(
        fake_supabase,
        monkeypatch,
        responses=[
            (200, {"object": {"sha": "base-sha"}}),               
            (422, {}),                                   
        ],
    )

    assert result["status"] == "failed"
    assert "already exists" in result["error"]
    assert fake_supabase.table("findings").rows[0]["fix_status"] == "failed"


async def test_success_posts_comment_on_original_pr(fake_supabase, monkeypatch):
    from services import patch_apply

    _seed_repo_and_finding(fake_supabase)

    posted = {}

    async def fake_post_comment(repo_name, pr_number, body, installation_id=None):
        posted["repo_name"] = repo_name
        posted["pr_number"] = pr_number
        posted["body"] = body
        posted["installation_id"] = installation_id
        return True

    monkeypatch.setattr(patch_apply.github_service, "post_pr_comment", fake_post_comment)

    result = await _run_apply(
        fake_supabase,
        monkeypatch,
        responses=[
            (200, {"object": {"sha": "base-sha"}}),
            (201, {}),
            (404, {}),
            (201, {}),
            (201, {"number": 7, "html_url": "https://github.com/acme/widgets/pull/7"}),
        ],
    )

    assert result["status"] == "opened"
    assert posted["repo_name"] == "acme/widgets"
    assert posted["pr_number"] == 42                                                               
    assert "PR #7" in posted["body"]
    assert "oasis/fix-" in posted["body"]
    assert "https://github.com/acme/widgets/pull/7" in posted["body"]


async def test_comment_failure_does_not_flip_overall_result(fake_supabase, monkeypatch):
    from services import patch_apply

    _seed_repo_and_finding(fake_supabase)

    async def failing_post_comment(*args, **kwargs):
        raise RuntimeError("GitHub API hiccup")

    monkeypatch.setattr(patch_apply.github_service, "post_pr_comment", failing_post_comment)

    result = await _run_apply(
        fake_supabase,
        monkeypatch,
        responses=[
            (200, {"object": {"sha": "base-sha"}}),
            (201, {}),
            (404, {}),
            (201, {}),
            (201, {"number": 7, "html_url": "https://github.com/acme/widgets/pull/7"}),
        ],
    )

    assert result["status"] == "opened"                                     
    assert fake_supabase.table("findings").rows[0]["fix_status"] == "opened"


def test_approving_a_finding_triggers_fix_pr_end_to_end(client, fake_supabase, monkeypatch):
    import routes.findings as findings_route

    _seed_repo_and_finding(fake_supabase)
    fake_supabase.table("findings").rows[0]["status"] = "awaiting_approval"

    async def fake_apply(supabase, finding):
        supabase.table("findings").update(
            {
                "fix_status": "opened",
                "fix_pr_number": 99,
                "fix_pr_url": "https://github.com/acme/widgets/pull/99",
                "fix_branch": "oasis/fix-abc123",
            }
        ).eq("id", finding["id"]).execute()
        return {"status": "opened", "pr_number": 99}

    monkeypatch.setattr(findings_route.patch_apply, "apply_patch_and_open_pr", fake_apply)

    r = client.patch("/api/v1/findings/66666666-6666-6666-6666-666666666666", json={"status": "approved"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "approved"
    assert data["fix_status"] == "opened"
    assert data["fix_pr_number"] == 99
    assert data["fix_pr_url"] == "https://github.com/acme/widgets/pull/99"


def test_approving_does_not_fail_request_if_fix_pr_fails(client, fake_supabase, monkeypatch):
    import routes.findings as findings_route

    _seed_repo_and_finding(fake_supabase, patch_pr_branch="")
    fake_supabase.table("findings").rows[0]["status"] = "awaiting_approval"

    r = client.patch("/api/v1/findings/66666666-6666-6666-6666-666666666666", json={"status": "approved"})

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "approved"                                   
    assert data["fix_status"] == "failed"
    assert data["fix_error"]
