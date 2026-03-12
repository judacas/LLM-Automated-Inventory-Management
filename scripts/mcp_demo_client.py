"""Minimal Streamable-HTTP MCP client for local demos.

Usage (server already running):
    uv run python scripts/mcp_demo_client.py --url http://localhost:8001/mcp --product-id 1001

This avoids Node tooling (npx inspector) and verifies:
- session initialize
- list_tools
- call_tool for inventory tools
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError


async def run_demo(url: str, product_id: int, qty: int) -> None:
    # The MCP Streamable HTTP transport is implemented as a pair of async streams:
    # - `read_stream`: messages coming from the server
    # - `write_stream`: messages we send to the server
    # The client helper also returns a third value (implementation detail) we don't need here.
    try:
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            # `ClientSession` implements MCP session semantics (initialize, list tools, call tools, etc.).
            async with ClientSession(read_stream, write_stream) as session:
                # MCP handshake: tells the server our capabilities and starts a session.
                await session.initialize()

                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                print("TOOLS:", tool_names)

                async def call(name: str, arguments: dict[str, Any]) -> Any:
                    # `call_tool` returns an object that may contain:
                    # - `structuredContent`: JSON-like content (best for demos)
                    # - other fields depending on server/client versions
                    result = await session.call_tool(name, arguments=arguments)
                    # Prefer structured output if present.
                    if getattr(result, "structuredContent", None) is not None:
                        return result.structuredContent
                    return result

                print("\nget_inventory:")
                print(await call("get_inventory", {"product_id": product_id}))

                print("\nreserve_inventory:")
                print(
                    await call(
                        "reserve_inventory", {"product_id": product_id, "qty": qty}
                    )
                )

                print("\nget_inventory (after reserve):")
                print(await call("get_inventory", {"product_id": product_id}))

                print("\nreceive_inventory:")
                print(
                    await call(
                        "receive_inventory", {"product_id": product_id, "qty": qty}
                    )
                )

                print("\nget_inventory (after receive):")
                print(await call("get_inventory", {"product_id": product_id}))
    except McpError as exc:
        # This is the common failure mode when the URL is wrong (wrong port/app/path)
        # or the server isn't actually serving MCP Streamable HTTP at that endpoint.
        print(f"MCP ERROR: {exc}")
        print("\nTroubleshooting:")
        print("1) Confirm the MCP ASGI app is running (not the legacy tool_api app).")
        print(
            "   Start command: uv run uvicorn inventory_mcp.app:app --reload --port 8000"
        )
        print("2) Confirm the MCP endpoint responds:")
        print("   curl -i http://localhost:8000/mcp")
        print("   curl -i http://localhost:8000/mcp/")
        print(
            "3) Make sure you're using the right port (if Uvicorn is on 8001, update --url)."
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/mcp")
    parser.add_argument("--product-id", type=int, default=1001)
    parser.add_argument("--qty", type=int, default=3)
    args = parser.parse_args()

    asyncio.run(run_demo(args.url, args.product_id, args.qty))


if __name__ == "__main__":
    main()
