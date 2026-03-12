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

# `FastMCP` is a high-level server helper from the MCP Python SDK.
#
# It lets us define:
# - server name + instructions (what the server is for)
# - tools (callable functions exposed to MCP clients)
# - the HTTP transport (handled by `mcp.streamable_http_app()` in `inventory_mcp.app`)
mcp = FastMCP(
    "contoso-inventory",
    instructions=(
        "Deterministic inventory MCP server. "
        "Exposes tool-backed inventory read/write operations backed by the InventoryService layer."
    ),
    # `stateless_http=True` is recommended for scalable HTTP deployments.
    # It avoids holding per-client state in-process between requests.
    stateless_http=True,
    # Always respond with JSON (easier to demo and integrate).
    json_response=True,
)

# Build the domain/service layer once at import time.
#
# Important: `build_inventory_service()` decides whether to use the real SQL repository
# or the in-memory/mock repository based on environment variables.
# That means your server behavior is controlled by env like `AZURE_SQL_CONNECTION_STRING`.
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
    """Get inventory status for a `product_id` (read-only).

    Returns a JSON-serializable dict (so clients can render it directly).

    Error behavior:
    - `ValueError` for invalid product IDs
    - `KeyError` for unknown product IDs (e.g., not in the Products table)
    Those exceptions propagate through MCP as tool call errors.
    """
    item = _inventory_service.get_inventory_by_product_id(product_id)
    return _item_to_dict(item)


@mcp.tool()
def reserve_inventory(product_id: int, qty: int) -> dict[str, Any]:
    """Reserve (decrease) inventory for a `product_id` (side-effect).

    This is an example of a tool that performs a write operation.
    """
    _inventory_service.reserve_by_product_id(product_id, qty)
    return {"status": "reserved", "product_id": product_id, "qty": qty}


@mcp.tool()
def receive_inventory(product_id: int, qty: int) -> dict[str, Any]:
    """Receive (increase) inventory for a `product_id` (side-effect)."""
    _inventory_service.receive_shipment_by_product_id(product_id, qty)
    return {"status": "received", "product_id": product_id, "qty": qty}
