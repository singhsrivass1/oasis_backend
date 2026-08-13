from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Plan = Literal["starter", "professional", "enterprise"]
AuthProvider = Literal["local", "google", "github"]


class MeResponse(BaseModel):
    """Safe, frontend-facing view of the current authenticated user.

    Deliberately excludes: password_hash, google_id, github_id (internal
    join keys), and every secret/token. See services/auth.py for the
    authentication mechanism this is sourced from.
    """

    id: str
    name: str
    email: str
    org: str
    plan: Plan
    avatar: str
    auth_provider: AuthProvider
    github_username: str
    github_repos: int
    github_followers: int
    created_at: datetime
