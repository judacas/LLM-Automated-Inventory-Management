"""Admin message orchestrator.

This module implements the "admin conversational interface" requirement in a
minimal way:
- classify an admin message into an intent
- call the correct Inventory MCP tool(s)
- return a human-friendly string response

In the full system this would likely be replaced by an LLM-powered agent, but
keeping it deterministic makes it easy to test and demo.
"""

from admin_orchestrator_agent.classifier import AdminIntent, AdminIntentClassifier
from admin_orchestrator_agent.inventory_mcp_client import (
    InventoryMcpClient,
    try_extract_product_id,
)
from admin_orchestrator_agent.quote_agent_client import build_quote_agent_client


class AdminOrchestratorService:
    """
    Routes admin requests to the correct underlying tool/agent.

    Today:
        - inventory path calls Inventory MCP tools (HTTP) via `InventoryMcpClient`
            (with an optional in-process fallback for local dev/tests)
        - quote path is a stub (to be implemented via A2A with the quote agent)
    """

    def __init__(self) -> None:
        """Create classifier + MCP client dependencies."""
        self.classifier = AdminIntentClassifier()
        self.inventory_client = InventoryMcpClient()
        self.quote_client = build_quote_agent_client()

    def handle_message(self, message: str) -> str:
        """Handle one admin message and return a response string."""
        intent = self.classifier.classify(message)

        def _inventory_error_response(action: str) -> str:
            return (
                f"I couldn’t complete the inventory {action} right now. "
                "Please try again, or verify the Inventory MCP/service is reachable."
            )

        if intent == AdminIntent.CHECK_INVENTORY:
            product_id = try_extract_product_id(message)
            if product_id is not None:
                try:
                    item = self.inventory_client.call_tool_sync(
                        "get_inventory", {"product_id": product_id}
                    )
                except Exception:
                    return _inventory_error_response("check")
                qty = item.get("quantity")
                status = item.get("status")
                name = item.get("product_name")
                return f"Inventory check: product_id {product_id} ({name}) has {qty} units ({status})."

            try:
                summary = self.inventory_client.call_tool_sync(
                    "inventory_admin_summary", {"low_stock_threshold": 5}
                )
            except Exception:
                return _inventory_error_response("summary")
            return (
                "Inventory check: "
                f"{summary.get('in_stock_products')} in-stock / {summary.get('out_of_stock_products')} out-of-stock "
                f"({summary.get('total_products')} total products); "
                f"{summary.get('low_stock_products')} low-stock; "
                f"{summary.get('total_units_in_stock')} total units in stock."
            )

        if intent == AdminIntent.CHECK_QUOTES:
            return self.quote_client.handle_admin_query(message)

        if intent == AdminIntent.SYSTEM_SUMMARY:
            try:
                inv = self.inventory_client.call_tool_sync(
                    "inventory_admin_summary", {"low_stock_threshold": 5}
                )
                unavailable = self.inventory_client.call_tool_sync(
                    "inventory_unavailable_requested_items",
                    {"quote_status": "Pending", "top_n": 10},
                )
            except Exception:
                return _inventory_error_response("summary")

            unavailable_items = unavailable.get("items", [])
            unavailable_count = len(unavailable_items)
            unavailable_preview = ", ".join(
                [
                    str(i.get("product_name"))
                    for i in unavailable_items[:3]
                    if i.get("product_name")
                ]
            )
            unavailable_suffix = (
                f" (top: {unavailable_preview})" if unavailable_preview else ""
            )
            return (
                "System summary (inventory): "
                f"{inv.get('in_stock_products')} in-stock / {inv.get('out_of_stock_products')} out-of-stock; "
                f"{inv.get('low_stock_products')} low-stock; "
                f"{unavailable_count} unavailable requested items on pending quotes{unavailable_suffix}. "
                + self.quote_client.admin_summary()
            )

        return (
            "I’m not sure what you mean. Can you clarify what you want to check? "
            "Examples: 'system summary', 'check inventory', 'check inventory for product 1001', 'how many quotes do we have?'."
        )
