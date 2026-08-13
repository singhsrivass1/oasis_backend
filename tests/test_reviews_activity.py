from tests.conftest import USER_A


def test_activity_scoped_to_owner(client, fake_supabase):
    fake_supabase.table("activity").rows.append(
        {"id": "a1", "owner_id": USER_A, "title": "Scan done", "meta": "ada/x PR #1", "color": "#fbbf24", "created_at": "2026-01-01T00:00:00Z"}
    )
    fake_supabase.table("activity").rows.append(
        {"id": "a2", "owner_id": "someone-else", "title": "Nope", "meta": "", "color": "#fff", "created_at": "2026-01-01T00:00:00Z"}
    )
    r = client.get("/api/v1/activity")
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()["data"]]
    assert ids == ["a1"]


def test_reviews_derived_from_findings_with_author_join(client, fake_supabase):
    fake_supabase.table("findings").rows.append(
        {
            "id": "88888888-8888-8888-8888-888888888888",
            "owner_id": USER_A,
            "repo_id": "r1",
            "repo_name": "ada/oasis-backend",
            "title": "SQL injection",
            "location": "db.py:10",
            "severity": "critical",
            "status": "awaiting_approval",
            "patch_filename": "db.py",
            "patch_diff": "",
            "patch_pr_number": 184,
            "patch_pr_title": "Fix login",
            "patch_pr_branch": "fix/login",
            "created_at": "2026-01-01T00:00:00Z",
            "approved_at": None,
            "dismissed_at": None,
            "resolved_at": None,
        }
    )
    fake_supabase.table("oasis_findings").rows.append(
        {
            "id": "of1",
            "owner_id": USER_A,
            "repo_name": "ada/oasis-backend",
            "pr_number": 184,
            "pr_author": "ada",
            "status": "analyzed",
        }
    )

    r = client.get("/api/v1/reviews")
    assert r.status_code == 200
    review = r.json()["data"][0]
    assert review["author"] == "ada"
    assert review["pr_number"] == 184

    r2 = client.get(f"/api/v1/reviews/{review['id']}")
    assert r2.status_code == 200
    assert r2.json()["data"]["author"] == "ada"


def test_review_author_null_when_unmatched(client, fake_supabase):
    """No matching oasis_findings row -> author is null, not fabricated."""
    fake_supabase.table("findings").rows.append(
        {
            "id": "f2",
            "owner_id": USER_A,
            "repo_id": "r1",
            "repo_name": "ada/oasis-backend",
            "title": "X",
            "location": "x.py:1",
            "severity": "low",
            "status": "open",
            "patch_filename": "x.py",
            "patch_diff": "",
            "patch_pr_number": 999,
            "patch_pr_title": "",
            "patch_pr_branch": "",
            "created_at": "2026-01-01T00:00:00Z",
            "approved_at": None,
            "dismissed_at": None,
            "resolved_at": None,
        }
    )
    r = client.get("/api/v1/reviews")
    review = r.json()["data"][0]
    assert review["author"] is None
