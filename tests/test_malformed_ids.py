def test_malformed_finding_id_returns_404_not_500(client):
    r = client.get("/api/v1/findings/not-a-real-uuid")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_malformed_repository_id_returns_404_not_500(client):
    r = client.get("/api/v1/repositories/not-a-real-uuid")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_malformed_review_id_returns_404_not_500(client):
    r = client.get("/api/v1/reviews/not-a-real-uuid")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_well_formed_but_missing_uuid_still_returns_404(client):
    r = client.get("/api/v1/findings/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
