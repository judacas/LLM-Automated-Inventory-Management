from admin_orchestrator_agent.service import AdminOrchestratorService


def test_inventory_intent_returns_stubbed_inventory_snapshot() -> None:
    svc = AdminOrchestratorService()
    resp = svc.handle_message("Check the inventory")
    assert resp == "Inventory check: SKU-1 has 10 units (in_stock)."


def test_quote_intent_returns_current_delegation_stub() -> None:
    svc = AdminOrchestratorService()
    resp = svc.handle_message("How many quotes do we have?")
    assert resp == "Delegating to Quote Agent (not implemented in my module)."


def test_summary_intent_returns_current_summary_stub() -> None:
    svc = AdminOrchestratorService()
    resp = svc.handle_message("Give me a system summary")
    assert resp == "System summary: inventory + quotes (summary not implemented yet)."


def test_unknown_intent() -> None:
    svc = AdminOrchestratorService()
    resp = svc.handle_message("Tell me something random")
    assert "clarify" in resp.lower()
