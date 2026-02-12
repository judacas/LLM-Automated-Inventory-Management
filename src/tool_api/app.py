from fastapi import FastAPI

from inventory_agent.repository import InventoryRepository
from inventory_agent.service import InventoryService

app = FastAPI(title="Contoso Inventory Tool API", version="0.1.0")

# For now: mock repo. Later: swap to AzureSqlInventoryRepository
inventory_service = InventoryService(InventoryRepository())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/inventory/get_item/{sku}")
def get_item(sku: str) -> dict[str, str | int | None]:
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
def reserve_item(sku: str, qty: int) -> dict[str, str | int]:
    inventory_service.reserve_item(sku, qty)
    return {"status": "reserved", "sku": sku, "qty": qty}


@app.post("/inventory/receive/{sku}/{qty}")
def receive_item(sku: str, qty: int) -> dict[str, str | int]:
    inventory_service.receive_shipment(sku, qty)
    return {"status": "received", "sku": sku, "qty": qty}
