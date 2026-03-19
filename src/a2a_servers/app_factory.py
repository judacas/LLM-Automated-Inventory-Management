from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from a2a_servers.agent_definition import AgentDefinition
from a2a_servers.foundry_agent import create_foundry_agent_backend
from a2a_servers.foundry_agent_executor import (
    FoundryAgentExecutor,
    create_foundry_agent_executor,
)
from a2a_servers.group_definition import GroupDefinition
from a2a_servers.group_router_executor import GroupRouterExecutor
from a2a_servers.settings import ServerSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MountedAgent:
    definition: AgentDefinition | GroupDefinition
    agent_card: AgentCard


def build_agent_card(
    definition: AgentDefinition | GroupDefinition, agent_card_url: str
) -> AgentCard:
    streaming = (
        definition.supports_streaming
        if isinstance(definition, AgentDefinition)
        else True  # Group routers forward streaming responses
    )
    return AgentCard(
        name=definition.public_name,
        description=definition.description,
        url=agent_card_url,
        version=definition.version,
        default_input_modes=list(definition.default_input_modes),
        default_output_modes=list(definition.default_output_modes),
        capabilities=AgentCapabilities(streaming=streaming),
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


def create_group_app(
    definition: GroupDefinition,
    settings: ServerSettings,
) -> tuple[Starlette, AgentCard, GroupRouterExecutor]:
    """Build a Starlette sub-app for a grouped A2A endpoint.

    The resulting app accepts A2A requests, parses ``[target:SLUG]`` from
    the message, and forwards the request to the matching individual agent
    endpoint via an outbound A2A call to ``http://localhost:<port>/<slug>``.
    """
    agent_card = build_agent_card(
        definition, settings.agent_card_url_for(definition.slug)
    )
    # Pass the local-URL factory so the router bypasses any forwarded URL mode
    # and always calls the individual agents on the loopback interface.
    group_executor = GroupRouterExecutor(
        card=agent_card,
        member_slugs=definition.member_slugs,
        local_base_url_for=settings.local_agent_base_url_for,
    )
    request_handler = DefaultRequestHandler(
        agent_executor=group_executor,
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

    return Starlette(routes=routes), agent_card, group_executor


def create_app(
    definitions: tuple[AgentDefinition, ...],
    settings: ServerSettings,
    group_definitions: tuple[GroupDefinition, ...] = (),
) -> tuple[Starlette, tuple[MountedAgent, ...]]:
    # Validate that group member slugs reference known individual agents and
    # that no group slug collides with an individual agent slug.
    agent_slugs = {d.slug for d in definitions}
    for group_def in group_definitions:
        if group_def.slug in agent_slugs:
            raise ValueError(
                f"Group slug '{group_def.slug}' collides with individual agent slug "
                f"'{group_def.slug}'. Choose a different slug for the group."
            )
        for member_slug in group_def.member_slugs:
            if member_slug not in agent_slugs:
                raise ValueError(
                    f"Group '{group_def.slug}' references unknown member slug "
                    f"'{member_slug}'. Known individual agent slugs: "
                    f"{sorted(agent_slugs)}"
                )

    mounted_agents: list[MountedAgent] = []
    executors: list[FoundryAgentExecutor | GroupRouterExecutor] = []
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

    # Mount grouped endpoints after individual agents so self-call routing works.
    for group_def in group_definitions:
        sub_app, agent_card, group_executor = create_group_app(group_def, settings)
        routes.append(
            Mount(
                path=f"/{group_def.slug}",
                app=sub_app,
                name=f"group-{group_def.slug}",
            )
        )
        mounted_agents.append(MountedAgent(definition=group_def, agent_card=agent_card))
        executors.append(group_executor)

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        yield
        for executor in executors:
            await executor.cleanup()

    return Starlette(routes=routes, lifespan=lifespan), tuple(mounted_agents)
