from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial

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
from settings import ServerSettings
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
) -> tuple[Starlette, tuple[MountedAgent, ...]]:
    mounted_agents: list[MountedAgent] = []
    executors: list[FoundryAgentExecutor] = []
    routes: list[Route | Mount] = []

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

    for definition in definitions:
        sub_app, agent_card, agent_executor = create_agent_app(definition, settings)
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
        executors.append(agent_executor)

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        yield
        for agent_executor in executors:
            await agent_executor.cleanup()

    return Starlette(routes=routes, lifespan=lifespan), tuple(mounted_agents)
