import logging

import click
import uvicorn
from dotenv import load_dotenv

from a2a_servers.agent_definition import load_agent_definitions
from a2a_servers.app_factory import MountedAgent, create_app
from a2a_servers.group_definition import GroupDefinition, load_group_definitions
from a2a_servers.settings import ServerSettings, load_server_settings

load_dotenv()

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
def main(
    host: str | None,
    port: int | None,
    url_mode: str | None,
    forwarded_base_url: str | None,
    agent_config_dir: str | None,
) -> None:
    """Start a multi-agent A2A server backed by Azure AI Foundry."""
    settings = load_server_settings(
        host=host,
        port=port,
        url_mode=url_mode,
        forwarded_base_url=forwarded_base_url,
    )

    definitions = load_agent_definitions(agent_config_dir)
    group_definitions = load_group_definitions(agent_config_dir)
    app, mounted_agents = create_app(definitions, settings, group_definitions)

    log_level_name = settings.log_level_name
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level)

    logger.info(
        "Starting multi-agent A2A server on %s:%s", settings.host, settings.port
    )
    logger.info(
        "Loaded %s individual agent definition(s), %s group definition(s)",
        len(definitions),
        len(group_definitions),
    )
    logger.info("Agent card URL mode: %s", settings.url_mode)
    logger.info("Root index available at: %s/", settings.public_base_url)

    for mounted_agent in mounted_agents:
        _log_agent_startup(mounted_agent, settings)

    uvicorn.run(app, host=settings.host, port=settings.port)


def _log_agent_startup(mounted_agent: MountedAgent, settings: ServerSettings) -> None:
    definition = mounted_agent.definition
    logger.info("Agent slug: %s", definition.slug)
    logger.info("Loaded config from %s", definition.source_path)
    logger.info("Agent card: %s", mounted_agent.agent_card.name)
    logger.info("Agent card URL: %s", mounted_agent.agent_card.url)
    if isinstance(definition, GroupDefinition):
        logger.info("Group members: %s", sorted(definition.member_slugs))
    else:
        logger.info("Foundry agent name: %s", definition.foundry_agent_name)
        logger.info("Skills: %s", [skill.name for skill in definition.skills])
    logger.info(
        "Health check available at: %s/health",
        settings.agent_base_url_for(definition.slug),
    )


if __name__ == "__main__":
    main()
