"""Signs a short-lived, tamper-proof token embedding an Oasis user id.

Used to correlate a GitHub App installation (which GitHub only ever
identifies by installation_id) back to the Oasis user who clicked
"Connect GitHub" -- since the browser redirect to/from GitHub can't carry
an Authorization header, this travels as a `state` query parameter
instead, the same pattern OAuth flows use.

No new dependency: HMAC-SHA256 over `user_id.issued_at`, base64url-encoded.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import HTTPException

from config import settings

_MAX_AGE_SECONDS = 600                                                  


def _secret() -> str:
    if not settings.oasis_state_secret:
        raise RuntimeError("OASIS_STATE_SECRET is not set.")
    return settings.oasis_state_secret


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_state(user_id: str) -> str:
    issued_at = str(int(time.time()))
    payload = f"{user_id}.{issued_at}"
    signature = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).digest()
    return f"{_b64url_encode(payload.encode())}.{_b64url_encode(signature)}"


def verify_state(token: str) -> str:
    """Returns the embedded user_id, or raises HTTPException(400)."""
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload = _b64url_decode(payload_b64).decode()
        signature = _b64url_decode(signature_b64)
        user_id, issued_at_str = payload.rsplit(".", 1)
        issued_at = int(issued_at_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid or corrupted state token.") from exc

    expected_signature = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=400, detail="Invalid state token signature.")

    if time.time() - issued_at > _MAX_AGE_SECONDS:
        raise HTTPException(status_code=400, detail="State token expired. Please try connecting again.")

    return user_id
