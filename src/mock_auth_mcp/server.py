"""Mock MCP server that enforces user-bound authorization.

This server is intentionally small and self contained:
- In-memory users and permission map (no database)
- Two tools: `get_my_data` and `get_sensitive_data`
- Authorization driven by the user identity sent in the MCP session/request

The key behavior demonstrated here is that *the application* chooses a trusted
user identity and binds it to the MCP client. The server validates that
identity on every tool call, regardless of what the LLM says.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import Implementation, RequestParams

_USERS: dict[str, dict[str, Any]] = {
    "alice@example.com": {
        "profile": {"role": "analyst", "department": "finance"},
        "permissions": {"basic", "sensitive"},
        "notes": ["Prefers CSV exports", "Cleared for quarterly reporting data"],
    },
    "bob@example.com": {
        "profile": {"role": "support", "department": "ops"},
        "permissions": {"basic"},
        "notes": ["No production data access", "Shadowing the finance team"],
    },
}

_SENSITIVE_RECORDS: dict[str, str] = {
    "vault-001": "Quarterly revenue forecast",
    "vault-002": "Payroll change log",
}


def _build_transport_security() -> TransportSecuritySettings:
    """Baseline transport security suitable for local dev + tunnels."""

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ],
    )


mcp = FastMCP(
    "auth-bound-mcp",
    instructions=(
        "Mock MCP server that enforces user-bound authorization. "
        "Client code must attach a trusted user identity to the MCP session. "
        "Tools will reject callers without the right permissions."
    ),
    stateless_http=True,
    json_response=True,
    transport_security=_build_transport_security(),
)


def resolve_identity_from_payload(
    client_info: Implementation | None, meta: RequestParams.Meta | None
) -> str | None:
    """Extract the asserted user identity from client_info or request meta.

    We support both because the app can bind identity at session-init time
    (client_info.extra) or per-call (call_tool meta). LLM output is not used.
    """

    def _pick(mapping: Mapping[str, Any] | None) -> str | None:
        if mapping is None:
            return None
        for key in ("user", "userEmail", "user_email", "identity"):
            value = mapping.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    if meta is not None:
        # RequestParams.Meta allows extra fields; Pydantic stores them in model_extra.
        meta_candidate = _pick(getattr(meta, "model_extra", None))
        if meta_candidate:
            return meta_candidate

    if client_info is not None:
        # Implementation permits extra attributes; prefer model_extra to avoid mypy noise.
        return _pick(getattr(client_info, "model_extra", None))

    return None


def resolve_identity(ctx: Context) -> str:
    """Resolve the caller's identity or raise a clear error."""

    client_params = getattr(ctx.request_context.session, "client_params", None)
    client_info = getattr(client_params, "clientInfo", None) if client_params else None
    identity = resolve_identity_from_payload(client_info, ctx.request_context.meta)

    if not identity:
        raise PermissionError(
            "Missing trusted user identity. Set `client_info.user` (or similar) "
            "when constructing the MCP ClientSession."
        )

    return identity.lower()


def require_permission(identity: str, permission: str) -> None:
    """Ensure the user holds the required permission."""

    permissions = _USERS.get(identity, {}).get("permissions", set())
    if permission not in permissions:
        raise PermissionError(
            f"{identity} is not authorized for '{permission}' operations."
        )


@mcp.tool()
def get_my_data(ctx: Context) -> dict[str, Any]:
    """Return caller-specific data."""

    identity = resolve_identity(ctx)
    profile = _USERS.get(identity)
    if profile is None:
        raise PermissionError(f"Unknown user {identity}")

    return {
        "user": identity,
        "profile": profile["profile"],
        "notes": list(profile["notes"]),
        "permissions": sorted(profile["permissions"]),
    }


@mcp.tool()
def get_sensitive_data(ctx: Context, record_id: str = "vault-001") -> dict[str, Any]:
    """Return sensitive data only to authorized users."""

    identity = resolve_identity(ctx)
    require_permission(identity, "sensitive")
    payload = _SENSITIVE_RECORDS.get(
        record_id, f"[no record stored for {record_id}]"
    )

    return {
        "user": identity,
        "record_id": record_id,
        "secret": payload,
    }
