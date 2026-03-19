from inventory_service.repository import InventoryRepository
from inventory_service.service import InventoryService


class RecordingRepo(InventoryRepository):
    """Minimal test double that records update_quantity calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def update_quantity(self, sku: str, delta: int) -> None:
        self.calls.append((sku, delta))


def test_reserve_item_updates_quantity_with_negative_delta() -> None:
    repo = RecordingRepo()
    svc = InventoryService(repo)

    svc.reserve_item("SKU-1", 2)

    assert repo.calls == [("SKU-1", -2)]


def test_receive_shipment_updates_quantity_with_positive_delta() -> None:
    repo = RecordingRepo()
    svc = InventoryService(repo)

    svc.receive_shipment("SKU-1", 5)

    assert repo.calls == [("SKU-1", 5)]


def test_reserve_item_rejects_zero_quantity() -> None:
    repo = RecordingRepo()
    svc = InventoryService(repo)

    try:
        svc.reserve_item("SKU-1", 0)
        raise AssertionError("Expected ValueError for qty=0")
    except ValueError:
        assert True


def test_reserve_item_rejects_negative_quantity() -> None:
    repo = RecordingRepo()
    svc = InventoryService(repo)

    try:
        svc.reserve_item("SKU-1", -1)
        raise AssertionError("Expected ValueError for qty=-1")
    except ValueError:
        assert True


def test_receive_shipment_rejects_zero_quantity() -> None:
    repo = RecordingRepo()
    svc = InventoryService(repo)

    try:
        svc.receive_shipment("SKU-1", 0)
        raise AssertionError("Expected ValueError for qty=0")
    except ValueError:
        assert True


def test_receive_shipment_rejects_negative_quantity() -> None:
    repo = RecordingRepo()
    svc = InventoryService(repo)

    try:
        svc.receive_shipment("SKU-1", -1)
        raise AssertionError("Expected ValueError for qty=-1")
    except ValueError:
        assert True
