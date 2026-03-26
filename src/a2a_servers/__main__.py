import logging

import click
import uvicorn
from agent_definition import load_agent_definitions
from app_factory import MountedAgent, create_app
from config_loader import AgentConfigLocation, prepare_agent_config_location
from composite_definition import load_composite_agent_definitions
from dotenv import load_dotenv
from settings import ServerSettings, load_server_settings

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
    "--agent-config-url",
    "agent_config_url",
    type=str,
    default=None,
)
def main(
    host: str | None,
    port: int | None,
    url_mode: str | None,
    forwarded_base_url: str | None,
    agent_config_dir: str | None,
    agent_config_url: str | None,
) -> None:
    """Start a multi-agent A2A server backed by Azure AI Foundry."""
    settings = load_server_settings(
        host=host,
        port=port,
        url_mode=url_mode,
        forwarded_base_url=forwarded_base_url,
    )

    config_location: AgentConfigLocation = prepare_agent_config_location(
        config_dir=agent_config_dir,
        config_url=agent_config_url,
    )
    config_dir_path = str(config_location.directory)
    definitions = load_agent_definitions(config_dir_path)
    composite_definitions = load_composite_agent_definitions(config_dir_path)
    app, mounted_agents = create_app(
        definitions, settings, composite_definitions=composite_definitions
    )

    log_level_name = settings.log_level_name
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level)

    logger.info(
        "Starting multi-agent A2A server on %s:%s", settings.host, settings.port
    )
    logger.info("Loaded %s agent definitions", len(mounted_agents))
    logger.info("Agent card URL mode: %s", settings.url_mode)
    logger.info("Agent configs loaded from: %s", config_location.source)
    logger.info("Root index available at: %s/", settings.public_base_url)

    for mounted_agent in mounted_agents:
        _log_agent_startup(mounted_agent, settings)

    uvicorn.run(app, host=settings.host, port=settings.port)


def _log_agent_startup(mounted_agent: MountedAgent, settings: ServerSettings) -> None:
    from agent_definition import AgentDefinition
    from composite_definition import CompositeAgentDefinition

    definition = mounted_agent.definition
    logger.info("Agent slug: %s", definition.slug)
    logger.info("Loaded agent config from %s", definition.source_path)
    logger.info("Agent card: %s", mounted_agent.agent_card.name)
    logger.info("Agent card URL: %s", mounted_agent.agent_card.url)
    logger.info("Skills: %s", [skill.name for skill in definition.skills])
    logger.info(
        "Health check available at: %s/health",
        settings.agent_base_url_for(definition.slug),
    )

    if isinstance(definition, AgentDefinition):
        logger.info("Foundry agent name: %s", definition.foundry_agent_name)
    elif isinstance(definition, CompositeAgentDefinition):
        for i, member in enumerate(definition.members):
            logger.info(
                "  Composite member %d: %s → %s",
                i,
                member.agent_definition.slug,
                member.agent_definition.foundry_agent_name,
            )


if __name__ == "__main__":
    main()
