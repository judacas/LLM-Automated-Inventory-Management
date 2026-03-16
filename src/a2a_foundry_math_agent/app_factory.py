from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import partial

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard
from agent_definition import AgentDefinition
from foundry_agent import create_foundry_agent_backend
from foundry_agent_executor import create_foundry_agent_executor
from settings import ServerSettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route


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


def create_app(
    definition: AgentDefinition,
    settings: ServerSettings,
) -> tuple[Starlette, AgentCard]:
    if settings.project_endpoint is None:
        raise ValueError("Server settings must include project_endpoint")

    agent_card = build_agent_card(definition, settings.agent_card_url)
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

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncGenerator[None, None]:
        yield
        await agent_executor.cleanup()

    return Starlette(routes=routes, lifespan=lifespan), agent_card
