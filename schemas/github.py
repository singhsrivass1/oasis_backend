from __future__ import annotations

from pydantic import BaseModel


class GitHubStatusResponse(BaseModel):
    connected: bool
    username: str | None = None


class GitHubRepositoriesResponse(BaseModel):
    """Live discovery of repos accessible through the user's connected
    GitHub App installation. `supported: false` only when no installation
    is connected yet -- once GET /api/v1/github/connect has been
    completed, this returns the real repo list from GitHub. See
    services/github_app.py.
    """

    supported: bool
    repositories: list[dict] = []
    message: str


class GitHubConnectResponse(BaseModel):
    """Returned by GET /api/v1/github/connect. The frontend opens
    `install_url` itself (e.g. via url_launcher) -- it can't be a raw
    HTTP redirect from this endpoint since GitHub's install picker is
    reached via a plain browser navigation with no Authorization header,
    while this endpoint itself requires one.
    """

    install_url: str
