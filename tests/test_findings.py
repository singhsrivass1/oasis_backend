import pytest

from tests.conftest import USER_A


def _seed_findings(fake_supabase, n=30):
    for i in range(n):
        fake_supabase.table("findings").rows.append(
            {
                "id": f"f-{i}",
                "owner_id": USER_A,
                "repo_id": "repo-1" if i % 2 == 0 else "repo-2",
                "repo_name": "ada/oasis-backend",
                "title": f"Finding {i}",
                "location": "main.py:1",
                "severity": "high" if i % 3 == 0 else "low",
                "status": "open" if i % 2 == 0 else "resolved",
                "patch_filename": "main.py",
                "patch_diff": "",
                "patch_pr_number": i,
                "patch_pr_title": "",
                "patch_pr_branch": "",
                "created_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
                "approved_at": None,
                "dismissed_at": None,
                "resolved_at": None,
            }
        )


def test_findings_pagination_no_dupes_no_gaps(client, fake_supabase):
    _seed_findings(fake_supabase, n=30)

    seen_ids = set()
    page = 1
    total_pages = None
    while True:
        r = client.get(f"/api/v1/findings?page={page}&limit=10")
        assert r.status_code == 200
        body = r.json()
        total_pages = body["pagination"]["pages"]
        assert body["pagination"]["total"] == 30
        for f in body["data"]:
            assert f["id"] not in seen_ids
            seen_ids.add(f["id"])
        if page >= total_pages:
            break
        page += 1

    assert len(seen_ids) == 30
    assert total_pages == 3


def test_findings_filter_by_severity(client, fake_supabase):
    _seed_findings(fake_supabase, n=30)
    r = client.get("/api/v1/findings?severity=high")
    assert r.status_code == 200
    assert all(f["severity"] == "high" for f in r.json()["data"])


def test_findings_filter_by_status_and_repo(client, fake_supabase):
    _seed_findings(fake_supabase, n=30)
    r = client.get("/api/v1/findings?status=open&repo_id=repo-1")
    body = r.json()
    assert body["data"]
    assert all(f["status"] == "open" and f["repo_id"] == "repo-1" for f in body["data"])


def test_findings_invalid_severity_rejected(client):
    r = client.get("/api/v1/findings?severity=apocalyptic")
    assert r.status_code == 422


@pytest.mark.parametrize(
    "start,target,expect_ok",
    [
        ("open", "awaiting_approval", True),
        ("open", "dismissed", True),
        ("open", "resolved", False),                                                    
        ("awaiting_approval", "approved", True),
        ("approved", "resolved", True),
        ("resolved", "open", False),                                    
        ("dismissed", "open", False),                  
    ],
)
def test_finding_state_transitions(client, fake_supabase, start, target, expect_ok):
    fake_supabase.table("findings").rows.append(
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "owner_id": USER_A,
            "repo_id": "repo-1",
            "repo_name": "ada/oasis-backend",
            "title": "T",
            "location": "x.py:1",
            "severity": "high",
            "status": start,
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
    r = client.patch("/api/v1/findings/11111111-1111-1111-1111-111111111111", json={"status": target})
    if expect_ok:
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == target
    else:
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INVALID_TRANSITION"


def test_finding_approval_stamps_timestamp(client, fake_supabase):
    fake_supabase.table("findings").rows.append(
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "owner_id": USER_A,
            "repo_id": "repo-1",
            "repo_name": "ada/oasis-backend",
            "title": "T",
            "location": "x.py:1",
            "severity": "high",
            "status": "awaiting_approval",
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
    r = client.patch("/api/v1/findings/22222222-2222-2222-2222-222222222222", json={"status": "approved"})
    assert r.status_code == 200
    assert r.json()["data"]["approved_at"] is not None
