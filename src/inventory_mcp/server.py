"""Inventory MCP server definition (tools/resources/prompts live here).

Key design choice:
    The MCP server exposes deterministic inventory operations backed by the
    existing InventoryService + repository layer.
"""

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from inventory_service.factory import build_inventory_service
from inventory_service.models import InventoryItem_v2

mcp = FastMCP(
    "contoso-inventory",
    instructions=(
        "Deterministic inventory MCP server. "
        "Exposes tool-backed inventory read/write operations backed by the InventoryService layer."
    ),
    # Recommended for scalable HTTP deployments.
    stateless_http=True,
    json_response=True,
)

_inventory_service = build_inventory_service()


def _item_to_dict(item: InventoryItem_v2) -> dict[str, Any]:
    """Convert our domain model to JSON-serializable output.

    MCP tools support structured output. Here we return a plain dict so clients
    can consume it easily.
    """
    payload = asdict(item)
    if item.available_date is not None:
        payload["available_date"] = item.available_date.isoformat()
    return payload


@mcp.tool()
def get_inventory(product_id: int) -> dict[str, Any]:
    """Get inventory status for a `product_id` (read-only)."""
    item = _inventory_service.get_inventory_by_product_id(product_id)
    return _item_to_dict(item)


@mcp.tool()
def reserve_inventory(product_id: int, qty: int) -> dict[str, Any]:
    """Reserve (decrease) inventory for a `product_id` (side-effect)."""
    _inventory_service.reserve_by_product_id(product_id, qty)
    return {"status": "reserved", "product_id": product_id, "qty": qty}


@mcp.tool()
def receive_inventory(product_id: int, qty: int) -> dict[str, Any]:
    """Receive (increase) inventory for a `product_id` (side-effect)."""
    _inventory_service.receive_shipment_by_product_id(product_id, qty)
    return {"status": "received", "product_id": product_id, "qty": qty}
