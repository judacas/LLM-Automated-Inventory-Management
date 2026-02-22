import os

from fastapi import Depends, FastAPI, Header, HTTPException

from inventory_service.factory import build_inventory_service

app = FastAPI(title="Contoso Inventory Tool API", version="0.2.0")

# Build service instance at startup
inventory_service = build_inventory_service()

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
            detail="Server misconfigured: TOOL_API_KEY is not set.",
        )

    if x_api_key is None or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


### V2 Endpoints using product_id (new SQL-backed methods) - these will eventually replace the SKU-based ones
@app.get("/v2/inventory/{product_id}")
def get_inventory_v2(
    product_id: int,
    _: None = Depends(require_api_key),
) -> dict[str, str | int]:
    try:
        item = inventory_service.get_inventory_by_product_id(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "product_id": item.product_id,
        "product_name": item.product_name,
        "quantity": item.quantity,
        "status": item.status,
    }


@app.post("/v2/inventory/reserve/{product_id}/{qty}")
def reserve_v2(
    product_id: int,
    qty: int,
    _: None = Depends(require_api_key),
) -> dict[str, str | int]:
    try:
        inventory_service.reserve_by_product_id(product_id, qty)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "reserved", "product_id": product_id, "qty": qty}


@app.post("/v2/inventory/receive/{product_id}/{qty}")
def receive_v2(
    product_id: int,
    qty: int,
    _: None = Depends(require_api_key),
) -> dict[str, str | int]:
    try:
        inventory_service.receive_shipment_by_product_id(product_id, qty)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "received", "product_id": product_id, "qty": qty}


### V1 Endpoints using SKU (legacy)


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
