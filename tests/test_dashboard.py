from tests.conftest import USER_A


def test_dashboard_empty_state_no_fabricated_data(client):
    r = client.get("/api/v1/dashboard")
    assert r.status_code == 200
    metrics = r.json()["data"]["metrics"]
    assert metrics["protected_repositories"] == 0
    assert metrics["security_score"] is None                                
    assert metrics["open_issues"] == 0
    assert metrics["prs_reviewed"] == 0


def test_dashboard_metrics_computed_from_real_data(client, fake_supabase):
    fake_supabase.table("repositories").rows.extend(
        [
            {
                "id": "r1",
                "owner_id": USER_A,
                "name": "a",
                "full_name": "ada/a",
                "language": "Python",
                "status": "secure",
                "score": 100,
                "prs_reviewed": 10,
                "issues_open": 0,
                "last_event": "2026-01-01T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "r2",
                "owner_id": USER_A,
                "name": "b",
                "full_name": "ada/b",
                "language": "Python",
                "status": "attention",
                "score": 60,
                "prs_reviewed": 5,
                "issues_open": 2,
                "last_event": "2026-01-01T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
    )
    fake_supabase.table("findings").rows.extend(
        [
            {
                "id": "f1",
                "owner_id": USER_A,
                "repo_id": "r2",
                "repo_name": "ada/b",
                "title": "x",
                "location": "x.py:1",
                "severity": "high",
                "status": "open",
                "patch_filename": "",
                "patch_diff": "",
                "patch_pr_number": 1,
                "patch_pr_title": "",
                "patch_pr_branch": "",
                "created_at": "2026-01-01T00:00:00Z",
                "approved_at": None,
                "dismissed_at": None,
                "resolved_at": None,
            },
            {
                "id": "f2",
                "owner_id": USER_A,
                "repo_id": "r2",
                "repo_name": "ada/b",
                "title": "y",
                "location": "y.py:1",
                "severity": "low",
                "status": "resolved",
                "patch_filename": "",
                "patch_diff": "",
                "patch_pr_number": 2,
                "patch_pr_title": "",
                "patch_pr_branch": "",
                "created_at": "2026-01-01T00:00:00Z",
                "approved_at": None,
                "dismissed_at": None,
                "resolved_at": None,
            },
        ]
    )

    r = client.get("/api/v1/dashboard")
    metrics = r.json()["data"]["metrics"]
    assert metrics["protected_repositories"] == 2
    assert metrics["security_score"] == 80.0                    
    assert metrics["open_issues"] == 1                                     
    assert metrics["prs_reviewed"] == 15          

    attention = r.json()["data"]["attention_required"]
    assert len(attention) == 1
    assert attention[0]["id"] == "r2"
