from inventory_service.repository import InventoryRepository
from inventory_service.service import InventoryService


def test_get_item_availability() -> None:
    service = InventoryService(InventoryRepository())
    item = service.get_item_availability("SKU-1")

    assert item.quantity == 10
    assert item.status == "in_stock"


def test_reserve_item() -> None:
    service = InventoryService(InventoryRepository())
    service.reserve_item("SKU-1", 2)


def test_receive_shipment() -> None:
    service = InventoryService(InventoryRepository())
    service.receive_shipment("SKU-1", 5)
