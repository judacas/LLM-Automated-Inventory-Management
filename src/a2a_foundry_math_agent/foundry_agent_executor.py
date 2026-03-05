"""AI Foundry Agent Executor for the A2A framework.

Bridges the portal-managed Foundry agent (FoundryMathAgent) with the
A2A server, translating between A2A message parts and the
Responses/Conversations API.
"""

import logging

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
from foundry_agent import FoundryMathAgent

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class FoundryAgentExecutor(AgentExecutor):
    """An AgentExecutor that drives a portal-managed Azure AI Foundry agent."""

    def __init__(self, card: AgentCard):
        self._card = card
        self._agent: FoundryMathAgent | None = None
        self._active_conversations: dict[str, str] = {}  # context_id → conversation_id

    # ------------------------------------------------------------------
    # Lazy initialisation helpers
    # ------------------------------------------------------------------

    async def _get_or_create_agent(self) -> FoundryMathAgent:
        if self._agent is None:
            from foundry_agent import create_foundry_math_agent

            self._agent = await create_foundry_math_agent()
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
            agent = await self._get_or_create_agent()
            conversation_id = await self._get_or_create_conversation(context_id)

            # Let the user know we're working
            await task_updater.update_status(
                TaskState.working,
                message=new_agent_text_message(
                    "Processing your request...", context_id=context_id
                ),
            )

            # Stream the response back, sending deltas as working updates
            full_text = ""
            async for delta in agent.run_conversation_streaming(
                conversation_id, user_message
            ):
                full_text += delta
                await task_updater.update_status(
                    TaskState.working,
                    message=new_agent_text_message(delta, context_id=context_id),
                )

            # Complete the task with the full response
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
        for part in parts:
            part = part.root
            if isinstance(part, TextPart):
                text_parts.append(part.text)
            elif isinstance(part, FilePart):
                if isinstance(part.file, FileWithUri):
                    text_parts.append(f"[File: {part.file.uri}]")
                elif isinstance(part.file, FileWithBytes):
                    text_parts.append(f"[File: {len(part.file.bytes)} bytes]")
            else:
                logger.warning("Unsupported part type: %s", type(part))
        return " ".join(text_parts)

    # ------------------------------------------------------------------
    # A2A entry-points
    # ------------------------------------------------------------------

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        logger.info("Executing request for context: %s", context.context_id)

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        if not context.current_task:
            await updater.submit()

        await updater.start_work()

        await self._process_request(
            context.message.parts,
            context.context_id,
            updater,
        )

        logger.debug("Foundry agent execution completed for %s", context.context_id)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info("Cancelling execution for context: %s", context.context_id)
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.failed(
            message=new_agent_text_message(
                "Task cancelled by user", context_id=context.context_id
            ),
        )

    async def cleanup(self) -> None:
        if self._agent:
            await self._agent.cleanup()
            self._agent = None
        self._active_conversations.clear()
        logger.info("Foundry agent executor cleaned up")


def create_foundry_agent_executor(card: AgentCard) -> FoundryAgentExecutor:
    """Factory function to create a Foundry agent executor."""
    return FoundryAgentExecutor(card)
