import time

import pytest
from fastapi import HTTPException

from services import state_token


def test_sign_and_verify_roundtrip(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "oasis_state_secret", "test-secret")
    token = state_token.sign_state("user-123")
    assert state_token.verify_state(token) == "user-123"


def test_verify_rejects_tampered_token(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "oasis_state_secret", "test-secret")
    token = state_token.sign_state("user-123")
    tampered = token[:-2] + "xx"
    with pytest.raises(HTTPException) as exc_info:
        state_token.verify_state(tampered)
    assert exc_info.value.status_code == 400


def test_verify_rejects_expired_token(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "oasis_state_secret", "test-secret")
    monkeypatch.setattr(state_token, "_MAX_AGE_SECONDS", 1)
    token = state_token.sign_state("user-123")
    time.sleep(1.2)
    with pytest.raises(HTTPException) as exc_info:
        state_token.verify_state(token)
    assert "expired" in exc_info.value.detail.lower()


def test_verify_rejects_wrong_secret(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "oasis_state_secret", "secret-a")
    token = state_token.sign_state("user-123")
    monkeypatch.setattr(settings, "oasis_state_secret", "secret-b")
    with pytest.raises(HTTPException):
        state_token.verify_state(token)
