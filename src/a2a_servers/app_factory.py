from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from a2a_servers.agent_definition import AgentDefinition
from a2a_servers.foundry_agent import create_foundry_agent_backend
from a2a_servers.foundry_agent_executor import (
    FoundryAgentExecutor,
    create_foundry_agent_executor,
)
from a2a_servers.settings import ServerSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MountedAgent:
    definition: AgentDefinition
    agent_card: AgentCard


class SwappableAgentApp:
    """Thin ASGI wrapper whose inner Starlette app can be hot-swapped on reload.

    The dashboard ``/dashboard/api/reload`` endpoint replaces ``_inner`` with a
    freshly-built Starlette application while the server keeps running.
    """

    def __init__(self, inner: Starlette) -> None:
        self._inner: ASGIApp = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._inner(scope, receive, send)

    def swap(self, new_inner: Starlette) -> None:
        """Replace the inner app atomically."""
        self._inner = new_inner


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


def _build_agent_starlette(
    definitions: tuple[AgentDefinition, ...],
    settings: ServerSettings,
    executors_out: list[FoundryAgentExecutor],
) -> tuple[Starlette, tuple[MountedAgent, ...]]:
    """Build the inner Starlette app for all agents and populate *executors_out*.

    This is extracted so that the dashboard reload can call it independently
    without needing to rebuild the outer app (dashboard, lifespan, etc.).
    """
    mounted_agents: list[MountedAgent] = []
    routes: list[Route | Mount] = []

    async def root_index(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "agents": [
                    {
                        "slug": ma.definition.slug,
                        "name": ma.agent_card.name,
                        "description": ma.agent_card.description,
                        "url": ma.agent_card.url,
                        "health_url": (
                            f"{settings.agent_base_url_for(ma.definition.slug)}/health"
                        ),
                        "source_path": str(ma.definition.source_path),
                    }
                    for ma in mounted_agents
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
        executors_out.append(agent_executor)

    return Starlette(routes=routes), tuple(mounted_agents)


def create_app(
    definitions: tuple[AgentDefinition, ...],
    settings: ServerSettings,
    config_dir: Path | None = None,
) -> tuple[Starlette, tuple[MountedAgent, ...]]:
    """Create the top-level ASGI application.

    Parameters
    ----------
    definitions:
        Agent definitions to mount.
    settings:
        Server settings (host, port, URLs, Azure endpoint, …).
    config_dir:
        When supplied, the developer dashboard is mounted at ``/dashboard``.
        Pass the same directory used to load *definitions* so the dashboard
        can read, write, and reload TOML files at runtime.
    """
    # Mutable executor list — shared between the lifespan and the reload callback
    # so that cleanup always covers the *current* set of executors.
    executors: list[FoundryAgentExecutor] = []

    inner, initial_mounted = _build_agent_starlette(definitions, settings, executors)
    swappable = SwappableAgentApp(inner)

    outer_routes: list[Route | Mount] = []

    # --- Dashboard (optional) ------------------------------------------------
    if config_dir is not None:
        from a2a_servers.dashboard.api import create_dashboard_routes
        from a2a_servers.dashboard.ui import create_ui_routes

        async def _on_reload(new_definitions: tuple[AgentDefinition, ...]) -> None:
            """Clean up old executors and hot-swap the inner agent app."""
            for ex in list(executors):
                await ex.cleanup()
            executors.clear()

            new_inner, _ = _build_agent_starlette(new_definitions, settings, executors)
            swappable.swap(new_inner)
            logger.info(
                "Hot-reloaded %d agent(s): %s",
                len(new_definitions),
                [d.slug for d in new_definitions],
            )

        api_routes = create_dashboard_routes(config_dir, settings, _on_reload)
        ui_routes = create_ui_routes()

        outer_routes.append(Mount("/dashboard/api", app=Starlette(routes=api_routes)))
        outer_routes.append(Mount("/dashboard", app=Starlette(routes=ui_routes)))

    # --- Swappable agent router (catches everything else) --------------------
    outer_routes.append(Mount("/", app=swappable))

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        yield
        for agent_executor in list(executors):
            await agent_executor.cleanup()

    return Starlette(routes=outer_routes, lifespan=lifespan), initial_mounted
