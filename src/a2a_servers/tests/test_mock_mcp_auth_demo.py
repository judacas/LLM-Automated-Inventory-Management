from __future__ import annotations

from dataclasses import dataclass

import pytest

from mock_mcp_auth_demo.server import (
    _authorize,
    _trusted_user_from_context,
    get_my_data,
    get_sensitive_data,
)


@dataclass
class _FakeRequest:
    headers: dict[str, str]


@dataclass
class _FakeRequestContext:
    request: _FakeRequest


@dataclass
class _FakeContext:
    request_context: _FakeRequestContext


def _ctx_for(identity: str | None) -> _FakeContext:
    headers: dict[str, str] = {}
    if identity is not None:
        headers["x-demo-user"] = identity
    return _FakeContext(request_context=_FakeRequestContext(request=_FakeRequest(headers)))


def test_trusted_user_reads_from_request_header() -> None:
    identity = _trusted_user_from_context(_ctx_for("alice@example.com"))
    assert identity == "alice@example.com"


def test_missing_identity_is_denied() -> None:
    with pytest.raises(PermissionError, match="Missing trusted identity header"):
        _trusted_user_from_context(_ctx_for(None))


def test_unknown_identity_is_denied() -> None:
    with pytest.raises(PermissionError, match="Unknown user identity"):
        _trusted_user_from_context(_ctx_for("mallory@example.com"))


def test_authorize_allows_granted_tool() -> None:
    _authorize("alice@example.com", "get_sensitive_data")


def test_authorize_denies_missing_permission() -> None:
    with pytest.raises(PermissionError, match="not authorized"):
        _authorize("bob@example.com", "get_sensitive_data")


def test_get_my_data_returns_profile_for_authorized_user() -> None:
    payload = get_my_data(_ctx_for("bob@example.com"))
    assert payload["user"] == "bob@example.com"
    assert payload["profile"]["department"] == "support"


def test_get_sensitive_data_denies_unauthorized_user() -> None:
    with pytest.raises(PermissionError, match="not authorized"):
        get_sensitive_data(_ctx_for("bob@example.com"))
