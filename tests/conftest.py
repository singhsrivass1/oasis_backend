"""Test fixtures.

No live Supabase/Gemini/GitHub credentials are available in this
environment, so these tests use an in-memory FakeSupabase that mimics the
subset of the supabase-py query builder chain the app actually uses
(.table().select().eq().order().range().execute(), etc). This lets us
verify ownership enforcement, filtering, pagination, and the finding
state machine deterministically and offline. Live integration against a
real Supabase project is listed as a documented gap in the final report.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import main as main_module
from services.auth import CurrentUser, get_current_user
from services.supabase_client import get_supabase

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeQuery:
    def __init__(self, table: "FakeTable", op: str, payload=None):
        self.table = table
        self.op = op
        self.payload = payload
        self.filters: list[tuple[str, str, object]] = []
        self._order = None
        self._range = None
        self._limit = None
        self._count = None

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def ilike(self, field, value):
        self.filters.append(("ilike", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, values))
        return self

    def order(self, field, desc=False):
        self._order = (field, desc)
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def select(self, *_args, count=None):
        self._count = count
        return self

    def _matches(self, row) -> bool:
        for op, field, value in self.filters:
            if op == "eq" and row.get(field) != value:
                return False
            if op == "in" and row.get(field) not in value:
                return False
            if op == "ilike":
                needle = value.replace("%", "")
                if needle not in (row.get(field) or ""):
                    return False
        return True

    def execute(self):
        rows = [r for r in self.table.rows if self._matches(r)]

        if self.op == "select":
            if self._order:
                field, desc = self._order
                rows.sort(key=lambda r: r.get(field) or "", reverse=desc)
            total = len(rows)
            if self._range:
                start, end = self._range
                rows = rows[start : end + 1]
            elif self._limit is not None:
                rows = rows[: self._limit]
            return FakeResult(copy.deepcopy(rows), count=total if self._count == "exact" else None)

        if self.op == "insert":
            new_row = dict(self.payload)
            new_row.setdefault("id", self.table.next_id())
            new_row.setdefault("created_at", now_iso())
                                                                              
                                                                        
            if self.table.name == "repositories":
                new_row.setdefault("last_event", now_iso())
            self.table.rows.append(new_row)
            return FakeResult([copy.deepcopy(new_row)])

        if self.op == "update":
            updated = []
            for r in self.table.rows:
                if self._matches(r):
                    r.update(self.payload)
                    updated.append(r)
            return FakeResult(copy.deepcopy(updated))

        if self.op == "delete":
            keep, removed = [], []
            for r in self.table.rows:
                (removed if self._matches(r) else keep).append(r)
            self.table.rows = keep
            return FakeResult(copy.deepcopy(removed))

        raise NotImplementedError(self.op)


class FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class FakeTable:
    def __init__(self, name: str):
        self.name = name
        self.rows: list[dict] = []
        self._id_counter = 0

    def next_id(self) -> str:
                                                                 
                                                                      
                                                                       
                                                               
        return str(uuid.uuid4())

    def select(self, *args, count=None):
        return FakeQuery(self, "select").select(*args, count=count)

    def insert(self, payload):
        return FakeQuery(self, "insert", payload)

    def update(self, payload):
        return FakeQuery(self, "update", payload)

    def delete(self):
        return FakeQuery(self, "delete")


class FakeSupabase:
    def __init__(self):
        self._tables: dict[str, FakeTable] = {}

    def table(self, name: str) -> FakeTable:
        return self._tables.setdefault(name, FakeTable(name))


@pytest.fixture
def fake_supabase():
    fs = FakeSupabase()

    fs.table("users").rows.append(
        {
            "id": USER_A,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "password_hash": "should-never-be-returned",
            "org": "Analytical Engines Inc",
            "plan": "professional",
            "avatar": "",
            "github_username": "ada",
            "github_repos": 3,
            "github_followers": 10,
            "auth_provider": "github",
            "created_at": now_iso(),
        }
    )
    fs.table("users").rows.append(
        {
            "id": USER_B,
            "name": "Grace Hopper",
            "email": "grace@example.com",
            "password_hash": "should-never-be-returned",
            "org": "Navy",
            "plan": "starter",
            "avatar": "",
            "github_username": "",
            "github_repos": 0,
            "github_followers": 0,
            "auth_provider": "local",
            "created_at": now_iso(),
        }
    )
    return fs


@pytest.fixture
def client(fake_supabase):
    main_module.app.dependency_overrides[get_supabase] = lambda: fake_supabase
    main_module.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_A, email="ada@example.com", profile=fake_supabase.table("users").rows[0]
    )
    with TestClient(main_module.app) as c:
        yield c
    main_module.app.dependency_overrides.clear()
