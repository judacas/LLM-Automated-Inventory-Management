"""Inventory MCP server definition (tools/resources/prompts live here).

Key design choice:
    The MCP server exposes deterministic inventory operations backed by the
    existing InventoryService + repository layer.
"""

import os
from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from inventory_service.admin_models import (
    InventoryAdminSummary,
    UnavailableRequestedItem,
)
from inventory_service.factory import (
    build_inventory_admin_service,
    build_inventory_service,
)
from inventory_service.models import InventoryItem_v2


# `FastMCP` is a high-level server helper from the MCP Python SDK.
#
# It lets us define:
# - server name + instructions (what the server is for)
# - tools (callable functions exposed to MCP clients)
# - the HTTP transport (handled by `mcp.streamable_http_app()` in `inventory_mcp.app`)
def _parse_csv_env(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [v.strip() for v in value.split(",") if v.strip()]


def _build_transport_security() -> TransportSecuritySettings:
    """Build DNS rebinding protection settings for deployed HTTP transports.

    Why this exists:
    - `FastMCP` auto-enables DNS rebinding protection when the server `host` is
      localhost-ish.
    - In App Service, requests arrive with `Host: <app>.azurewebsites.net`.
    - If allowed hosts don't include the Azure hostname, MCP requests fail with:
      `421 Invalid Host header`.

    Configuration:
    - `MCP_ALLOWED_HOSTS`: comma-separated hostnames to allow.
      Example: "admin-inventory-mcp.azurewebsites.net,mcp.contoso.com"
    - `WEBSITE_HOSTNAME`: automatically set by Azure App Service.
    """

    website_hostname = os.getenv("WEBSITE_HOSTNAME", "").strip()

    allowed_hosts: set[str] = {
        # Local dev / tests
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
    }

    for host in _parse_csv_env("MCP_ALLOWED_HOSTS"):
        allowed_hosts.add(host)
        allowed_hosts.add(f"{host}:*")

    if website_hostname:
        allowed_hosts.add(website_hostname)
        allowed_hosts.add(f"{website_hostname}:*")

    allowed_origins = {
        # Common dev origins (MCP Inspector)
        "http://127.0.0.1:*",
        "http://localhost:*",
    }
    for origin in _parse_csv_env("MCP_ALLOWED_ORIGINS"):
        allowed_origins.add(origin)

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(allowed_hosts),
        allowed_origins=sorted(allowed_origins),
    )


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
    transport_security=_build_transport_security(),
)

# Build the domain/service layer once at import time.
#
# Important: `build_inventory_service()` decides whether to use the real SQL repository
# or the in-memory/mock repository based on environment variables.
# That means your server behavior is controlled by env like `AZURE_SQL_CONNECTION_STRING`.
_inventory_service = build_inventory_service()
_inventory_admin_service = build_inventory_admin_service()


def _item_to_dict(item: InventoryItem_v2) -> dict[str, Any]:
    """Convert our domain model to JSON-serializable output.

    MCP tools support structured output. Here we return a plain dict so clients
    can consume it easily.
    """
    payload = asdict(item)
    if item.available_date is not None:
        payload["available_date"] = item.available_date.isoformat()
    return payload


def _admin_summary_to_dict(summary: InventoryAdminSummary) -> dict[str, Any]:
    payload = asdict(summary)
    return payload


def _unavailable_item_to_dict(item: UnavailableRequestedItem) -> dict[str, Any]:
    payload = asdict(item)
    if item.next_available_date is not None:
        payload["next_available_date"] = item.next_available_date.isoformat()
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


@mcp.tool()
def inventory_admin_summary(low_stock_threshold: int = 5) -> dict[str, Any]:
    """Admin-facing inventory rollup metrics.

    This supports the admin chat/orchestrator requirement:
    - "All general information about the current state of the system / inventory"
    """

    summary = _inventory_admin_service.get_summary(
        low_stock_threshold=low_stock_threshold
    )
    return _admin_summary_to_dict(summary)


@mcp.tool()
def inventory_unavailable_requested_items(
    quote_status: str = "active",
    top_n: int = 20,
) -> dict[str, Any]:
    """List items requested by customers that are currently not fulfillable from stock.

    Unified requested-unavailable definition:
    - Aggregate QuoteItems for Quotes with the given `quote_status` (default: active)
    - Use current inventory snapshot per product
    - Return products where requested_qty > in_stock_qty
      (includes both out-of-stock and partial-shortfall)

    Output is shaped as a dict containing an `items` array.
    """

    items = _inventory_admin_service.get_unavailable_requested_items(
        quote_status=quote_status,
        top_n=top_n,
    )
    return {
        "quote_status": quote_status,
        "items": [_unavailable_item_to_dict(i) for i in items],
    }


@mcp.tool()
def get_all_inventory() -> dict[str, Any]:
    """List inventory levels for all products (read-only).

    Supports admin requirements like:
    - "Admin can see inventory levels for all products."

    Output is shaped as a dict containing an `items` array.
    """

    items = _inventory_service.list_all_inventory()
    return {"items": [_item_to_dict(i) for i in items]}
