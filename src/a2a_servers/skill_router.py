from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Sequence

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import AgentSkill
from foundry_agent_executor import FoundryAgentExecutor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillRoute:
    skill: AgentSkill
    agent_slug: str
    executor: AgentExecutor
    keywords: tuple[str, ...]
    patterns: tuple[re.Pattern[str], ...]


def _normalize_keywords(
    configured: Sequence[str] | None, skill: AgentSkill
) -> tuple[str, ...]:
    """Build a de-duplicated keyword list for a skill."""
    keywords: list[str] = []
    seen: set[str] = set()

    for candidate in configured or []:
        normalized = candidate.strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        keywords.append(normalized)

    if not keywords:
        defaults = [skill.id, skill.name]
        defaults.extend(skill.tags)
        for item in defaults:
            normalized = item.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            keywords.append(normalized)

    return tuple(keywords)


def _compile_patterns(keywords: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    if not keywords:
        return ()
    return tuple(
        re.compile(rf"\b{re.escape(keyword)}\b", flags=re.IGNORECASE)
        for keyword in keywords
    )


def build_skill_route(
    *,
    skill: AgentSkill,
    agent_slug: str,
    executor: AgentExecutor,
    configured_keywords: Sequence[str] | None = None,
) -> SkillRoute:
    keywords = _normalize_keywords(configured_keywords, skill)
    patterns = _compile_patterns(keywords)
    return SkillRoute(
        skill=skill,
        agent_slug=agent_slug,
        executor=executor,
        keywords=keywords,
        patterns=patterns,
    )


class SkillRoutingAgentExecutor(AgentExecutor):
    """Preprocesses the request and routes to a target executor based on keywords."""

    def __init__(self, routes: Sequence[SkillRoute]) -> None:
        if not routes:
            raise ValueError("SkillRoutingAgentExecutor requires at least one route")
        self._routes: tuple[SkillRoute, ...] = tuple(routes)
        self._fallback: SkillRoute = routes[0]

    def _select_route(self, message_text: str) -> SkillRoute:
        for route in self._routes:
            if not route.patterns:
                continue
            if any(pattern.search(message_text) for pattern in route.patterns):
                return route
        logger.info(
            "No routing keyword matched; falling back to %s for skill %s",
            self._fallback.agent_slug,
            self._fallback.skill.id,
        )
        return self._fallback

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        text = ""
        if context.message is not None:
            text = FoundryAgentExecutor._convert_parts_to_text(context.message.parts)

        route = self._select_route(text)
        logger.info(
            "Routing request to agent %s via skill %s",
            route.agent_slug,
            route.skill.id,
        )
        await route.executor.execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = ""
        if context.message is not None:
            text = FoundryAgentExecutor._convert_parts_to_text(context.message.parts)
        route = self._select_route(text)
        await route.executor.cancel(context, event_queue)

    async def cleanup(self) -> None:  # pragma: no cover - no-op wrapper
        # Underlying executors are cleaned up by the app lifecycle.
        return None
