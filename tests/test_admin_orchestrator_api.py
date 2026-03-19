"""API-level tests for the Admin Orchestrator FastAPI app.

Why these exist:
- The UI will call the orchestrator over HTTP, so we want at least one test that
  validates the basic request/response contract.
- These tests do NOT require the Inventory MCP server to be running because the
  client wrapper supports an in-process fallback by default.
"""

from fastapi.testclient import TestClient

from admin_orchestrator_agent.app import create_app


def test_health_ok() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_contract_ok() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.post("/chat", json={"message": "Check inventory"})
    assert resp.status_code == 200

    payload = resp.json()
    assert "response" in payload
    assert isinstance(payload["response"], str)
    assert payload["response"]


def test_chat_requires_message() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.post("/chat", json={})
    assert resp.status_code == 422
