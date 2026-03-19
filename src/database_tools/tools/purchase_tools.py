from database_tools.services.purchase_service import (
    CreatePurchaseOrderInput,
    PurchaseOrderResult,
    PurchaseOrderSummary,
    create_purchase_order,
    get_purchase_orders_by_domain,
)


def tool_create_purchase_order(
    data: CreatePurchaseOrderInput,
) -> PurchaseOrderResult:
    return create_purchase_order(data)


def tool_get_purchase_orders(
    domain: str,
) -> list[PurchaseOrderSummary]:
    return get_purchase_orders_by_domain(domain=domain)
