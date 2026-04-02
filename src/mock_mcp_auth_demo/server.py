"""Isolated mock MCP server for trusted-identity authorization demos."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

USERS: dict[str, dict[str, Any]] = {
    "alice@example.com": {
        "email": "alice@example.com",
        "department": "procurement",
        "tier": "admin",
    },
    "bob@example.com": {
        "email": "bob@example.com",
        "department": "support",
        "tier": "standard",
    },
}

PERMISSIONS: dict[str, set[str]] = {
    "alice@example.com": {"get_my_data", "get_sensitive_data"},
    "bob@example.com": {"get_my_data"},
}

SENSITIVE_DATA: dict[str, Any] = {
    "quarterly_margin": "42%",
    "acquisition_plan": "Confidential draft for next quarter",
}

mcp = FastMCP(
    "trusted-identity-mock-mcp",
    instructions=(
        "Mock MCP server used to demonstrate server-side authorization using a "
        "trusted app-supplied user identity."
    ),
    stateless_http=True,
    json_response=True,
)


def _trusted_user_from_context(ctx: Context) -> str:
    request = ctx.request_context.request
    if request is None:
        raise PermissionError("Missing HTTP request context for authorization.")

    identity = request.headers.get("x-demo-user", "").strip()
    if not identity:
        raise PermissionError(
            "Missing trusted identity header: x-demo-user. "
            "The app must bind a trusted user identity when creating the MCP client."
        )
    if identity not in USERS:
        raise PermissionError(f"Unknown user identity: {identity}")
    return identity


def _authorize(identity: str, tool_name: str) -> None:
    allowed_tools = PERMISSIONS.get(identity, set())
    if tool_name not in allowed_tools:
        raise PermissionError(
            f"User '{identity}' is not authorized to call tool '{tool_name}'."
        )


@mcp.tool()
def get_my_data(ctx: Context) -> dict[str, Any]:
    identity = _trusted_user_from_context(ctx)
    _authorize(identity, "get_my_data")
    return {
        "user": identity,
        "profile": USERS[identity],
        "source": "mock-mcp-server",
    }


@mcp.tool()
def get_sensitive_data(ctx: Context) -> dict[str, Any]:
    identity = _trusted_user_from_context(ctx)
    _authorize(identity, "get_sensitive_data")
    return {
        "user": identity,
        "sensitive": SENSITIVE_DATA,
        "source": "mock-mcp-server",
    }
