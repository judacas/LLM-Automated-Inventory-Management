"""Legacy REST Tool API (FastAPI).

This file is intentionally kept under `legacy/` so it is NOT on the normal
runtime import path (e.g. when running with `PYTHONPATH=src`).

Current direction:
- The MCP server lives under `src/inventory_mcp/` and is served as an ASGI app via
  `inventory_mcp.app:app` with the MCP endpoint mounted at `/mcp`.

Security:
- Protected by `x-api-key` checked against the `TOOL_API_KEY` env var.
"""

import os

from fastapi import Depends, FastAPI, Header, HTTPException

from inventory_service.factory import build_inventory_service

app = FastAPI(title="Contoso Inventory Tool API", version="0.2.0")

inventory_service = build_inventory_service()

TOOL_API_KEY = os.getenv("TOOL_API_KEY")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = TOOL_API_KEY
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="Server misconfigured: TOOL_API_KEY is not set.",
        )

    if x_api_key is None or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


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
