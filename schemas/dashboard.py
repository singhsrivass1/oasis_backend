from __future__ import annotations

from pydantic import BaseModel

from schemas.activity import ActivityItem
from schemas.repository import Repository


class DashboardMetrics(BaseModel):
    protected_repositories: int
                                                                        
                                                                    
                                                                 
    security_score: float | None
    open_issues: int
    prs_reviewed: int


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    repositories: list[Repository]
    attention_required: list[Repository]
    recent_activity: list[ActivityItem]
