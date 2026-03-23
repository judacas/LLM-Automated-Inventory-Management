from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard
from agent_definition import AgentDefinition
from foundry_agent import create_foundry_agent_backend
from foundry_agent_executor import (
    FoundryAgentExecutor,
    create_foundry_agent_executor,
)
from settings import CompositeAgentSettings, ServerSettings
from skill_router import SkillRoutingAgentExecutor, build_skill_route
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route


@dataclass(frozen=True)
class MountedAgent:
    definition: AgentDefinition
    agent_card: AgentCard


def build_agent_card(definition: AgentDefinition, agent_card_url: str) -> AgentCard:
    return AgentCard(
        name=definition.public_name,
        description=definition.description,
        url=agent_card_url,
        version=definition.version,
        default_input_modes=list(definition.default_input_modes),
        default_output_modes=list(definition.default_output_modes),
        capabilities=AgentCapabilities(streaming=definition.supports_streaming),
        skills=list(definition.skills),
    )


def _build_composite_definition(
    definitions: tuple[AgentDefinition, ...],
    composite_settings: CompositeAgentSettings,
) -> AgentDefinition:
    if not definitions:
        raise ValueError("Composite agent requested but no agent definitions are loaded")

    skills: list = []
    skill_keywords: dict[str, tuple[str, ...]] = {}
    default_input_modes: set[str] = set()
    default_output_modes: set[str] = set()
    supports_streaming = all(definition.supports_streaming for definition in definitions)

    for definition in definitions:
        default_input_modes.update(definition.default_input_modes)
        default_output_modes.update(definition.default_output_modes)

        for skill in definition.skills:
            if skill.id in skill_keywords:
                raise ValueError(
                    "Duplicate skill id detected while building composite agent: "
                    f"{skill.id}"
                )
            skills.append(skill)
            skill_keywords[skill.id] = definition.skill_keywords.get(skill.id, ())

    if not default_input_modes:
        default_input_modes.add("text")
    if not default_output_modes:
        default_output_modes.add("text")

    return AgentDefinition(
        slug=composite_settings.slug,
        source_path=Path(f"<composite:{composite_settings.slug}>"),
        public_name=composite_settings.name,
        description=composite_settings.description,
        version=composite_settings.version,
        health_message=composite_settings.health_message,
        foundry_agent_name="skill-router",
        default_input_modes=tuple(sorted(default_input_modes)),
        default_output_modes=tuple(sorted(default_output_modes)),
        skills=tuple(skills),
        skill_keywords=skill_keywords,
        smoke_test_prompts=(),
        supports_streaming=supports_streaming,
    )


def create_agent_app(
    definition: AgentDefinition,
    settings: ServerSettings,
) -> tuple[Starlette, AgentCard, FoundryAgentExecutor]:
    if settings.project_endpoint is None:
        raise ValueError("Server settings must include project_endpoint")

    agent_card = build_agent_card(
        definition, settings.agent_card_url_for(definition.slug)
    )
    backend_factory = partial(
        create_foundry_agent_backend,
        endpoint=settings.project_endpoint,
        agent_name=definition.foundry_agent_name,
    )
    agent_executor = create_foundry_agent_executor(agent_card, backend_factory)
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
    )
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    routes = a2a_app.routes()

    async def health_check(_: Request) -> PlainTextResponse:
        return PlainTextResponse(definition.health_message)

    routes.append(Route(path="/health", methods=["GET"], endpoint=health_check))

    return Starlette(routes=routes), agent_card, agent_executor


def create_app(
    definitions: tuple[AgentDefinition, ...],
    settings: ServerSettings,
    composite_settings: CompositeAgentSettings | None = None,
) -> tuple[Starlette, tuple[MountedAgent, ...]]:
    mounted_agents: list[MountedAgent] = []
    routes: list[Route | Mount] = []
    cleanup_targets: list[FoundryAgentExecutor] = []
    agent_apps: list[
        tuple[AgentDefinition, Starlette, AgentCard, FoundryAgentExecutor]
    ] = []

    for definition in definitions:
        sub_app, agent_card, agent_executor = create_agent_app(definition, settings)
        agent_apps.append((definition, sub_app, agent_card, agent_executor))

    async def root_index(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "agents": [
                    {
                        "slug": mounted_agent.definition.slug,
                        "name": mounted_agent.agent_card.name,
                        "description": mounted_agent.agent_card.description,
                        "url": mounted_agent.agent_card.url,
                        "health_url": (
                            f"{settings.agent_base_url_for(mounted_agent.definition.slug)}"
                            "/health"
                        ),
                        "source_path": str(mounted_agent.definition.source_path),
                    }
                    for mounted_agent in mounted_agents
                ]
            }
        )

    routes.append(Route(path="/", methods=["GET"], endpoint=root_index))

    for definition, sub_app, agent_card, agent_executor in agent_apps:
        routes.append(
            Mount(
                path=f"/{definition.slug}",
                app=sub_app,
                name=f"agent-{definition.slug}",
            )
        )
        mounted_agents.append(
            MountedAgent(definition=definition, agent_card=agent_card)
        )
        cleanup_targets.append(agent_executor)

    if composite_settings is not None and composite_settings.enabled:
        composite_definition = _build_composite_definition(
            definitions, composite_settings
        )
        composite_card = build_agent_card(
            composite_definition,
            settings.agent_card_url_for(composite_definition.slug),
        )

        skill_routes = [
            build_skill_route(
                skill=skill,
                agent_slug=definition.slug,
                executor=agent_executor,
                configured_keywords=definition.skill_keywords.get(skill.id),
            )
            for definition, _, _, agent_executor in agent_apps
            for skill in definition.skills
        ]
        routing_executor = SkillRoutingAgentExecutor(skill_routes)
        request_handler = DefaultRequestHandler(
            agent_executor=routing_executor,
            task_store=InMemoryTaskStore(),
        )
        composite_a2a = A2AStarletteApplication(
            agent_card=composite_card,
            http_handler=request_handler,
        )
        composite_routes = composite_a2a.routes()

        async def composite_health(_: Request) -> PlainTextResponse:
            return PlainTextResponse(composite_definition.health_message)

        composite_routes.append(
            Route(path="/health", methods=["GET"], endpoint=composite_health)
        )

        routes.append(
            Mount(
                path=f"/{composite_definition.slug}",
                app=Starlette(routes=composite_routes),
                name=f"agent-{composite_definition.slug}",
            )
        )
        mounted_agents.append(
            MountedAgent(definition=composite_definition, agent_card=composite_card)
        )
        cleanup_targets.append(routing_executor)

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        yield
        for agent_executor in cleanup_targets:
            await agent_executor.cleanup()

    return Starlette(routes=routes, lifespan=lifespan), tuple(mounted_agents)
