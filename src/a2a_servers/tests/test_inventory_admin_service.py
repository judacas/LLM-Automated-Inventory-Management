"""Unit tests for admin-facing inventory service queries."""

from inventory_service.admin_repository import MockInventoryAdminRepository
from inventory_service.admin_service import InventoryAdminService


def test_admin_summary_validates_threshold() -> None:
    svc = InventoryAdminService(MockInventoryAdminRepository())

    try:
        svc.get_summary(low_stock_threshold=0)
        raise AssertionError("Expected ValueError")
    except ValueError:
        assert True


def test_admin_summary_returns_shape() -> None:
    svc = InventoryAdminService(MockInventoryAdminRepository())

    summary = svc.get_summary(low_stock_threshold=5)

    assert summary.total_products >= 0
    assert summary.in_stock_products >= 0
    assert summary.out_of_stock_products >= 0


def test_unavailable_requested_items_validates_inputs() -> None:
    svc = InventoryAdminService(MockInventoryAdminRepository())

    try:
        svc.get_unavailable_requested_items(quote_status="", top_n=10)
        raise AssertionError("Expected ValueError")
    except ValueError:
        assert True

    try:
        svc.get_unavailable_requested_items(quote_status="Pending", top_n=0)
        raise AssertionError("Expected ValueError")
    except ValueError:
        assert True


def test_unavailable_requested_items_returns_items() -> None:
    svc = InventoryAdminService(MockInventoryAdminRepository())

    result = svc.get_unavailable_requested_items(quote_status="Pending", top_n=5)

    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0].shortfall_qty > 0
