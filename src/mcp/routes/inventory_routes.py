from fastapi import APIRouter, HTTPException

from mcp.services.inventory_service import (
    InventoryResponse,
    get_inventory_by_product_id,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/{product_id}")
def fetch_inventory(product_id: int) -> InventoryResponse:
    try:
        return get_inventory_by_product_id(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
