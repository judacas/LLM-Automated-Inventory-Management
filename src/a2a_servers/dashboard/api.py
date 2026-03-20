"""Dashboard API routes: CRUD for agent TOML files and a reload endpoint.

All handlers return JSON.  Routes are created via ``create_dashboard_routes``
and mounted by ``app_factory.create_app`` under ``/dashboard/api``.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a_servers.agent_definition import (
    AGENT_CONFIG_GLOB,
    AgentDefinition,
    load_agent_definition,
    load_agent_definitions,
)
from a2a_servers.dashboard.toml_writer import agent_config_to_toml
from a2a_servers.settings import ServerSettings

logger = logging.getLogger(__name__)

# Type alias for the async reload callback supplied by app_factory.
OnReloadFn = Callable[[tuple[AgentDefinition, ...]], Awaitable[None]]


# ---------------------------------------------------------------------------
# Serialisation helper
# ---------------------------------------------------------------------------


def _definition_to_dict(defn: AgentDefinition) -> dict[str, object]:
    """Flatten an ``AgentDefinition`` to a JSON-serialisable dict."""
    return {
        "slug": defn.slug,
        "filename": defn.source_path.name,
        "source_path": str(defn.source_path),
        "public_name": defn.public_name,
        "description": defn.description,
        "version": defn.version,
        "health_message": defn.health_message,
        "foundry_agent_name": defn.foundry_agent_name,
        "default_input_modes": list(defn.default_input_modes),
        "default_output_modes": list(defn.default_output_modes),
        "supports_streaming": defn.supports_streaming,
        "smoke_test_prompts": list(defn.smoke_test_prompts),
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "tags": list(s.tags or []),
                "examples": list(s.examples or []),
            }
            for s in defn.skills
        ],
        # The [a2a] / [foundry] / [smoke_tests] shape that the PUT/POST
        # endpoints accept — pre-filled for the UI's edit form.
        "config": {
            "a2a": {
                "name": defn.public_name,
                "description": defn.description,
                "version": defn.version,
                "health_message": defn.health_message,
                "default_input_modes": list(defn.default_input_modes),
                "default_output_modes": list(defn.default_output_modes),
                "streaming": defn.supports_streaming,
            },
            "foundry": {"agent_name": defn.foundry_agent_name},
            "smoke_tests": {"prompts": list(defn.smoke_test_prompts)},
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "tags": list(s.tags or []),
                    "examples": list(s.examples or []),
                }
                for s in defn.skills
            ],
        },
    }


# ---------------------------------------------------------------------------
# TOML validation helper
# ---------------------------------------------------------------------------


def _validate_config_dict(config: dict[str, object]) -> str:
    """Write *config* to a temp file and validate it via ``load_agent_definition``.

    Returns the rendered TOML text on success.
    Raises ``ValueError`` on validation failure.
    Raises ``KeyError`` / ``TypeError`` if the config shape is wrong.
    """
    toml_text = agent_config_to_toml(config)

    # Write to a temp file whose name ends with ``_agent.toml`` so that the
    # slug-derivation logic inside load_agent_definition works correctly.
    with tempfile.NamedTemporaryFile(
        suffix="_agent.toml",
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=tempfile.gettempdir(),
    ) as tmp:
        tmp.write(toml_text)
        tmp_path = Path(tmp.name)

    try:
        load_agent_definition(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return toml_text


# ---------------------------------------------------------------------------
# Route factory
# ---------------------------------------------------------------------------


def create_dashboard_routes(
    config_dir: Path,
    settings: ServerSettings,
    on_reload: OnReloadFn,
) -> list[Route]:
    """Return a list of Starlette ``Route`` objects for the dashboard API.

    Parameters
    ----------
    config_dir:
        Directory that contains ``*_agent.toml`` files.
    settings:
        Server settings (used to know whether Azure is configured so we can
        rebuild live routes on reload).
    on_reload:
        Async callback invoked with the new set of ``AgentDefinition`` objects
        when a reload is requested.  Supplied by ``app_factory`` so that the
        swappable agent app can be hot-swapped without a circular import.
    """

    # ------------------------------------------------------------------
    # GET /api/agents  — list all configured agents
    # ------------------------------------------------------------------

    async def list_agents(_: Request) -> JSONResponse:
        try:
            definitions = load_agent_definitions(str(config_dir))
            return JSONResponse([_definition_to_dict(d) for d in definitions])
        except FileNotFoundError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error listing agents")
            return JSONResponse({"error": str(exc)}, status_code=500)

    # ------------------------------------------------------------------
    # GET /api/agents/{slug}  — get one agent
    # ------------------------------------------------------------------

    async def get_agent(request: Request) -> JSONResponse:
        slug = request.path_params["slug"]
        try:
            definitions = load_agent_definitions(str(config_dir))
        except FileNotFoundError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error loading agents")
            return JSONResponse({"error": str(exc)}, status_code=500)

        for defn in definitions:
            if defn.slug == slug:
                return JSONResponse(_definition_to_dict(defn))
        return JSONResponse({"error": f"Agent '{slug}' not found"}, status_code=404)

    # ------------------------------------------------------------------
    # POST /api/agents  — create a new agent TOML file
    # ------------------------------------------------------------------

    async def create_agent(request: Request) -> JSONResponse:
        try:
            body: object = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "Request body must be a JSON object"}, status_code=400
            )

        filename: object = body.get("filename", "")
        if not isinstance(filename, str) or not filename.strip():
            return JSONResponse({"error": "'filename' is required"}, status_code=400)

        filename = filename.strip()
        if not filename.endswith(".toml"):
            filename += ".toml"

        # Warn if the filename doesn't follow the naming convention but allow it
        glob_suffix = AGENT_CONFIG_GLOB.lstrip("*")  # "_agent.toml"
        if not filename.endswith(glob_suffix):
            logger.warning(
                "New agent file '%s' does not match the glob '%s'; "
                "it will not be auto-discovered.",
                filename,
                AGENT_CONFIG_GLOB,
            )

        target = config_dir / filename
        if target.exists():
            return JSONResponse(
                {"error": f"File already exists: {filename}"}, status_code=409
            )

        config: object = body.get("config")
        if not isinstance(config, dict):
            return JSONResponse(
                {"error": "'config' object is required (a2a, foundry, skills, …)"},
                status_code=400,
            )

        try:
            toml_text = _validate_config_dict(config)
        except (KeyError, TypeError) as exc:
            return JSONResponse(
                {"error": f"Invalid config shape: {exc}"}, status_code=400
            )
        except ValueError as exc:
            return JSONResponse({"error": f"Validation failed: {exc}"}, status_code=422)

        target.write_text(toml_text, encoding="utf-8")
        try:
            defn = load_agent_definition(target)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"error": f"Saved but could not reload: {exc}"}, status_code=500
            )

        logger.info("Dashboard: created agent '%s' in %s", defn.slug, target)
        return JSONResponse(_definition_to_dict(defn), status_code=201)

    # ------------------------------------------------------------------
    # PUT /api/agents/{slug}  — update an existing agent TOML file
    # ------------------------------------------------------------------

    async def update_agent(request: Request) -> JSONResponse:
        slug = request.path_params["slug"]

        try:
            body: object = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "Request body must be a JSON object"}, status_code=400
            )

        # Find existing definition
        try:
            definitions = load_agent_definitions(str(config_dir))
        except FileNotFoundError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)}, status_code=500)

        existing = next((d for d in definitions if d.slug == slug), None)
        if existing is None:
            return JSONResponse({"error": f"Agent '{slug}' not found"}, status_code=404)

        config: object = body.get("config")
        if not isinstance(config, dict):
            return JSONResponse(
                {"error": "'config' object is required"},
                status_code=400,
            )

        try:
            toml_text = _validate_config_dict(config)
        except (KeyError, TypeError) as exc:
            return JSONResponse(
                {"error": f"Invalid config shape: {exc}"}, status_code=400
            )
        except ValueError as exc:
            return JSONResponse({"error": f"Validation failed: {exc}"}, status_code=422)

        existing.source_path.write_text(toml_text, encoding="utf-8")
        try:
            defn = load_agent_definition(existing.source_path)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"error": f"Saved but could not reload: {exc}"}, status_code=500
            )

        logger.info(
            "Dashboard: updated agent '%s' in %s", defn.slug, existing.source_path
        )
        return JSONResponse(_definition_to_dict(defn))

    # ------------------------------------------------------------------
    # DELETE /api/agents/{slug}  — remove an agent TOML file
    # ------------------------------------------------------------------

    async def delete_agent(request: Request) -> JSONResponse:
        slug = request.path_params["slug"]

        try:
            definitions = load_agent_definitions(str(config_dir))
        except FileNotFoundError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)}, status_code=500)

        existing = next((d for d in definitions if d.slug == slug), None)
        if existing is None:
            return JSONResponse({"error": f"Agent '{slug}' not found"}, status_code=404)

        existing.source_path.unlink()
        logger.info("Dashboard: deleted agent '%s' (%s)", slug, existing.source_path)
        return JSONResponse({"deleted": slug})

    # ------------------------------------------------------------------
    # POST /api/reload  — validate TOMLs and hot-swap the agent router
    # ------------------------------------------------------------------

    async def reload_agents(_: Request) -> JSONResponse:
        try:
            definitions = load_agent_definitions(str(config_dir))
        except FileNotFoundError as exc:
            return JSONResponse(
                {
                    "error": str(exc),
                    "hint": "No valid agent TOML files found; add at least one agent first.",
                },
                status_code=422,
            )
        except ValueError as exc:
            return JSONResponse(
                {"error": f"Agent config validation error: {exc}"},
                status_code=422,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error loading agent definitions during reload")
            return JSONResponse({"error": str(exc)}, status_code=500)

        # Try to rebuild and hot-swap the live routing table.
        # This requires AZURE_AI_PROJECT_ENDPOINT; if it is absent, we skip
        # the hot-swap and just return the validated agent list.
        if settings.project_endpoint is None:
            logger.info(
                "Dashboard reload: AZURE_AI_PROJECT_ENDPOINT not set — "
                "agent TOML files validated but live routing was NOT updated. "
                "Restart the server to apply changes."
            )
            return JSONResponse(
                {
                    "reloaded": False,
                    "reason": (
                        "AZURE_AI_PROJECT_ENDPOINT is not set. "
                        "TOML files were validated successfully. "
                        "Restart the server to apply routing changes."
                    ),
                    "agents": [_definition_to_dict(d) for d in definitions],
                }
            )

        try:
            await on_reload(definitions)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error during agent hot-reload")
            return JSONResponse(
                {"error": f"Hot-reload failed: {exc}"},
                status_code=500,
            )

        logger.info(
            "Dashboard: hot-reloaded %d agent(s): %s",
            len(definitions),
            [d.slug for d in definitions],
        )
        return JSONResponse(
            {
                "reloaded": True,
                "agents": [_definition_to_dict(d) for d in definitions],
            }
        )

    # ------------------------------------------------------------------
    # Route table
    # ------------------------------------------------------------------

    return [
        Route("/agents", endpoint=list_agents, methods=["GET"]),
        Route("/agents/{slug}", endpoint=get_agent, methods=["GET"]),
        Route("/agents", endpoint=create_agent, methods=["POST"]),
        Route("/agents/{slug}", endpoint=update_agent, methods=["PUT"]),
        Route("/agents/{slug}", endpoint=delete_agent, methods=["DELETE"]),
        Route("/reload", endpoint=reload_agents, methods=["POST"]),
    ]
