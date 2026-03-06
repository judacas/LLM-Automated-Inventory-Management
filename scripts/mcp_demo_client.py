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


async def run_demo(url: str, product_id: int, qty: int) -> None:
    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            print("TOOLS:", tool_names)

            async def call(name: str, arguments: dict[str, Any]) -> Any:
                result = await session.call_tool(name, arguments=arguments)
                # Prefer structured output if present.
                if getattr(result, "structuredContent", None) is not None:
                    return result.structuredContent
                return result

            print("\nget_inventory:")
            print(await call("get_inventory", {"product_id": product_id}))

            print("\nreserve_inventory:")
            print(
                await call("reserve_inventory", {"product_id": product_id, "qty": qty})
            )

            print("\nget_inventory (after reserve):")
            print(await call("get_inventory", {"product_id": product_id}))

            print("\nreceive_inventory:")
            print(
                await call("receive_inventory", {"product_id": product_id, "qty": qty})
            )

            print("\nget_inventory (after receive):")
            print(await call("get_inventory", {"product_id": product_id}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/mcp")
    parser.add_argument("--product-id", type=int, default=1001)
    parser.add_argument("--qty", type=int, default=3)
    args = parser.parse_args()

    asyncio.run(run_demo(args.url, args.product_id, args.qty))


if __name__ == "__main__":
    main()
