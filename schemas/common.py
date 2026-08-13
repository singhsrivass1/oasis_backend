"""Shared response envelope / pagination models used across every /api/v1 route.

Convention (documented in README):
  single object  -> {"data": {...}}
  list           -> {"data": [...], "pagination": {...}}
  error          -> {"error": {"code": ..., "message": ...}}
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Pagination(BaseModel):
    page: int
    limit: int
    total: int
    pages: int


class DataEnvelope(BaseModel, Generic[T]):
    data: T


class ListEnvelope(BaseModel, Generic[T]):
    data: list[T]
    pagination: Pagination


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class SimpleStatus(BaseModel):
    """Used for the pre-existing, non-versioned endpoints (/, /webhook) which
    predate the /api/v1 envelope convention and are intentionally left as-is
    to avoid breaking the existing GitHub webhook contract."""

    status: str
    reason: str | None = None


def pagination_params(page: int = 1, limit: int = 25) -> tuple[int, int]:
    """Clamp + validate pagination query params. Returns (page, limit)."""
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    return page, limit
