import os

from fastapi import Depends, FastAPI, Header, HTTPException

from inventory_service.repository import InventoryRepository
from inventory_service.service import InventoryService

app = FastAPI(title="Contoso Inventory Tool API", version="0.1.0")

# For now: mock repo. Later: swap to AzureSqlInventoryRepository
inventory_service = InventoryService(InventoryRepository())

TOOL_API_KEY = os.getenv("TOOL_API_KEY")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Require x-api-key header to match TOOL_API_KEY environment variable.

    Fail-closed behavior:
      - If TOOL_API_KEY is not set, we treat it as a server misconfiguration and return 500.
      - If header missing or wrong, return 401.
    """
    expected = TOOL_API_KEY
    if not expected:
        # Misconfigured deployment should not silently expose write endpoints
        raise HTTPException(
            status_code=500,
            detail=f"Server misconfigured: {TOOL_API_KEY} is not set.",
        )

    if x_api_key is None or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/inventory/get_item/{sku}")
def get_item(
    sku: str, _: None = Depends(require_api_key)
) -> dict[str, str | int | None]:
    item = inventory_service.get_item_availability(sku)
    return {
        "sku": item.sku,
        "name": item.name,
        "quantity": item.quantity,
        "status": item.status,
        "available_date": item.available_date.isoformat()
        if item.available_date
        else None,
    }


@app.post("/inventory/reserve/{sku}/{qty}")
def reserve_item(
    sku: str,
    qty: int,
    _: None = Depends(require_api_key),
) -> dict[str, str | int]:
    try:
        inventory_service.reserve_item(sku, qty)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "reserved", "sku": sku, "qty": qty}


@app.post("/inventory/receive/{sku}/{qty}")
def receive_item(
    sku: str,
    qty: int,
    _: None = Depends(require_api_key),
) -> dict[str, str | int]:
    try:
        inventory_service.receive_shipment(sku, qty)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "received", "sku": sku, "qty": qty}
