"""GroupRouterExecutor: routes A2A requests to individual agent endpoints.

This executor powers grouped A2A endpoints.  Instead of calling a model
directly it inspects the incoming message for a ``[target:SLUG]`` marker,
validates the slug against the group's allowed member set, and then
forwards the full message to the matching individual agent endpoint via
an outbound A2A call.  The downstream response is streamed back to the
original caller as working-state task updates, and the completed full
text is emitted as the final task result.

See docs/grouped-endpoint-input-contract.md for the expected input format.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    FilePart,
    FileWithBytes,
    FileWithUri,
    MessageSendParams,
    Part,
    SendStreamingMessageRequest,
    TaskState,
    TextPart,
)
from a2a.utils.message import new_agent_text_message

logger = logging.getLogger(__name__)

# Timeout (seconds) for outbound A2A forwarding calls to individual agent endpoints.
_DOWNSTREAM_TIMEOUT_SECONDS = 120

# Regex that matches [target:SLUG] anywhere in the message text.
# Leading and trailing whitespace inside the brackets is accepted.
# The slug may contain lowercase letters, digits, and hyphens.
_TARGET_PATTERN = re.compile(r"\[target:\s*([a-z0-9][a-z0-9-]*)\s*\]", re.IGNORECASE)


class GroupRouterExecutor(AgentExecutor):
    """An AgentExecutor that routes requests to individual agent endpoints.

    Rather than calling a model directly, this executor:
    1. Parses ``[target:SLUG]`` from the incoming message text.
    2. Validates SLUG against the group's allowed ``member_slugs``.
    3. Forwards the request via an outbound A2A streaming call to the
       individual agent endpoint at ``local_base_url_for(slug)``.
    4. Re-emits downstream streaming deltas as working-state updates.
    5. Completes the task with the full concatenated response text.
    """

    def __init__(
        self,
        card: AgentCard,
        member_slugs: frozenset[str],
        local_base_url_for: Callable[[str], str],
    ) -> None:
        self._card = card
        self._member_slugs = member_slugs
        # Factory that returns the local (non-forwarded) base URL for a slug,
        # e.g. http://localhost:10007/quote  — used for self-call routing.
        self._local_base_url_for = local_base_url_for
        # Agent cards are cached after first resolution to avoid repeated fetches.
        self._agent_cards: dict[str, AgentCard] = {}

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_target_slug(text: str) -> str | None:
        """Return the slug from the first ``[target:SLUG]`` marker, or None."""
        match = _TARGET_PATTERN.search(text)
        return match.group(1).lower() if match else None

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parts_to_text(parts: list[Part]) -> str:
        """Convert A2A message parts to a plain-text string."""
        fragments: list[str] = []
        for part_wrapper in parts:
            inner = part_wrapper.root
            if isinstance(inner, TextPart):
                fragments.append(inner.text)
            elif isinstance(inner, FilePart):
                if isinstance(inner.file, FileWithUri):
                    fragments.append(f"[File: {inner.file.uri}]")
                elif isinstance(inner.file, FileWithBytes):
                    fragments.append(f"[File: {len(inner.file.bytes)} bytes]")
            else:
                logger.warning("Unsupported part type: %s", type(inner))
        return " ".join(fragments)

    # ------------------------------------------------------------------
    # Chunk text extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text_from_parts(parts: list[Any]) -> str:
        texts: list[str] = []
        for part in parts:
            inner: Any = part.root if hasattr(part, "root") else part
            if isinstance(inner, dict):
                if inner.get("kind") == "text":
                    texts.append(inner.get("text", ""))
            elif hasattr(inner, "kind") and inner.kind == "text":
                texts.append(inner.text)
        return "\n".join(texts)

    @classmethod
    def _extract_chunk_text(cls, result: Any) -> str:
        """Extract displayable text from any streaming response chunk variant."""
        kind: Any = getattr(result, "kind", None)

        if kind == "status-update":
            status_obj: Any = getattr(result, "status", None)
            if status_obj is not None:
                msg_obj: Any = getattr(status_obj, "message", None)
                if msg_obj is not None:
                    parts: Any = getattr(msg_obj, "parts", [])
                    return cls._extract_text_from_parts(parts)
            return ""

        if kind == "artifact-update":
            artifact_obj: Any = getattr(result, "artifact", None)
            if artifact_obj is not None:
                parts_obj: Any = getattr(artifact_obj, "parts", [])
                return cls._extract_text_from_parts(parts_obj)
            return ""

        if kind == "message":
            parts_obj = getattr(result, "parts", [])
            return cls._extract_text_from_parts(parts_obj)

        # Final Task payload (no "kind", but carries .status)
        status_obj = getattr(result, "status", None)
        if status_obj is not None:
            msg_obj = getattr(status_obj, "message", None)
            if msg_obj is not None:
                parts_obj = getattr(msg_obj, "parts", [])
                return cls._extract_text_from_parts(parts_obj)

        return ""

    # ------------------------------------------------------------------
    # Card resolution (cached)
    # ------------------------------------------------------------------

    async def _resolve_card(
        self, slug: str, base_url: str, httpx_client: httpx.AsyncClient
    ) -> AgentCard:
        """Return the agent card for *slug*, fetching it once and caching it."""
        if slug not in self._agent_cards:
            resolver = A2ACardResolver(
                httpx_client=httpx_client,
                base_url=base_url,
            )
            self._agent_cards[slug] = await resolver.get_agent_card()
            logger.info("Resolved agent card for slug '%s'", slug)
        return self._agent_cards[slug]

    # ------------------------------------------------------------------
    # ID helpers (mirrors FoundryAgentExecutor._normalize_ids)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_ids(context: RequestContext) -> tuple[str, str]:
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

    # ------------------------------------------------------------------
    # A2A entry-points
    # ------------------------------------------------------------------

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        task_id, context_id = self._normalize_ids(context)
        updater = TaskUpdater(event_queue, task_id, context_id)

        if not context.current_task:
            await updater.submit()

        if context.message is None:
            logger.error("RequestContext.message is None for context %s", context_id)
            await updater.failed(
                message=new_agent_text_message(
                    "No message provided.", context_id=context_id
                )
            )
            return

        # --- Parse the target agent slug from the message text ---
        message_text = self._parts_to_text(context.message.parts)
        target_slug = self._parse_target_slug(message_text)

        if target_slug is None:
            logger.warning(
                "Group router: no [target:SLUG] found in message for context %s",
                context_id,
            )
            await updater.failed(
                message=new_agent_text_message(
                    "No target agent specified. "
                    "Include [target:AGENT_SLUG] anywhere in your message. "
                    f"Allowed agents: {sorted(self._member_slugs)}",
                    context_id=context_id,
                )
            )
            return

        # --- Validate that the target slug is in this group's allowed set ---
        if target_slug not in self._member_slugs:
            logger.warning(
                "Group router: unknown target '%s' for context %s (allowed: %s)",
                target_slug,
                context_id,
                sorted(self._member_slugs),
            )
            await updater.failed(
                message=new_agent_text_message(
                    f"Unknown target agent '{target_slug}'. "
                    f"Allowed agents: {sorted(self._member_slugs)}",
                    context_id=context_id,
                )
            )
            return

        await updater.start_work()
        await updater.update_status(
            TaskState.working,
            message=new_agent_text_message(
                f"Routing to agent '{target_slug}'…", context_id=context_id
            ),
        )

        # --- Forward the request to the individual agent endpoint via A2A ---
        target_base_url = self._local_base_url_for(target_slug)
        logger.info(
            "Group router: forwarding context %s to '%s' at %s",
            context_id,
            target_slug,
            target_base_url,
        )

        try:
            async with httpx.AsyncClient(
                timeout=_DOWNSTREAM_TIMEOUT_SECONDS
            ) as httpx_client:
                card = await self._resolve_card(
                    target_slug, target_base_url, httpx_client
                )
                a2a_client = A2AClient(httpx_client=httpx_client, agent_card=card)

                # Stream the downstream response, forwarding each text delta
                # as a working-state update so the caller sees incremental output.
                streaming_request = SendStreamingMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(message=context.message),
                )

                full_parts: list[str] = []
                async for chunk in a2a_client.send_message_streaming(streaming_request):
                    result_obj: Any = getattr(chunk, "root", chunk)
                    result: Any = getattr(result_obj, "result", result_obj)
                    chunk_text = self._extract_chunk_text(result)
                    if chunk_text:
                        full_parts.append(chunk_text)
                        await updater.update_status(
                            TaskState.working,
                            message=new_agent_text_message(
                                chunk_text, context_id=context_id
                            ),
                        )

                full_text = "".join(full_parts) or "Task completed."
                logger.info(
                    "Group router: completed forwarding context %s → '%s' (%d chars)",
                    context_id,
                    target_slug,
                    len(full_text),
                )
                await updater.complete(
                    message=new_agent_text_message(full_text, context_id=context_id)
                )

        except Exception as e:
            logger.error(
                "Group router: error forwarding to '%s' for context %s: %s",
                target_slug,
                context_id,
                e,
                exc_info=True,
            )
            await updater.failed(
                message=new_agent_text_message(
                    f"Routing error while forwarding to '{target_slug}': {e!s}",
                    context_id=context_id,
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id, context_id = self._normalize_ids(context)
        logger.info("Group router: cancelling context %s", context_id)
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.failed(
            message=new_agent_text_message(
                "Task cancelled by user", context_id=context_id
            ),
        )

    async def cleanup(self) -> None:
        # No persistent connections or backend state to clean up;
        # httpx clients are per-request.
        self._agent_cards.clear()
        logger.info("GroupRouterExecutor cleaned up")
