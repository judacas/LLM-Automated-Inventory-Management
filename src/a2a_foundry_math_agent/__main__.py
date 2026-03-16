import logging

import click
import uvicorn
from agent_definition import load_agent_definition
from app_factory import create_app
from dotenv import load_dotenv
from settings import load_server_settings

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
@click.option("--agent-config", "agent_config_path", default=None)
def main(
    host: str | None,
    port: int | None,
    url_mode: str | None,
    forwarded_base_url: str | None,
    agent_config_path: str | None,
) -> None:
    """Start a single-agent A2A server backed by Azure AI Foundry."""
    settings = load_server_settings(
        host=host,
        port=port,
        url_mode=url_mode,
        forwarded_base_url=forwarded_base_url,
    )

    definition = load_agent_definition(agent_config_path)
    app, agent_card = create_app(definition, settings)

    log_level_name = settings.log_level_name
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level)

    # Log startup information
    logger.info("Starting %s on %s:%s", agent_card.name, settings.host, settings.port)
    logger.info("Loaded agent config from %s", definition.source_path)
    logger.info("Foundry agent name: %s", definition.foundry_agent_name)
    logger.info("Agent card URL mode: %s", settings.url_mode)
    if settings.url_mode == "forwarded":
        logger.info(
            "Agent is behind reverse proxy. External URL: %s", settings.agent_card_url
        )
    else:
        logger.info("Agent card URL (local): %s", settings.agent_card_url)
    logger.info("Agent card: %s", agent_card.name)
    logger.info("Skills: %s", [skill.name for skill in definition.skills])
    logger.info(
        "Health check available at: http://%s:%s/health", settings.host, settings.port
    )

    # Run the server
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
