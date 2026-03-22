"""Tests for `inventory_service.factory` environment-driven wiring.

These are intentionally small and do not require a real database.

Goal:
- Prevent accidental deployments where the mock repository is used when the
  operator intended to run against the real database.
"""

import pytest

from inventory_service.factory import (
    build_inventory_admin_service,
    build_inventory_service,
)


def test_require_sql_without_connection_string_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_SQL_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("INVENTORY_REQUIRE_SQL", "1")

    with pytest.raises(RuntimeError):
        build_inventory_service()

    with pytest.raises(RuntimeError):
        build_inventory_admin_service()


def test_without_require_sql_allows_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZURE_SQL_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("INVENTORY_REQUIRE_SQL", raising=False)

    # Should not raise; defaults to mock/in-memory.
    svc = build_inventory_service()
    admin_svc = build_inventory_admin_service()

    assert svc is not None
    assert admin_svc is not None
