import logging

import click
import uvicorn
from dotenv import load_dotenv

from a2a_servers.agent_definition import load_agent_definitions
from a2a_servers.agent_store import (
    DEFAULT_TABLE_NAME,
    load_agent_definitions_from_db,
    seed_agents_to_db,
)
from a2a_servers.app_factory import MountedAgent, create_app
from a2a_servers.settings import ServerSettings, load_server_settings

load_dotenv()

logger = logging.getLogger(__name__)


@click.group()
def cli() -> None:
    """A2A server tools for Azure AI Foundry."""


@cli.command("serve")
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
    help="Directory with *_agent.toml files. Used when DB is not configured.",
)
def serve(
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

    if settings.use_db:
        logger.info("Loading agent definitions from Azure Table Storage")
        definitions = load_agent_definitions_from_db(
            connection_string=settings.storage_connection_string,
            account_url=settings.storage_account_url,
            table_name=settings.agents_table_name,
        )
    else:
        logger.info("Loading agent definitions from local TOML files")
        definitions = load_agent_definitions(agent_config_dir)

    app, mounted_agents = create_app(definitions, settings)

    log_level_name = settings.log_level_name
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level)

    logger.info(
        "Starting multi-agent A2A server on %s:%s", settings.host, settings.port
    )
    logger.info("Loaded %s agent definitions", len(mounted_agents))
    logger.info("Agent card URL mode: %s", settings.url_mode)
    logger.info("Root index available at: %s/", settings.public_base_url)

    for mounted_agent in mounted_agents:
        _log_agent_startup(mounted_agent, settings)

    uvicorn.run(app, host=settings.host, port=settings.port)


@cli.command("seed-db")
@click.option(
    "--agent-config-dir",
    "agent_config_dir",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=str),
    default=None,
    help="Directory with *_agent.toml files to seed from. Defaults to agents/.",
)
@click.option(
    "--connection-string",
    "connection_string",
    envvar="AZURE_STORAGE_CONNECTION_STRING",
    default=None,
    help="Azure Storage connection string. Overrides env var.",
)
@click.option(
    "--account-url",
    "account_url",
    envvar="AZURE_STORAGE_ACCOUNT_URL",
    default=None,
    help="Azure Storage account URL. Uses DefaultAzureCredential.",
)
@click.option(
    "--table",
    "table_name",
    envvar="A2A_AGENTS_TABLE",
    default=None,
    help="Azure Storage table name. Defaults to a2aagents.",
)
def seed_db(
    agent_config_dir: str | None,
    connection_string: str | None,
    account_url: str | None,
    table_name: str | None,
) -> None:
    """Seed Azure Table Storage with agent definitions from local TOML files.

    Reads every *_agent.toml in the agent config directory and upserts each
    one into the configured Azure Storage table. Creates the table when it
    does not exist. Existing records are overwritten.
    """
    resolved_table = (table_name or DEFAULT_TABLE_NAME).strip()

    logging.basicConfig(level=logging.INFO)
    logger.info("Reading agent definitions from local TOML files")
    definitions = load_agent_definitions(agent_config_dir)
    logger.info("Found %d agent definition(s)", len(definitions))

    seed_agents_to_db(
        definitions,
        connection_string=connection_string or None,
        account_url=account_url or None,
        table_name=resolved_table,
    )
    logger.info(
        "Done. %d agent(s) seeded to table `%s`.", len(definitions), resolved_table
    )


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


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

# Keep `python -m a2a_servers` (invoked via __main__) working as before:
# the group is invoked which will print help unless a subcommand is given.
if __name__ == "__main__":
    cli()
