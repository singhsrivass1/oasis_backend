from tests.conftest import USER_A


def _seed_installation(fake_supabase, *, installation_id, owner_id):
    fake_supabase.table("github_installations").rows.append(
        {
            "id": f"inst-{installation_id}",
            "installation_id": installation_id,
            "owner_id": owner_id,
            "account_login": "acme",
            "account_type": "Organization",
        }
    )


def test_installation_created_syncs_repos_when_owner_already_known(client, fake_supabase, monkeypatch):
    import routes.webhook as webhook_route

    _seed_installation(fake_supabase, installation_id=555, owner_id=USER_A)

    async def fake_list_repos(installation_id):
        assert installation_id == 555
        return [
            {"full_name": "acme/one", "name": "one", "language": "Python"},
            {"full_name": "acme/two", "name": "two", "language": None},
        ]

    monkeypatch.setattr(webhook_route.github_app, "list_installation_repositories", fake_list_repos)

    r = client.post(
        "/webhook",
        json={"action": "created", "installation": {"id": 555, "account": {"login": "acme", "type": "Organization"}}},
        headers={"X-GitHub-Event": "installation"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "processed"}

    repo_names = {row["full_name"] for row in fake_supabase.table("repositories").rows}
    assert repo_names == {"acme/one", "acme/two"}
    for row in fake_supabase.table("repositories").rows:
        assert row["owner_id"] == USER_A
        assert row["installation_id"] == 555


def test_installation_created_with_unknown_owner_does_not_sync(client, fake_supabase, monkeypatch):
    import routes.webhook as webhook_route

    called = False

    async def fake_list_repos(installation_id):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(webhook_route.github_app, "list_installation_repositories", fake_list_repos)

    r = client.post(
        "/webhook",
        json={"action": "created", "installation": {"id": 999, "account": {"login": "someone", "type": "User"}}},
        headers={"X-GitHub-Event": "installation"},
    )
    assert r.status_code == 200
    assert not called

    installations = fake_supabase.table("github_installations").rows
    assert len(installations) == 1
    assert installations[0]["owner_id"] is None
    assert fake_supabase.table("repositories").rows == []


def test_installation_deleted_detaches_repos_and_removes_record(client, fake_supabase):
    _seed_installation(fake_supabase, installation_id=555, owner_id=USER_A)
    fake_supabase.table("repositories").rows.append(
        {
            "id": "r1",
            "owner_id": USER_A,
            "installation_id": 555,
            "name": "one",
            "full_name": "acme/one",
            "language": "Python",
            "status": "reviewing",
            "score": 0,
            "prs_reviewed": 0,
            "issues_open": 0,
        }
    )

    r = client.post(
        "/webhook",
        json={"action": "deleted", "installation": {"id": 555, "account": {"login": "acme", "type": "Organization"}}},
        headers={"X-GitHub-Event": "installation"},
    )
    assert r.status_code == 200

    assert fake_supabase.table("repositories").rows[0]["installation_id"] is None
    assert fake_supabase.table("github_installations").rows == []


def test_installation_repositories_added_registers_new_repo(client, fake_supabase):
    _seed_installation(fake_supabase, installation_id=777, owner_id=USER_A)

    r = client.post(
        "/webhook",
        json={
            "installation": {"id": 777},
            "repositories_added": [{"full_name": "acme/three", "name": "three", "language": "Go"}],
            "repositories_removed": [],
        },
        headers={"X-GitHub-Event": "installation_repositories"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "processed"}

    rows = fake_supabase.table("repositories").rows
    assert len(rows) == 1
    assert rows[0]["full_name"] == "acme/three"
    assert rows[0]["owner_id"] == USER_A
    assert rows[0]["installation_id"] == 777


def test_installation_repositories_removed_detaches_repo(client, fake_supabase):
    _seed_installation(fake_supabase, installation_id=777, owner_id=USER_A)
    fake_supabase.table("repositories").rows.append(
        {
            "id": "r1",
            "owner_id": USER_A,
            "installation_id": 777,
            "name": "three",
            "full_name": "acme/three",
            "language": "Go",
            "status": "reviewing",
            "score": 0,
            "prs_reviewed": 0,
            "issues_open": 0,
        }
    )

    r = client.post(
        "/webhook",
        json={
            "installation": {"id": 777},
            "repositories_added": [],
            "repositories_removed": [{"full_name": "acme/three"}],
        },
        headers={"X-GitHub-Event": "installation_repositories"},
    )
    assert r.status_code == 200

    assert fake_supabase.table("repositories").rows[0]["installation_id"] is None


def test_installation_repositories_unresolved_installation_is_ignored(client, fake_supabase):
    r = client.post(
        "/webhook",
        json={
            "installation": {"id": 4242},
            "repositories_added": [{"full_name": "nobody/repo", "name": "repo"}],
            "repositories_removed": [],
        },
        headers={"X-GitHub-Event": "installation_repositories"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}
    assert fake_supabase.table("repositories").rows == []
