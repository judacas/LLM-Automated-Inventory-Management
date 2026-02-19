from datetime import date

from inventory_service.models import InventoryItem_v2
from inventory_service.repository import InventoryRepository
from inventory_service.service import InventoryService


class RecordingRepoV2(InventoryRepository):
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def get_item_v2(self, product_id: int) -> InventoryItem_v2:
        if product_id == 999999:
            raise KeyError("Unknown product_id: 999999")
        return InventoryItem_v2(
            product_id=product_id,
            product_name="Test Product",
            quantity=10,
            available_date=date(2026, 1, 15),
            status="in_stock",
        )

    def update_quantity_v2(self, product_id: int, delta: int) -> None:
        self.calls.append((product_id, delta))


def test_get_inventory_by_product_id_validates_positive_id() -> None:
    repo = RecordingRepoV2()
    svc = InventoryService(repo)
    try:
        svc.get_inventory_by_product_id(0)
        raise AssertionError("Expected ValueError for product_id=0")
    except ValueError:
        assert True


def test_reserve_by_product_id_validates_positive_qty() -> None:
    repo = RecordingRepoV2()
    svc = InventoryService(repo)

    try:
        svc.reserve_by_product_id(1, 0)
        raise AssertionError("Expected ValueError for qty=0")
    except ValueError:
        assert True


def test_receive_by_product_id_validates_positive_qty() -> None:
    repo = RecordingRepoV2()
    svc = InventoryService(repo)

    try:
        svc.receive_shipment_by_product_id(1, -1)
        raise AssertionError("Expected ValueError for qty=-1")
    except ValueError:
        assert True


def test_reserve_by_product_id_calls_negative_delta() -> None:
    repo = RecordingRepoV2()
    svc = InventoryService(repo)

    svc.reserve_by_product_id(12, 3)

    assert repo.calls == [(12, -3)]


def test_receive_by_product_id_calls_positive_delta() -> None:
    repo = RecordingRepoV2()
    svc = InventoryService(repo)

    svc.receive_shipment_by_product_id(12, 5)

    assert repo.calls == [(12, 5)]
