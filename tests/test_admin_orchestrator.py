"""Unit tests for the admin orchestrator routing logic."""

from admin_orchestrator_agent.service import AdminOrchestratorService


def test_inventory_intent() -> None:
    svc = AdminOrchestratorService()
    resp = svc.handle_message("Check the inventory")
    assert "Inventory check" in resp


def test_quote_intent() -> None:
    svc = AdminOrchestratorService()
    resp = svc.handle_message("How many quotes do we have?")
    assert "Quote Agent" in resp


def test_system_summary_includes_quote_stub_summary() -> None:
    svc = AdminOrchestratorService()
    resp = svc.handle_message("system summary")
    assert "System summary" in resp
    assert "Quote summary" in resp


def test_unknown_intent() -> None:
    svc = AdminOrchestratorService()
    resp = svc.handle_message("Tell me something random")
    assert "clarify" in resp.lower()
