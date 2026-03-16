from admin_orchestrator_agent.classifier import AdminIntent, AdminIntentClassifier
from admin_orchestrator_agent.inventory_mcp_client import (
    InventoryMcpClient,
    try_extract_product_id,
)


class AdminOrchestratorService:
    """
    Routes admin requests to the correct underlying tool/agent.

    Today:
    - inventory path uses InventoryService (mock repo)
    - quote path is a stub (your teammate will own it)
    """

    def __init__(self) -> None:
        self.classifier = AdminIntentClassifier()
        self.inventory_client = InventoryMcpClient()

    def handle_message(self, message: str) -> str:
        intent = self.classifier.classify(message)

        if intent == AdminIntent.CHECK_INVENTORY:
            product_id = try_extract_product_id(message)
            if product_id is not None:
                item = self.inventory_client.call_tool_sync(
                    "get_inventory", {"product_id": product_id}
                )
                qty = item.get("quantity")
                status = item.get("status")
                name = item.get("product_name")
                return f"Inventory check: product_id {product_id} ({name}) has {qty} units ({status})."

            summary = self.inventory_client.call_tool_sync(
                "inventory_admin_summary", {"low_stock_threshold": 5}
            )
            return (
                "Inventory check: "
                f"{summary.get('in_stock_products')} in-stock / {summary.get('out_of_stock_products')} out-of-stock "
                f"({summary.get('total_products')} total products)."
            )

        if intent == AdminIntent.CHECK_QUOTES:
            return "Delegating to Quote Agent (not implemented in my module)."

        if intent == AdminIntent.SYSTEM_SUMMARY:
            inv = self.inventory_client.call_tool_sync(
                "inventory_admin_summary", {"low_stock_threshold": 5}
            )
            unavailable = self.inventory_client.call_tool_sync(
                "inventory_unavailable_requested_items",
                {"quote_status": "Pending", "top_n": 10},
            )
            unavailable_count = len(unavailable.get("items", []))
            return (
                "System summary (inventory): "
                f"{inv.get('in_stock_products')} in-stock / {inv.get('out_of_stock_products')} out-of-stock; "
                f"{unavailable_count} unavailable requested items on pending quotes."
            )

        return "I’m not sure what you mean. Can you clarify what you want to check?"
