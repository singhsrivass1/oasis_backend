from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from schemas.activity import ActivityItem
from schemas.finding import Finding

RepoStatus = Literal["secure", "reviewing", "attention"]

                                                                      
                                                                    
_FULL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Repository(BaseModel):
    id: str
    owner_id: str
    name: str
    full_name: str
    language: str
    status: RepoStatus
    score: float
    prs_reviewed: int
    issues_open: int
    last_event: datetime
    created_at: datetime


class RepositoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    full_name: str = Field(..., min_length=3, max_length=300)
    language: str = Field(default="TypeScript", max_length=50)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        if not _FULL_NAME_RE.match(v):
            raise ValueError("full_name must look like 'owner/repo'")
        return v


class RepositoryDetail(BaseModel):
    repository: Repository
    findings: list[Finding]
    activity: list[ActivityItem]
