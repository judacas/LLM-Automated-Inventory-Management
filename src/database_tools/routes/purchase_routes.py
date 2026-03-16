from fastapi import APIRouter, HTTPException
from mcp.services.purchase_service import (
    CreatePurchaseOrderInput,
    PurchaseOrderResult,
    PurchaseOrderSummary,
    create_purchase_order,
    get_purchase_orders_by_domain,
)

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.post("/create", response_model=PurchaseOrderResult)
def create(data: CreatePurchaseOrderInput) -> PurchaseOrderResult:
    try:
        return create_purchase_order(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=list[PurchaseOrderSummary])
def list_purchase_orders(domain: str) -> list[PurchaseOrderSummary]:
    return get_purchase_orders_by_domain(domain)
