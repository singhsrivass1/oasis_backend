from tests.conftest import USER_A, USER_B


def test_me_requires_auth(fake_supabase):
    """No dependency override for get_current_user -> must 401, not crash."""
    import main as main_module
    from fastapi.testclient import TestClient
    from services.supabase_client import get_supabase

    main_module.app.dependency_overrides[get_supabase] = lambda: fake_supabase
    try:
        with TestClient(main_module.app) as c:
            r = c.get("/api/v1/me")
            assert r.status_code == 401
            assert r.json()["error"]["code"] == "MISSING_TOKEN"
    finally:
        main_module.app.dependency_overrides.clear()


def test_me_returns_safe_fields_only(client):
    r = client.get("/api/v1/me")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["email"] == "ada@example.com"
    assert "password_hash" not in data


def test_user_a_cannot_see_user_b_repository(client, fake_supabase):
    fake_supabase.table("repositories").rows.append(
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "owner_id": USER_B,
            "name": "secret-repo",
            "full_name": "grace/secret-repo",
            "language": "Python",
            "status": "secure",
            "score": 90,
            "prs_reviewed": 5,
            "issues_open": 0,
            "last_event": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )

    r = client.get("/api/v1/repositories")
    assert r.status_code == 200
    assert r.json()["data"] == []

    r = client.get("/api/v1/repositories/33333333-3333-3333-3333-333333333333")
    assert r.status_code == 404


def test_user_a_cannot_see_user_b_finding(client, fake_supabase):
    fake_supabase.table("findings").rows.append(
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "owner_id": USER_B,
            "repo_id": "33333333-3333-3333-3333-333333333333",
            "repo_name": "grace/secret-repo",
            "title": "Secret",
            "location": "x.py:1",
            "severity": "high",
            "status": "open",
            "patch_filename": "x.py",
            "patch_diff": "",
            "patch_pr_number": 1,
            "patch_pr_title": "",
            "patch_pr_branch": "",
            "created_at": "2026-01-01T00:00:00Z",
            "approved_at": None,
            "dismissed_at": None,
            "resolved_at": None,
        }
    )
    r = client.get("/api/v1/findings")
    assert r.json()["data"] == []
    r = client.get("/api/v1/findings/44444444-4444-4444-4444-444444444444")
    assert r.status_code == 404
