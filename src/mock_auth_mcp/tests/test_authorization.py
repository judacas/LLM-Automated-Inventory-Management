import pytest
from mcp.types import Implementation, RequestParams

from mock_auth_mcp import server


def test_resolve_identity_prefers_meta() -> None:
    client_info = Implementation(
        name="demo-client", version="1.0.0", user="alice@example.com"
    )
    meta = RequestParams.Meta(user="bob@example.com")

    assert server.resolve_identity_from_payload(client_info, meta) == "bob@example.com"


def test_resolve_identity_from_client_info_extra_field() -> None:
    client_info = Implementation(
        name="demo-client",
        version="1.0.0",
        identity="carol@example.com",
    )

    assert (
        server.resolve_identity_from_payload(client_info, None)
        == "carol@example.com"
    )


def test_require_permission_blocks_unauthorized_user() -> None:
    with pytest.raises(PermissionError):
        server.require_permission("bob@example.com", "sensitive")


def test_require_permission_allows_authorized_user() -> None:
    server.require_permission("alice@example.com", "sensitive")
