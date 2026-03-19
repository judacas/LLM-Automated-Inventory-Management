"""Quote-agent integration boundary for the admin orchestrator.

Why this module exists:
- The admin orchestrator must answer admin questions about outstanding quotes.
- The quote agent is owned by a different teammate and will be integrated via
  A2A (agent-to-agent) later.

To avoid rewriting `AdminOrchestratorService` when the A2A details arrive, we
introduce a small interface here and default it to a safe stub.

Design rules:
- Default behavior must be deterministic and test-friendly (no network calls).
- When integration details are known, add a real implementation (e.g., A2A).
"""

from __future__ import annotations

import os
from typing import Protocol


class QuoteAgentClient(Protocol):
    """Abstraction for interacting with the quote agent from the admin side."""

    def handle_admin_query(self, message: str) -> str:
        """Handle an admin quote-related query and return a response string."""

    def admin_summary(self) -> str:
        """Return a one-line quote summary suitable for a system dashboard."""


class NullQuoteAgentClient:
    """Default implementation (no quote agent configured).

    This keeps local demos working while making it obvious what is missing.
    """

    def handle_admin_query(self, _message: str) -> str:
        return "Delegating to Quote Agent (not implemented in my module)."

    def admin_summary(self) -> str:
        return "Quote summary: unavailable (quote agent not configured yet)."


def build_quote_agent_client() -> QuoteAgentClient:
    """Factory for selecting the quote-agent integration mode.

    Environment variables:
    - QUOTE_AGENT_MODE:
        - "null" (default): no external integration, return stub responses.

    Future:
    - Add modes like "a2a" once the team standardizes how quote-agent calls work.
    """

    mode = os.getenv("QUOTE_AGENT_MODE", "null").strip().lower()
    if mode in {"", "null", "none"}:
        return NullQuoteAgentClient()

    # Keep behavior safe by default. If someone misconfigures the env var we
    # prefer a clear stub rather than trying a network call.
    return NullQuoteAgentClient()
