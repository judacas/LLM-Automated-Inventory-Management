from __future__ import annotations

from pathlib import Path

import pytest
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import AgentSkill
from agent_definition import AgentDefinition
from app_factory import create_app
from settings import CompositeAgentSettings, ServerSettings
from skill_router import SkillRoutingAgentExecutor, build_skill_route


class DummyExecutor(AgentExecutor):
    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None

    async def cleanup(self) -> None:
        return None


def _skill(skill_id: str, name: str) -> AgentSkill:
    return AgentSkill(
        id=skill_id,
        name=name,
        description=f"{name} description",
        tags=[],
        examples=[],
    )


def test_select_route_matches_configured_keyword() -> None:
    inventory_route = build_skill_route(
        skill=_skill("inventory", "Inventory"),
        agent_slug="inventory",
        executor=DummyExecutor("inventory"),
        configured_keywords=("inventory",),
    )
    quote_route = build_skill_route(
        skill=_skill("quote", "Quote"),
        agent_slug="quote",
        executor=DummyExecutor("quote"),
        configured_keywords=("quote",),
    )

    router = SkillRoutingAgentExecutor((inventory_route, quote_route))
    selected = router._select_route("Need inventory status for laptops")

    assert selected.agent_slug == "inventory"
    assert selected.skill.id == "inventory"


def test_select_route_falls_back_to_first_route() -> None:
    inventory_route = build_skill_route(
        skill=_skill("inventory", "Inventory"),
        agent_slug="inventory",
        executor=DummyExecutor("inventory"),
        configured_keywords=("inventory",),
    )
    quote_route = build_skill_route(
        skill=_skill("quote", "Quote"),
        agent_slug="quote",
        executor=DummyExecutor("quote"),
        configured_keywords=("quote",),
    )

    router = SkillRoutingAgentExecutor((inventory_route, quote_route))
    selected = router._select_route("No obvious keywords here")

    assert selected.agent_slug == "inventory"
    assert selected.skill.id == "inventory"


def _definition(slug: str, skill_id: str) -> AgentDefinition:
    skill = _skill(skill_id, f"{skill_id.title()} Skill")
    return AgentDefinition(
        slug=slug,
        source_path=Path(f"/tmp/{slug}.toml"),
        public_name=f"{slug.title()} Agent",
        description="desc",
        version="1.0.0",
        health_message="ok",
        foundry_agent_name=f"{slug}-foundry",
        default_input_modes=("text",),
        default_output_modes=("text",),
        skills=(skill,),
        skill_keywords={skill.id: ()},
        smoke_test_prompts=(),
        supports_streaming=True,
    )


def test_composite_duplicate_skill_ids_raise() -> None:
    settings = ServerSettings(
        host="localhost",
        port=10007,
        url_mode="local",
        forwarded_base_url="",
        log_level_name="INFO",
        project_endpoint="https://example.test",
    )
    composite_settings = CompositeAgentSettings(
        slug="combined",
        name="Combined Agent",
        description="desc",
        version="1.0.0",
        health_message="healthy",
    )
    definitions = (
        _definition("one", "shared"),
        _definition("two", "shared"),
    )

    with pytest.raises(ValueError, match="Duplicate skill id"):
        create_app(definitions, settings, composite_settings)
