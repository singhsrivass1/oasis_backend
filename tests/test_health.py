def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "Oasis Backend Online"


def test_health_reports_honest_unconfigured_state(client, monkeypatch):
    """/health's database check calls the REAL get_supabase() (not the
    fake_supabase override) so it reflects actual configured-ness rather
    than test wiring. Force the "no credentials" case explicitly here
    (via monkeypatch) instead of relying on the ambient .env being empty
    -- a real .env with real Supabase credentials, like a developer would
    have locally, should not make this test fail. It must degrade
    gracefully, not crash or lie, when nothing is configured."""
    import routes.health as health_route

    monkeypatch.setattr(health_route.settings, "supabase_url", None)
    monkeypatch.setattr(health_route.settings, "supabase_key", None)
    monkeypatch.setattr(health_route.settings, "gemini_api_key", None)

    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "oasis-backend"
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "not configured"
    assert body["checks"]["gemini_configured"] is False


def test_health_reports_connected_when_db_reachable(client, monkeypatch, fake_supabase):
    import routes.health as health_route

    monkeypatch.setattr(health_route.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(health_route.settings, "supabase_key", "fake-key")
    monkeypatch.setattr(health_route, "get_supabase", lambda: fake_supabase)

    r = client.get("/health")
    body = r.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"] == "connected"