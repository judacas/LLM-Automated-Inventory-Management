"""Client wrapper for talking to the Inventory MCP server.

This module is used by the admin orchestrator to call MCP tools over Streamable
HTTP.

Key behaviors:
- Endpoint is configured via `INVENTORY_MCP_URL` (defaults to localhost).
- Optional in-process fallback enables unit tests and local dev even if the MCP
    server isn't running.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from inventory_service.factory import (
    build_inventory_admin_service,
    build_inventory_service,
)
from inventory_service.models import InventoryItem_v2


class InventoryMcpClient:
    """Small wrapper around the MCP Streamable-HTTP client.

    The orchestrator agent should be *decision logic* only (pick which tool to call).
    This wrapper keeps MCP session/transport details out of the orchestrator.

    Configure the endpoint via env var:
    - INVENTORY_MCP_URL (default: http://localhost:8000/mcp)
    """

    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv("INVENTORY_MCP_URL", "http://localhost:8000/mcp")

        # Unit-test/dev safety valve:
        # - If the MCP server isn't running yet, we can still provide useful behavior
        #   by calling the same service layer in-process.
        # - In integration/production, set this to "0" to fail fast if MCP is down.
        self.allow_in_process_fallback = (
            os.getenv("INVENTORY_MCP_FALLBACK_IN_PROCESS", "1").strip() != "0"
        )

        # In-process services use the same mock-vs-SQL switching logic as MCP.
        self._inventory_service = build_inventory_service()
        self._inventory_admin_service = build_inventory_admin_service()

    @staticmethod
    def _item_to_dict(item: InventoryItem_v2) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "product_id": item.product_id,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "available_date": item.available_date.isoformat()
            if item.available_date
            else None,
            "status": item.status,
        }
        return payload

    def _call_tool_in_process(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "get_inventory":
            product_id = int(arguments["product_id"])
            item = self._inventory_service.get_inventory_by_product_id(product_id)
            return self._item_to_dict(item)

        if name == "reserve_inventory":
            product_id = int(arguments["product_id"])
            qty = int(arguments["qty"])
            self._inventory_service.reserve_by_product_id(product_id, qty)
            return {"status": "reserved", "product_id": product_id, "qty": qty}

        if name == "receive_inventory":
            product_id = int(arguments["product_id"])
            qty = int(arguments["qty"])
            self._inventory_service.receive_shipment_by_product_id(product_id, qty)
            return {"status": "received", "product_id": product_id, "qty": qty}

        if name == "inventory_admin_summary":
            low_stock_threshold = int(arguments.get("low_stock_threshold", 5))
            summary = self._inventory_admin_service.get_summary(
                low_stock_threshold=low_stock_threshold
            )
            return {
                "total_products": summary.total_products,
                "in_stock_products": summary.in_stock_products,
                "out_of_stock_products": summary.out_of_stock_products,
                "low_stock_products": summary.low_stock_products,
                "total_units_in_stock": summary.total_units_in_stock,
                "most_recent_inventory_update": summary.most_recent_inventory_update,
            }

        if name == "inventory_unavailable_requested_items":
            quote_status = str(arguments.get("quote_status", "Pending"))
            top_n = int(arguments.get("top_n", 20))
            items = self._inventory_admin_service.get_unavailable_requested_items(
                quote_status=quote_status,
                top_n=top_n,
            )
            return {
                "quote_status": quote_status,
                "items": [
                    {
                        "product_id": i.product_id,
                        "product_name": i.product_name,
                        "requested_qty": i.requested_qty,
                        "in_stock_qty": i.in_stock_qty,
                        "shortfall_qty": i.shortfall_qty,
                        "next_available_date": i.next_available_date.isoformat()
                        if i.next_available_date
                        else None,
                    }
                    for i in items
                ],
            }

        raise KeyError(f"Unknown tool: {name}")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            if ClientSession is None or streamable_http_client is None:
                raise RuntimeError("MCP client dependencies are not installed")

            async with streamable_http_client(self.url) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments=arguments)
                    if getattr(result, "structuredContent", None) is not None:
                        return result.structuredContent
                    return result
        except Exception:
            if not self.allow_in_process_fallback:
                raise
            return self._call_tool_in_process(name, arguments)

    def call_tool_sync(self, name: str, arguments: dict[str, Any]) -> Any:
        """Synchronous helper for simple scripts/tests.

        Note: this uses `asyncio.run(...)`, which cannot be called from inside an
        already-running event loop (e.g., inside an async web framework).
        """
        return asyncio.run(self.call_tool(name, arguments))


_PRODUCT_ID_RE = re.compile(r"\b(\d{1,9})\b")


def try_extract_product_id(message: str) -> int | None:
    """Best-effort extraction of a product_id from a user/admin message."""

    match = _PRODUCT_ID_RE.search(message)
    if not match:
        return None
    try:
        value = int(match.group(1))
    except ValueError:
        return None
    return value if value > 0 else None
