"""GitHub webhook payload + AI analysis contract.

This replaces the original schemas.py, which defined GitHubWebhookPayload
TWICE. The second definition silently shadowed the first in Python (last
class statement wins), and main.py's actual behavior depended on that
second, stricter definition:

    class GitHubWebhookPayload(BaseModel):
        action: str
        number: int
        repository: dict
        pull_request: dict

That is preserved here verbatim as the real contract. The first,
looser definition (extra="ignore", optional `number`, no `pull_request`
field, typed `repository: GitHubRepository`) is dropped as dead code --
it was never actually in effect.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GitHubWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str
    number: int
    repository: dict
    pull_request: dict


class OasisAnalysisResponse(BaseModel):
    severity: str = Field(description="Strictly evaluate as: critical, high, medium, low, or advisory.")
    file_path: str = Field(description="Exact file path.")
    line_number: int = Field(description="Starting line number.")
    title: str = Field(description="A short, 5 to 7 word summary of the vulnerability.")
    description: str = Field(description="Clinical security audit report.")
    suggested_patch: str = Field(description="Comprehensive, production-ready code replacement.")
