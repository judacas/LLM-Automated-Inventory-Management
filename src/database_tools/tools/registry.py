from typing import Any, Callable

from database_tools.tools.business_tools import (
    tool_create_business_account,
    tool_get_business_by_email,
)
from database_tools.tools.purchase_tools import (
    tool_create_purchase_order,
    tool_get_purchase_orders,
)
from database_tools.tools.quote_tools import (
    tool_confirm_quote,
    tool_confirm_quote_by_product_name,
    tool_get_active_quotes,
    tool_get_all_inventory,
    tool_get_dashboard_metrics,
    tool_get_inventory_status,
    tool_get_out_of_stock_items,
    tool_get_outstanding_quotes,
    tool_get_product_id_by_name,
    tool_get_quote_by_id,
)


class MCPToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, func: Callable[..., Any]) -> None:
        self._tools[name] = func

    def get(self, name: str) -> Callable[..., Any]:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not registered")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


registry = MCPToolRegistry()

registry.register("create_business_account", tool_create_business_account)
registry.register("get_business_by_email", tool_get_business_by_email)

registry.register("get_product_id_by_name", tool_get_product_id_by_name)
registry.register("confirm_quote_by_product_name", tool_confirm_quote_by_product_name)
registry.register("confirm_quote", tool_confirm_quote)
registry.register("get_active_quotes", tool_get_active_quotes)
registry.register("get_dashboard_metrics", tool_get_dashboard_metrics)
registry.register("get_outstanding_quotes", tool_get_outstanding_quotes)
registry.register("get_quote_by_id", tool_get_quote_by_id)
registry.register("get_out_of_stock_items", tool_get_out_of_stock_items)
registry.register("get_all_inventory", tool_get_all_inventory)
registry.register("get_inventory_status", tool_get_inventory_status)

registry.register("create_purchase_order", tool_create_purchase_order)
registry.register("get_purchase_orders", tool_get_purchase_orders)
