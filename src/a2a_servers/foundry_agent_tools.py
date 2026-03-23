"""CLI helpers for managing Azure AI Foundry agents with A2A tools.

Two primary workflows are supported:

- Show and rename the tool schema for a portal-created agent (fixes duplicate
  tool name errors when multiple A2A connections were added through the UI).
- Create a prompt agent fully via code with A2A tools that already have unique
  names.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import click
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import AgentVersionDetails, PromptAgentDefinition
from azure.core.exceptions import HttpResponseError
from azure.identity.aio import DefaultAzureCredential

from foundry_tool_schema import (
    ensure_unique_tool_names,
    parse_a2a_tool_spec,
    summarize_tool,
)

DEFAULT_CARD_PATH = "/.well-known/agent-card.json"


@click.group()
def cli() -> None:
    """Manage portal-created agents and code-created agents."""


@cli.command("show-tools")
@click.option(
    "--agent-name",
    required=True,
    help="The Foundry agent name or ID to inspect.",
)
@click.option(
    "--version",
    default=None,
    help="Optional explicit version to inspect; defaults to latest.",
)
@click.option(
    "--endpoint",
    envvar="AZURE_AI_PROJECT_ENDPOINT",
    required=True,
    help="Azure AI Project endpoint (https://<name>.services.ai.azure.com/api/projects/<project>).",
)
def show_tools_command(agent_name: str, version: str | None, endpoint: str) -> None:
    """Print the current tool schema for an agent."""
    asyncio.run(show_tools(agent_name=agent_name, version=version, endpoint=endpoint))


@cli.command("rename-tools")
@click.option(
    "--agent-name",
    required=True,
    help="The Foundry agent name or ID to update.",
)
@click.option(
    "--version",
    default=None,
    help="Optional version to base the update on; defaults to latest.",
)
@click.option(
    "--prefix",
    default=None,
    help="Prefix for generated tool names. Defaults to the agent name.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show the planned changes without creating a new agent version.",
)
@click.option(
    "--endpoint",
    envvar="AZURE_AI_PROJECT_ENDPOINT",
    required=True,
    help="Azure AI Project endpoint (https://<name>.services.ai.azure.com/api/projects/<project>).",
)
def rename_tools_command(
    agent_name: str,
    version: str | None,
    prefix: str | None,
    dry_run: bool,
    endpoint: str,
) -> None:
    """Ensure every tool attached to an agent has a unique name."""
    asyncio.run(
        rename_tools(
            agent_name=agent_name,
            version=version,
            prefix=prefix,
            dry_run=dry_run,
            endpoint=endpoint,
        )
    )


@cli.command("create-agent")
@click.option(
    "--agent-name",
    required=True,
    help="Agent name to create (or update with a new version).",
)
@click.option(
    "--model-deployment",
    required=True,
    help="Deployment name to back the prompt agent (for example: gpt-4o-mini).",
)
@click.option(
    "--instructions-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to a text file containing the agent's system instructions.",
)
@click.option(
    "--a2a-tool",
    "a2a_tools",
    multiple=True,
    required=True,
    help=(
        "Comma-separated spec for each A2A tool: "
        "name=<optional>,base_url=<required>,connection_id=<required>,agent_card_path=<optional>"
    ),
)
@click.option(
    "--tool-name-prefix",
    default=None,
    help="Prefix used if tool names need to be generated. Defaults to the agent name.",
)
@click.option(
    "--description",
    default="Created via foundry_agent_tools.py",
    show_default=True,
    help="Description for the created agent version.",
)
@click.option(
    "--endpoint",
    envvar="AZURE_AI_PROJECT_ENDPOINT",
    required=True,
    help="Azure AI Project endpoint (https://<name>.services.ai.azure.com/api/projects/<project>).",
)
def create_agent_command(
    agent_name: str,
    model_deployment: str,
    instructions_path: Path,
    a2a_tools: tuple[str, ...],
    tool_name_prefix: str | None,
    description: str,
    endpoint: str,
) -> None:
    """Create a prompt agent in code with pre-named A2A tools."""
    asyncio.run(
        create_agent_with_tools(
            agent_name=agent_name,
            model_deployment=model_deployment,
            instructions_path=instructions_path,
            a2a_tools=a2a_tools,
            tool_name_prefix=tool_name_prefix,
            description=description,
            endpoint=endpoint,
        )
    )


async def show_tools(
    *, agent_name: str, version: str | None, endpoint: str
) -> None:
    client, credential = await _build_client(endpoint)
    try:
        agent = await client.agents.get(agent_name=agent_name)
        target_version = version or agent.versions.latest.version
        details = await _get_agent_version(client, agent.name, target_version)
        tools = list(details.definition.tools or [])
        summaries = [summarize_tool(tool, index) for index, tool in enumerate(tools)]
        payload = {
            "agent": agent.name,
            "version": target_version,
            "tool_count": len(summaries),
            "tools": summaries,
        }
        click.echo(json.dumps(payload, indent=2))
    finally:
        await _safe_close(client, credential)


async def rename_tools(
    *,
    agent_name: str,
    version: str | None,
    prefix: str | None,
    dry_run: bool,
    endpoint: str,
) -> None:
    client, credential = await _build_client(endpoint)
    try:
        agent = await client.agents.get(agent_name=agent_name)
        target_version = version or agent.versions.latest.version
        details = await _get_agent_version(client, agent.name, target_version)

        tools = list(details.definition.tools or [])
        updated_tools, rename_map = ensure_unique_tool_names(
            tools, prefix=prefix or agent.name
        )

        if not rename_map:
            click.echo("Tool schema already has unique names; no changes made.")
            return

        click.echo("Planned tool name updates:")
        click.echo(json.dumps(rename_map, indent=2))

        if dry_run:
            click.echo("Dry-run requested; no agent version was created.")
            return

        await client.agents.create_version(
            agent_name=agent.name,
            definition=PromptAgentDefinition(
                model=details.definition.get("model"),
                instructions=details.definition.get("instructions"),
                tools=updated_tools,
                text=details.definition.get("text"),
                tool_choice=details.definition.get("tool_choice"),
                structured_inputs=details.definition.get("structured_inputs"),
                rai_config=details.definition.get("rai_config"),
                temperature=details.definition.get("temperature"),
                top_p=details.definition.get("top_p"),
                reasoning=details.definition.get("reasoning"),
            ),
            description=details.description,
            metadata=details.metadata,
        )
        click.echo("Created a new agent version with unique tool names.")
    finally:
        await _safe_close(client, credential)


async def create_agent_with_tools(
    *,
    agent_name: str,
    model_deployment: str,
    instructions_path: Path,
    a2a_tools: tuple[str, ...],
    tool_name_prefix: str | None,
    description: str,
    endpoint: str,
) -> None:
    instructions_text = instructions_path.read_text(encoding="utf-8")
    tools = [
        parse_a2a_tool_spec(spec, default_card_path=DEFAULT_CARD_PATH)
        for spec in a2a_tools
    ]
    tools, rename_map = ensure_unique_tool_names(
        tools, prefix=tool_name_prefix or agent_name
    )

    client, credential = await _build_client(endpoint)
    try:
        await client.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=instructions_text,
                tools=tools,
            ),
            description=description,
            metadata={"created_by": "foundry_agent_tools.py"},
        )

        click.echo(
            f"Created/updated agent `{agent_name}` with {len(tools)} A2A tool(s)."
        )
        if rename_map:
            click.echo("Applied tool name normalisation:")
            click.echo(json.dumps(rename_map, indent=2))
    finally:
        await _safe_close(client, credential)


async def _build_client(
    endpoint: str,
) -> tuple[AIProjectClient, DefaultAzureCredential]:
    credential = DefaultAzureCredential()
    client = AIProjectClient(endpoint=endpoint, credential=credential)
    return client, credential


async def _safe_close(client: AIProjectClient, credential: DefaultAzureCredential) -> None:
    try:
        await client.close()
    finally:
        try:
            await credential.close()
        except Exception:
            pass


async def _get_agent_version(
    client: AIProjectClient, agent_name: str, version: str
) -> AgentVersionDetails:
    try:
        return await client.agents.get_version(
            agent_name=agent_name, agent_version=version
        )
    except HttpResponseError as exc:
        raise RuntimeError(
            f"Failed to fetch agent {agent_name!r} version {version!r}: {exc}"
        ) from exc


if __name__ == "__main__":
    cli()
