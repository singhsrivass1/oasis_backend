from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReviewItem(BaseModel):
    """A 'review' is not a stored entity -- there is no reviews table in the
    current schema (see section 23 of the product brief). This is a derived
    view built from a `findings` row (product-facing status/severity) joined
    in-memory against the matching `oasis_findings` row (which is the only
    place `pr_author` is currently persisted).

    KNOWN LIMITATION: if a PR's oasis_findings row cannot be matched (e.g.
    it predates this join key, or the webhook write to oasis_findings
    failed while findings still has a row), `author` will be null rather
    than fabricated. See services/reviews.py.
    """

    id: str                                                                        
    repository: str
    pr_number: int | None
    pr_title: str
    pr_branch: str
    author: str | None
    status: str
    severity: str
    created_at: datetime
