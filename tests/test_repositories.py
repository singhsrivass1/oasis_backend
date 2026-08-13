from tests.conftest import USER_A


def test_create_repository(client):
    r = client.post(
        "/api/v1/repositories",
        json={"name": "oasis-backend", "full_name": "ada/oasis-backend", "language": "Python"},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["full_name"] == "ada/oasis-backend"
    assert data["status"] == "reviewing"
    assert data["score"] == 0


def test_create_repository_rejects_bad_full_name(client):
    r = client.post("/api/v1/repositories", json={"name": "x", "full_name": "not-a-valid-name"})
    assert r.status_code == 422


def test_create_repository_duplicate_conflicts(client):
    body = {"name": "x", "full_name": "ada/x"}
    r1 = client.post("/api/v1/repositories", json=body)
    assert r1.status_code == 201
    r2 = client.post("/api/v1/repositories", json=body)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "ALREADY_CONNECTED"


def test_get_repository_detail_not_found(client):
    r = client.get("/api/v1/repositories/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_delete_repository(client, fake_supabase):
    created = client.post(
        "/api/v1/repositories", json={"name": "x", "full_name": "ada/x"}
    ).json()["data"]
    r = client.delete(f"/api/v1/repositories/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/repositories/{created['id']}").status_code == 404


def test_delete_repository_not_owned_returns_404(client, fake_supabase):
    fake_supabase.table("repositories").rows.append(
        {
            "id": "77777777-7777-7777-7777-777777777777",
            "owner_id": "not-ada",
            "name": "x",
            "full_name": "other/x",
            "language": "Python",
            "status": "secure",
            "score": 90,
            "prs_reviewed": 0,
            "issues_open": 0,
            "last_event": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    r = client.delete("/api/v1/repositories/77777777-7777-7777-7777-777777777777")
    assert r.status_code == 404
