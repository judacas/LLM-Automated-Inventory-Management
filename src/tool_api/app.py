import os

from fastapi import Depends, FastAPI, Header, HTTPException

from inventory_agent.repository import InventoryRepository
from inventory_agent.service import InventoryService

app = FastAPI(title="Contoso Inventory Tool API", version="0.1.0")

# For now: mock repo. Later: swap to AzureSqlInventoryRepository
inventory_service = InventoryService(InventoryRepository())

TOOL_API_KEY = os.getenv("TOOL_API_KEY")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    # If TOOL_API_KEY isn't set, allow (useful for local dev)
    if TOOL_API_KEY and x_api_key != TOOL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


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
    sku: str, qty: int, _: None = Depends(require_api_key)
) -> dict[str, str | int]:
    inventory_service.reserve_item(sku, qty)
    return {"status": "reserved", "sku": sku, "qty": qty}


@app.post("/inventory/receive/{sku}/{qty}")
def receive_item(
    sku: str, qty: int, _: None = Depends(require_api_key)
) -> dict[str, str | int]:
    inventory_service.receive_shipment(sku, qty)
    return {"status": "received", "sku": sku, "qty": qty}
