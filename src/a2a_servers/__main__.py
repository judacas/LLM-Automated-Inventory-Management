import logging

import click
import uvicorn
from agent_definition import load_agent_definitions
from app_factory import MountedAgent, create_app
from dotenv import load_dotenv
from settings import (
    CompositeAgentSettings,
    ServerSettings,
    load_composite_agent_settings,
    load_server_settings,
)

load_dotenv()  # TODO: match the .env loading strategy in foundry_agent.py (currently duplicated) but also might need a better strategy overall for config management across the codebase

logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", "host", default=None)
@click.option("--port", "port", type=int, default=None)
@click.option(
    "--url-mode",
    "url_mode",
    type=click.Choice(["local", "forwarded"], case_sensitive=False),
    default=None,
)
@click.option("--forwarded-base-url", "forwarded_base_url", default=None)
@click.option(
    "--agent-config-dir",
    "agent_config_dir",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=str),
    default=None,
)
@click.option(
    "--composite-slug",
    "composite_slug",
    type=str,
    default=None,
    help="If provided, mount a composite agent that routes skills to other agents.",
)
@click.option(
    "--composite-name",
    "composite_name",
    type=str,
    default=None,
    help="Display name for the composite agent (defaults to 'Composite Agent').",
)
@click.option(
    "--composite-description",
    "composite_description",
    type=str,
    default=None,
    help="Description for the composite agent card.",
)
@click.option(
    "--composite-version",
    "composite_version",
    type=str,
    default=None,
    help="Version string for the composite agent.",
)
@click.option(
    "--composite-health-message",
    "composite_health_message",
    type=str,
    default=None,
    help="Health check response for the composite agent.",
)
def main(
    host: str | None,
    port: int | None,
    url_mode: str | None,
    forwarded_base_url: str | None,
    agent_config_dir: str | None,
    composite_slug: str | None,
    composite_name: str | None,
    composite_description: str | None,
    composite_version: str | None,
    composite_health_message: str | None,
) -> None:
    """Start a multi-agent A2A server backed by Azure AI Foundry."""
    settings = load_server_settings(
        host=host,
        port=port,
        url_mode=url_mode,
        forwarded_base_url=forwarded_base_url,
    )
    composite_settings: CompositeAgentSettings | None = load_composite_agent_settings(
        slug=composite_slug,
        name=composite_name,
        description=composite_description,
        version=composite_version,
        health_message=composite_health_message,
    )

    definitions = load_agent_definitions(agent_config_dir)
    app, mounted_agents = create_app(definitions, settings, composite_settings)

    log_level_name = settings.log_level_name
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level)

    logger.info(
        "Starting multi-agent A2A server on %s:%s", settings.host, settings.port
    )
    logger.info("Loaded %s agent definitions", len(mounted_agents))
    logger.info("Agent card URL mode: %s", settings.url_mode)
    logger.info("Root index available at: %s/", settings.public_base_url)
    if composite_settings is not None and composite_settings.enabled:
        logger.info(
            "Composite routing enabled at /%s using %s source agents",
            composite_settings.slug,
            len(definitions),
        )

    for mounted_agent in mounted_agents:
        _log_agent_startup(mounted_agent, settings)

    uvicorn.run(app, host=settings.host, port=settings.port)


def _log_agent_startup(mounted_agent: MountedAgent, settings: ServerSettings) -> None:
    definition = mounted_agent.definition
    logger.info("Agent slug: %s", definition.slug)
    logger.info("Loaded agent config from %s", definition.source_path)
    logger.info("Foundry agent name: %s", definition.foundry_agent_name)
    logger.info("Agent card: %s", mounted_agent.agent_card.name)
    logger.info("Agent card URL: %s", mounted_agent.agent_card.url)
    logger.info("Skills: %s", [skill.name for skill in definition.skills])
    logger.info(
        "Health check available at: %s/health",
        settings.agent_base_url_for(definition.slug),
    )


if __name__ == "__main__":
    main()
