"""Composite AgentExecutor that routes requests across multiple Foundry backends.

The executor selects the target Foundry backend by scanning the user's message
for regex keyword patterns defined in the composite config.
Exactly one member must match on the first message of a context.

Routing is *sticky per context*: once a context (conversation) is mapped to a
member, all subsequent messages in that context continue to use the same backend
so that conversation history is preserved.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentCard, Part, TaskState
from a2a.utils.message import new_agent_text_message
from foundry_agent_executor import (
    FoundryAgentExecutor,
    StreamingConversationBackend,
)

logger = logging.getLogger(__name__)


@dataclass
class CompositeMemberBackend:
    """Pairs a backend factory with the compiled keyword patterns that select it."""

    backend_factory: Callable[[], Awaitable[StreamingConversationBackend]]
    keyword_patterns: tuple[re.Pattern[str], ...]
    route_label: str


class CompositeAgentExecutor(AgentExecutor):
    """Routes each request to the Foundry backend whose keywords match the message.

    Routing is evaluated on the first message of a context and then locked in for
    the remainder of that context so that conversation threads remain coherent.
    """

    def __init__(
        self,
        card: AgentCard,
        members: list[CompositeMemberBackend],
    ) -> None:
        if not members:
            raise ValueError("CompositeAgentExecutor requires at least one member")
        self._card = card
        self._members = members
        self._agents: list[StreamingConversationBackend | None] = [None] * len(members)
        # context_id → member index (routing locked on first message)
        self._context_routes: dict[str, int] = {}
        # context_id → Foundry conversation_id
        self._active_conversations: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route_message(self, message: str) -> int:
        """Return the unique member index selected by keyword matching.

        Raises ``ValueError`` when zero members match or when multiple members
        match so callers can return an explicit routing error to the requester.
        """
        matching_indices: list[int] = []
        for index, member in enumerate(self._members):
            for pattern in member.keyword_patterns:
                if pattern.search(message):
                    matching_indices.append(index)
                    logger.debug(
                        "Message matched member %d via pattern %r",
                        index,
                        pattern.pattern,
                    )
                    break

        if len(matching_indices) == 1:
            return matching_indices[0]

        route_hints = [f"Route to {member.route_label}" for member in self._members]
        hints_text = "; ".join(route_hints)

        if not matching_indices:
            logger.warning("No keyword pattern matched message %r", message[:120])
            raise ValueError(
                "Composite endpoint requires the target agent to be specified. "
                f"No routing pattern matched. Use one of: {hints_text}."
            )

        matched_routes = ", ".join(
            self._members[index].route_label for index in matching_indices
        )
        raise ValueError(
            "Composite endpoint requires exactly one target agent. "
            f"Message matched multiple routes: {matched_routes}. "
            f"Use only one route prefix. Valid options: {hints_text}."
        )

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    async def _get_or_create_agent(
        self, member_idx: int
    ) -> StreamingConversationBackend:
        if self._agents[member_idx] is None:
            self._agents[member_idx] = await self._members[member_idx].backend_factory()
        agent = self._agents[member_idx]
        assert agent is not None  # guaranteed by the initialisation block above
        return agent

    async def _get_or_create_conversation(
        self, context_id: str, member_idx: int
    ) -> str:
        if context_id not in self._active_conversations:
            agent = await self._get_or_create_agent(member_idx)
            conversation_id = await agent.create_conversation()
            self._active_conversations[context_id] = conversation_id
            logger.info(
                "Created conversation %s for context %s (member %d)",
                conversation_id,
                context_id,
                member_idx,
            )
        return self._active_conversations[context_id]

    # ------------------------------------------------------------------
    # Request processing
    # ------------------------------------------------------------------

    async def _process_request(
        self,
        message_parts: Sequence[Part],
        context_id: str,
        task_updater: TaskUpdater,
    ) -> None:
        try:
            user_message = FoundryAgentExecutor._convert_parts_to_text(
                list(message_parts)
            )
            logger.info("💬 User message: %s", user_message)

            # Determine (and lock in) routing for this context
            if context_id not in self._context_routes:
                member_idx = self._route_message(user_message)
                self._context_routes[context_id] = member_idx
                logger.info("Routing context %s to member %d", context_id, member_idx)
            else:
                member_idx = self._context_routes[context_id]

            conversation_id = await self._get_or_create_conversation(
                context_id, member_idx
            )

            await task_updater.update_status(
                TaskState.working,
                message=new_agent_text_message(
                    "Processing your request...", context_id=context_id
                ),
            )

            full_text_parts: list[str] = []
            agent = await self._get_or_create_agent(member_idx)
            async for delta in agent.run_conversation_streaming(
                conversation_id, user_message
            ):
                full_text_parts.append(delta)
                await task_updater.update_status(
                    TaskState.working,
                    message=new_agent_text_message(delta, context_id=context_id),
                )

            full_text = "".join(full_text_parts)
            final_message = full_text or "Task completed."
            logger.info("🤖 Agent response:\n%s", final_message)
            await task_updater.complete(
                message=new_agent_text_message(final_message, context_id=context_id),
            )

        except Exception as exc:
            logger.error("Error processing request: %s", exc, exc_info=True)
            await task_updater.failed(
                message=new_agent_text_message(
                    f"Error: {exc!s}", context_id=context_id
                ),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_ids(context: RequestContext) -> tuple[str, str]:
        task_id = context.task_id
        if task_id is None:
            task_id = f"auto-task-{uuid4().hex}"
            logger.warning(
                "RequestContext.task_id was None; generated fallback: %s",
                task_id,
            )
        context_id = context.context_id
        if context_id is None:
            context_id = f"auto-context-{uuid4().hex}"
            logger.warning(
                "RequestContext.context_id was None; generated fallback: %s",
                context_id,
            )
        return task_id, context_id

    # ------------------------------------------------------------------
    # A2A entry-points
    # ------------------------------------------------------------------

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        task_id, context_id = self._normalize_ids(context)
        logger.info("Executing composite request for context: %s", context_id)

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
        logger.debug("Composite agent execution completed for %s", context_id)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id, context_id = self._normalize_ids(context)
        logger.info("Cancelling composite execution for context: %s", context_id)
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.failed(
            message=new_agent_text_message(
                "Task cancelled by user", context_id=context_id
            ),
        )

    async def cleanup(self) -> None:
        for agent in self._agents:
            if agent is not None:
                await agent.cleanup()
        self._agents = [None] * len(self._members)
        self._context_routes.clear()
        self._active_conversations.clear()
        logger.info("Composite agent executor cleaned up")
