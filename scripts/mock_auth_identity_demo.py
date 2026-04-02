"""Demonstrate binding a trusted user identity to an MCP client.

The app (not the LLM) chooses the identity, attaches it to ClientSession
client_info, and then lets a mock "Foundry-style" planner decide which MCP
tool to call. The server enforces authorization based on that bound identity.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any, Iterable

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError
from mcp.types import Implementation


async def _foundry_style_tool_choice(user_message: str) -> tuple[str, dict[str, Any]]:
    """Very small stand-in for a Foundry agent choosing a tool call."""

    if "sensitive" in user_message.lower():
        return "get_sensitive_data", {"record_id": "vault-001"}
    return "get_my_data", {}


async def _run_once(identity: str, url: str, user_message: str) -> None:
    client_info = Implementation(
        name="auth-binding-demo-client",
        version="1.0.0",
        user=identity,
    )

    print(f"\n=== Running as {identity} ===")
    print(f"User message: {user_message}")

    try:
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(
                read_stream, write_stream, client_info=client_info
            ) as session:
                await session.initialize()
                tool_name, arguments = await _foundry_style_tool_choice(user_message)

                print(f"Calling MCP tool: {tool_name} with args {arguments or '{}'}")
                result = await session.call_tool(
                    tool_name,
                    arguments=arguments,
                    meta={"user": identity},
                )
                if getattr(result, "structuredContent", None) is not None:
                    print("Result:", result.structuredContent)
                else:
                    print("Result:", result)

    except McpError as exc:
        print("MCP denied the request:", exc)


async def run_demo(url: str, identities: Iterable[str]) -> None:
    user_message = "Please pull the sensitive report for this quarter."
    for identity in identities:
        await _run_once(identity, url, user_message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8011/mcp")
    parser.add_argument(
        "--identity",
        help="Single user identity (default runs authorized + unauthorized examples)",
    )
    args = parser.parse_args()

    identities = (
        [args.identity] if args.identity else ["alice@example.com", "bob@example.com"]
    )
    asyncio.run(run_demo(args.url, identities))


if __name__ == "__main__":
    main()
