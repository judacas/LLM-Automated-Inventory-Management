"""Generic Foundry-backed AgentExecutor for the A2A framework.

Bridges a portal-managed Foundry backend with the
A2A server, translating between A2A message parts and the
Responses/Conversations API.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    FilePart,
    FileWithBytes,
    FileWithUri,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils.message import new_agent_text_message


class StreamingConversationBackend(Protocol):
    async def create_conversation(self) -> str: ...

    def run_conversation_streaming(
        self, conversation_id: str, user_message: str
    ) -> AsyncIterator[str]: ...

    async def cleanup(self) -> None: ...


logger = logging.getLogger(__name__)


class FoundryAgentExecutor(AgentExecutor):
    """An AgentExecutor that drives a portal-managed Azure AI Foundry agent."""

    def __init__(
        self,
        card: AgentCard,
        backend_factory: Callable[[], Awaitable[StreamingConversationBackend]],
    ):
        self._card = card
        self._backend_factory = backend_factory
        self._agent: StreamingConversationBackend | None = None
        # TODO: _active_conversations grows unboundedly (one entry per context_id, never evicted).
        # This is acceptable for now, but will be replaced once the service is backed by a
        # persistent database, at which point conversation state will be stored there instead.
        self._active_conversations: dict[str, str] = {}  # context_id → conversation_id

    # ------------------------------------------------------------------
    # Lazy initialisation helpers
    # ------------------------------------------------------------------

    async def _get_or_create_agent(self) -> StreamingConversationBackend:
        if self._agent is None:
            self._agent = await self._backend_factory()
        return self._agent

    async def _get_or_create_conversation(self, context_id: str) -> str:
        if context_id not in self._active_conversations:
            agent = await self._get_or_create_agent()
            conversation_id = await agent.create_conversation()
            self._active_conversations[context_id] = conversation_id
            logger.info(
                "Created conversation %s for context %s",
                conversation_id,
                context_id,
            )
        return self._active_conversations[context_id]

    # ------------------------------------------------------------------
    # Request processing
    # ------------------------------------------------------------------

    async def _process_request(
        self,
        message_parts: list[Part],
        context_id: str,
        task_updater: TaskUpdater,
    ) -> None:
        try:
            user_message = self._convert_parts_to_text(message_parts)
            logger.info("💬 User message: %s", user_message)
            conversation_id = await self._get_or_create_conversation(context_id)

            # Let the user know we're working
            await task_updater.update_status(
                TaskState.working,
                message=new_agent_text_message(
                    "Processing your request...", context_id=context_id
                ),
            )

            # Stream the response back, sending deltas as working updates
            full_text_parts = []
            agent = await self._get_or_create_agent()
            async for delta in agent.run_conversation_streaming(
                conversation_id, user_message
            ):
                full_text_parts.append(delta)
                await task_updater.update_status(
                    TaskState.working,
                    message=new_agent_text_message(delta, context_id=context_id),
                )

            # Complete the task with the full response
            full_text = "".join(full_text_parts)
            final_message = full_text or "Task completed."
            logger.info("🤖 Agent response:\n%s", final_message)
            await task_updater.complete(
                message=new_agent_text_message(final_message, context_id=context_id),
            )

        except Exception as e:
            logger.error("Error processing request: %s", e, exc_info=True)
            await task_updater.failed(
                message=new_agent_text_message(f"Error: {e!s}", context_id=context_id),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_parts_to_text(parts: list[Part]) -> str:
        text_parts: list[str] = []
        for part_wrapper in parts:
            inner = part_wrapper.root
            if isinstance(inner, TextPart):
                text_parts.append(inner.text)
            elif isinstance(inner, FilePart):
                if isinstance(inner.file, FileWithUri):
                    text_parts.append(f"[File: {inner.file.uri}]")
                elif isinstance(inner.file, FileWithBytes):
                    text_parts.append(f"[File: {len(inner.file.bytes)} bytes]")
            else:
                logger.warning("Unsupported part type: %s", type(inner))
        return " ".join(text_parts)

    # ------------------------------------------------------------------
    # A2A entry-points
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_ids(context: RequestContext) -> tuple[str, str]:
        """Return non-optional task_id and context_id, generating fallbacks if needed."""
        task_id = context.task_id
        if task_id is None:
            task_id = f"auto-task-{uuid4().hex}"
            logger.warning(
                "RequestContext.task_id was None; generated fallback: %s", task_id
            )
        context_id = context.context_id
        if context_id is None:
            context_id = f"auto-context-{uuid4().hex}"
            logger.warning(
                "RequestContext.context_id was None; generated fallback: %s", context_id
            )
        return task_id, context_id

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        task_id, context_id = self._normalize_ids(context)
        logger.info("Executing request for context: %s", context_id)

        updater = TaskUpdater(event_queue, task_id, context_id)

        if not context.current_task:
            await updater.submit()

        if context.message is None:
            logger.error(
                "RequestContext.message is None for context %s; cannot process.",
                context_id,
            )
            await updater.failed(
                message=new_agent_text_message(
                    "No message provided.", context_id=context_id
                )
            )
            return

        await updater.start_work()
        await self._process_request(context.message.parts, context_id, updater)
        logger.debug("Foundry agent execution completed for %s", context_id)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id, context_id = self._normalize_ids(context)
        logger.info("Cancelling execution for context: %s", context_id)
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.failed(
            message=new_agent_text_message(
                "Task cancelled by user", context_id=context_id
            ),
        )

    async def cleanup(self) -> None:
        if self._agent:
            await self._agent.cleanup()
            self._agent = None
        self._active_conversations.clear()
        logger.info("Foundry agent executor cleaned up")


def create_foundry_agent_executor(
    card: AgentCard,
    backend_factory: Callable[[], Awaitable[StreamingConversationBackend]],
) -> FoundryAgentExecutor:
    """Factory function to create a Foundry agent executor."""
    return FoundryAgentExecutor(card, backend_factory)
