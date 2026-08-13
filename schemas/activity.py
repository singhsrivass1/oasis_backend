from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityItem(BaseModel):
    id: str
    title: str
    meta: str
    color: str
    created_at: datetime
