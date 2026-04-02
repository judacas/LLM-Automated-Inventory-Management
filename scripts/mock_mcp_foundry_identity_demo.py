"""Demo: app binds trusted user identity to MCP client in a Foundry-style flow.

This demo is intentionally isolated from production code and focuses on the
security pattern: the app chooses identity, binds it to the MCP client, and the
MCP server enforces authorization independent of model output.
"""

from __future__ import annotations

import argparse
import asyncio
import json

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError


def _simulate_foundry_tool_plan(user_prompt: str) -> list[str]:
    """Simple deterministic stand-in for a Foundry model selecting MCP tools."""
    lowered = user_prompt.lower()
    planned: list[str] = ["get_my_data"]
    if "sensitive" in lowered or "secret" in lowered:
        planned.append("get_sensitive_data")
    return planned


async def _run_for_identity(
    *,
    mcp_url: str,
    trusted_identity: str,
    user_prompt: str,
) -> dict[str, object]:
    tool_plan = _simulate_foundry_tool_plan(user_prompt)

    async with httpx.AsyncClient(headers={"x-demo-user": trusted_identity}) as http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                results: dict[str, object] = {}
                for tool_name in tool_plan:
                    try:
                        tool_result = await session.call_tool(tool_name, arguments={})
                        if getattr(tool_result, "isError", False):
                            content = getattr(tool_result, "content", []) or []
                            text_parts = [
                                getattr(item, "text", str(item)) for item in content
                            ]
                            results[tool_name] = {
                                "error": " ".join(text_parts) or str(tool_result)
                            }
                            continue
                        if getattr(tool_result, "structuredContent", None) is not None:
                            results[tool_name] = tool_result.structuredContent
                        else:
                            results[tool_name] = str(tool_result)
                    except (McpError, RuntimeError, ValueError, PermissionError) as exc:
                        results[tool_name] = {"error": str(exc)}
                return {
                    "trusted_identity": trusted_identity,
                    "tool_plan": tool_plan,
                    "tool_results": results,
                }


async def main_async(args: argparse.Namespace) -> None:
    base_url = args.base_url.rstrip("/")
    mcp_url = f"{base_url}/mcp"

    authorized = await _run_for_identity(
        mcp_url=mcp_url,
        trusted_identity=args.authorized_user,
        user_prompt=args.prompt,
    )
    unauthorized = await _run_for_identity(
        mcp_url=mcp_url,
        trusted_identity=args.unauthorized_user,
        user_prompt=args.prompt,
    )

    print("=== Trusted identity bound in app code ===")
    print(f"authorized user: {args.authorized_user}")
    print(f"unauthorized user: {args.unauthorized_user}")
    print()

    print("=== Authorized user run ===")
    print(json.dumps(authorized, indent=2))
    print()

    print("=== Unauthorized user run ===")
    print(json.dumps(unauthorized, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--authorized-user", default="alice@example.com")
    parser.add_argument("--unauthorized-user", default="bob@example.com")
    parser.add_argument(
        "--prompt",
        default="Please get my profile and sensitive planning data.",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
