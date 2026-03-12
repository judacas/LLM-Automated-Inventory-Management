from typing import Any, TypedDict

from mcp.services.purchase_service import (
    create_purchase_order,
    get_purchase_orders_by_domain,
)


class CreatePurchaseOrderArgs(TypedDict):
    quote_id: int
    domain: str | None


class GetPurchaseOrdersArgs(TypedDict):
    domain: str


def tool_create_purchase_order(
    arguments: CreatePurchaseOrderArgs,
) -> Any:
    return create_purchase_order(arguments)


def tool_get_purchase_orders(
    arguments: GetPurchaseOrdersArgs,
) -> Any:
    return get_purchase_orders_by_domain(
        domain=arguments["domain"],
    )
