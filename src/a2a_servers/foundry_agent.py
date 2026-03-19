"""Reusable Azure AI Foundry backend using the azure-ai-projects SDK.

Uses the Responses/Conversations API to interact with a portal-managed
agent rather than creating agents in code.

Uses the **async** SDK (``azure.ai.projects.aio``) so that network I/O
never blocks the asyncio event-loop that powers the A2A server.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)


class FoundryAgentBackend:
    """Wrapper around a portal-managed Azure AI Foundry agent.

    The agent (and its tools, such as Code Interpreter) are configured
    via the Foundry portal.  This class only references the agent by
    name and drives conversations through the Responses API.
    """

    def __init__(self, *, endpoint: str, agent_name: str) -> None:
        self.endpoint = endpoint
        self.agent_name = agent_name
        self.credential = DefaultAzureCredential()

        # Clients – initialised lazily in ``initialize``
        self._project_client: AIProjectClient | None = None
        self._openai_client: Any | None = None

        # conversation_id tracking
        self._conversations: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open SDK clients and verify the agent exists."""
        if self._project_client is not None:
            return

        self._project_client = AIProjectClient(
            endpoint=self.endpoint,
            credential=self.credential,
        )
        self._openai_client = self._project_client.get_openai_client()

        # Verify the portal-managed agent is reachable
        agent = await self._project_client.agents.get(agent_name=self.agent_name)
        logger.info(
            "Connected to agent %s (id=%s, latest_version=%s)",
            agent.name,
            agent.id,
            agent.versions.latest.version,
        )

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def create_conversation(self) -> str:
        """Create a new conversation and return its id."""
        assert self._openai_client is not None  # noqa: S101
        conversation = await self._openai_client.conversations.create()
        if not conversation.id:
            raise ValueError("Failed to create conversation: no ID returned")
        self._conversations[conversation.id] = False
        logger.info("Created conversation %s", conversation.id)
        return str(conversation.id)

    # ------------------------------------------------------------------
    # Non-streaming response
    # ------------------------------------------------------------------

    async def run_conversation(self, conversation_id: str, user_message: str) -> str:
        """Send *user_message* and return the agent's text reply."""
        assert self._openai_client is not None  # noqa: S101

        # Add the user message to the conversation
        await self._openai_client.conversations.items.create(
            conversation_id=conversation_id,
            items=[
                {
                    "type": "message",
                    "role": "user",
                    "content": user_message,
                }
            ],
        )
        self._conversations[conversation_id] = True

        # Get the agent's response (single call – no polling required)
        response = await self._openai_client.responses.create(
            conversation=conversation_id,
            extra_body={
                "agent_reference": {
                    "name": self.agent_name,
                    "type": "agent_reference",
                }
            },
        )

        text = response.output_text or ""
        logger.debug("Agent response (%d chars): %s…", len(text), text[:120])
        return text

    # ------------------------------------------------------------------
    # Streaming response
    # ------------------------------------------------------------------

    async def run_conversation_streaming(
        self, conversation_id: str, user_message: str
    ) -> AsyncIterator[str]:
        """Send *user_message* and yield text deltas as they arrive."""
        assert self._openai_client is not None  # noqa: S101

        # Add the user message to the conversation
        await self._openai_client.conversations.items.create(
            conversation_id=conversation_id,
            items=[
                {
                    "type": "message",
                    "role": "user",
                    "content": user_message,
                }
            ],
        )
        self._conversations[conversation_id] = True

        # Stream the response – await the coroutine first, then use the
        # resulting AsyncStream as an async context-manager.
        async with await self._openai_client.responses.create(
            conversation=conversation_id,
            extra_body={
                "agent_reference": {
                    "name": self.agent_name,
                    "type": "agent_reference",
                }
            },
            stream=True,
        ) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield event.delta

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a single conversation."""
        if self._openai_client is None:
            return
        try:
            await self._openai_client.conversations.delete(
                conversation_id=conversation_id
            )
            self._conversations.pop(conversation_id, None)
            logger.info("Deleted conversation %s", conversation_id)
        except Exception:
            logger.warning(
                "Failed to delete conversation %s",
                conversation_id,
                exc_info=True,
            )

    async def cleanup(self) -> None:
        """Close SDK clients.  Does NOT delete the portal-managed agent."""
        for cid in list(self._conversations):
            await self.delete_conversation(cid)

        if self._openai_client is not None:
            try:
                await self._openai_client.close()
            except Exception:
                logger.exception("Error closing OpenAI client")
            self._openai_client = None

        if self._project_client is not None:
            try:
                await self._project_client.close()
            except Exception:
                logger.exception("Error closing project client")
            self._project_client = None

        if self.credential is not None:
            try:
                await self.credential.close()
            except Exception:
                logger.exception("Error closing credential")
        self.credential = DefaultAzureCredential()
        logger.info("FoundryAgentBackend cleaned up")


async def create_foundry_agent_backend(
    *, endpoint: str, agent_name: str
) -> FoundryAgentBackend:
    """Factory: create, initialise, and return a ``FoundryAgentBackend``."""
    agent = FoundryAgentBackend(endpoint=endpoint, agent_name=agent_name)
    await agent.initialize()
    return agent
