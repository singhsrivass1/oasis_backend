from tests.conftest import USER_A


def test_connect_returns_install_url(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "github_app_id", "12345")
    monkeypatch.setattr(settings, "github_app_private_key", "fake-key")
    monkeypatch.setattr(settings, "github_app_slug", "oasis-devsecops")
    monkeypatch.setattr(settings, "oasis_state_secret", "test-secret")

    r = client.get("/api/v1/github/connect")
    assert r.status_code == 200
    install_url = r.json()["data"]["install_url"]
    assert install_url.startswith("https://github.com/apps/oasis-devsecops/installations/new?state=")


def test_connect_without_app_configured_returns_503(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "github_app_id", None)
    monkeypatch.setattr(settings, "github_app_private_key", None)

    r = client.get("/api/v1/github/connect")
    assert r.status_code == 503


def test_callback_with_invalid_state_redirects_to_error(client):
    r = client.get(
        "/api/v1/github/callback",
        params={"installation_id": 555, "state": "garbage", "setup_action": "install"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 307)
    assert "github=error" in r.headers["location"]


def test_callback_with_valid_state_syncs_and_redirects_to_success(client, fake_supabase, monkeypatch):
    import httpx

    import routes.github as github_route
    from config import settings
    from services import state_token

    monkeypatch.setattr(settings, "oasis_state_secret", "test-secret")
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:5000")

    async def fake_get_installation_token(installation_id):
        return "fake-installation-token"

    async def fake_sync_installation(supabase, *, owner_id, installation_id):
        fake_supabase.table("repositories").insert(
            {
                "owner_id": owner_id,
                "installation_id": installation_id,
                "name": "synced-repo",
                "full_name": "acme/synced-repo",
                "language": "Python",
                "status": "reviewing",
                "score": 0,
                "prs_reviewed": 0,
                "issues_open": 0,
            }
        ).execute()
        return 1

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"account": {"login": "acme", "type": "Organization"}}

    async def fake_get(self, url, headers=None):
        return FakeResponse()

    monkeypatch.setattr(github_route.github_app, "get_installation_token", fake_get_installation_token)
    monkeypatch.setattr(github_route.github_app, "sync_installation", fake_sync_installation)
    monkeypatch.setattr(github_route.github_app, "build_app_jwt", lambda: "fake-app-jwt")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    state = state_token.sign_state(USER_A)
    r = client.get(
        "/api/v1/github/callback",
        params={"installation_id": 555, "state": state, "setup_action": "install"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 307)
    assert "github=connected" in r.headers["location"]

    installations = fake_supabase.table("github_installations").rows
    assert len(installations) == 1
    assert installations[0]["owner_id"] == USER_A
    assert installations[0]["account_login"] == "acme"

    repo_names = {row["full_name"] for row in fake_supabase.table("repositories").rows}
    assert "acme/synced-repo" in repo_names


def test_status_reflects_real_installation(client, fake_supabase):
    r = client.get("/api/v1/github/status")
    assert r.json()["data"] == {"connected": False, "username": None}

    fake_supabase.table("github_installations").rows.append(
        {
            "id": "inst-1",
            "installation_id": 555,
            "owner_id": USER_A,
            "account_login": "acme",
            "account_type": "Organization",
        }
    )
    r = client.get("/api/v1/github/status")
    assert r.json()["data"] == {"connected": True, "username": "acme"}
