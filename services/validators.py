"""Small shared validators used by the *_or_404 lookup helpers.

Fixes a real bug found during Phase 6 testing: passing a non-UUID string
(e.g. a stale/typo'd URL, or literally the word "undefined" from a buggy
frontend link) as an id straight into `.eq("id", value)` makes Postgres
throw a column-type syntax error, which surfaced as a raw 500
INTERNAL_ERROR instead of an honest 404. A malformed id and a
well-formed-but-missing id should look identical to the API caller.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException


def require_valid_uuid(value: str, *, not_found_message: str) -> None:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
                                                                         
                                                                 
                                    
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": not_found_message})