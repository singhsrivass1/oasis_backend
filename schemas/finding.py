from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Severity = Literal["critical", "high", "medium", "low", "advisory"]
FindingStatus = Literal["open", "awaiting_approval", "approved", "dismissed", "resolved"]
FixStatus = Literal["not_attempted", "opening", "opened", "failed"]

                                                            
                                                                     
                                                                        
                                                                         
                                                    
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"awaiting_approval", "dismissed"},
    "awaiting_approval": {"approved", "dismissed"},
    "approved": {"resolved"},
    "dismissed": set(),            
    "resolved": set(),            
}


class Finding(BaseModel):
    id: str
    repo_id: str | None
    repo_name: str
    title: str
    location: str
    severity: Severity
    status: FindingStatus
    patch_filename: str
    patch_diff: str
    patch_pr_number: int | None
    patch_pr_title: str
    patch_pr_branch: str
    created_at: datetime
    approved_at: datetime | None
    dismissed_at: datetime | None
    resolved_at: datetime | None
                                                                      
                                                                      
                                                                           
    fix_status: FixStatus = "not_attempted"
    fix_error: str | None = None
    fix_pr_number: int | None = None
    fix_pr_url: str | None = None
    fix_branch: str | None = None


class FindingStatusUpdateRequest(BaseModel):
    status: FindingStatus
