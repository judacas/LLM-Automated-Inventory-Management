"""Azure Table Storage backend for agent definitions.

Stores each agent as a single entity in the ``a2aagents`` table
(configurable via ``A2A_AGENTS_TABLE``).  List-typed fields and the
``skills`` array are serialised as JSON strings because Azure Table
Storage only supports flat scalar properties.

Schema
------
PartitionKey : "agents"  (all agents share one partition for easy listing)
RowKey       : <slug>    (unique agent identifier; same as AgentDefinition.slug)
public_name  : str
description  : str
version      : str
health_message : str
foundry_agent_name : str
default_input_modes_json  : JSON-encoded list[str]
default_output_modes_json : JSON-encoded list[str]
skills_json               : JSON-encoded list of skill objects
smoke_test_prompts_json   : JSON-encoded list[str]
supports_streaming        : bool
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from a2a.types import AgentSkill
from azure.data.tables import TableClient, TableServiceClient

from a2a_servers.agent_definition import (
    AgentDefinition,
    _normalize_agent_slug,
    _read_required_string,
)

logger = logging.getLogger(__name__)

DEFAULT_TABLE_NAME = "a2aagents"
_PARTITION_KEY = "agents"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_str(mapping: dict[str, Any], key: str, context: str) -> str:
    """Return a non-empty string from *mapping[key]* or raise ValueError."""
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Agent record `{context}`: missing required field `{key}`")
    return value.strip()


def _parse_json_list(raw: Any, field: str, context: str) -> list[Any]:
    """Parse a JSON-encoded list from a Table Storage property."""
    if not isinstance(raw, str):
        raise ValueError(
            f"Agent record `{context}`: field `{field}` must be a JSON string"
        )
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError(
            f"Agent record `{context}`: field `{field}` must decode to a JSON array"
        )
    return parsed


# ---------------------------------------------------------------------------
# Serialisation / deserialisation
# ---------------------------------------------------------------------------


def _entity_from_definition(definition: AgentDefinition) -> dict[str, Any]:
    """Convert an AgentDefinition to a flat dict for Azure Table Storage."""
    skills_payload = [
        {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "tags": list(skill.tags or []),
            "examples": list(skill.examples or []),
        }
        for skill in definition.skills
    ]
    return {
        "PartitionKey": _PARTITION_KEY,
        "RowKey": definition.slug,
        "public_name": definition.public_name,
        "description": definition.description,
        "version": definition.version,
        "health_message": definition.health_message,
        "foundry_agent_name": definition.foundry_agent_name,
        "default_input_modes_json": json.dumps(list(definition.default_input_modes)),
        "default_output_modes_json": json.dumps(list(definition.default_output_modes)),
        "skills_json": json.dumps(skills_payload),
        "smoke_test_prompts_json": json.dumps(list(definition.smoke_test_prompts)),
        "supports_streaming": definition.supports_streaming,
    }


def _definition_from_entity(entity: dict[str, Any]) -> AgentDefinition:
    """Convert an Azure Table Storage entity to an AgentDefinition.

    Raises ValueError if required fields are missing or malformed.
    """
    slug = _normalize_agent_slug(str(entity.get("RowKey", "")))
    context = slug or "<unknown>"

    skills_raw = _parse_json_list(
        entity.get("skills_json", "[]"), "skills_json", context
    )
    if not skills_raw:
        raise ValueError(
            f"Agent record `{context}`: `skills_json` must contain at least one skill"
        )

    skills: list[AgentSkill] = []
    for i, skill_data in enumerate(skills_raw, start=1):
        if not isinstance(skill_data, dict):
            raise ValueError(
                f"Agent record `{context}`: skill #{i} must be a JSON object"
            )
        skill_ctx = f"{context}/skill[{i}]"
        tags = skill_data.get("tags", [])
        examples = skill_data.get("examples", [])
        if not isinstance(tags, list):
            raise ValueError(f"Agent record `{skill_ctx}`: `tags` must be a list")
        if not isinstance(examples, list):
            raise ValueError(f"Agent record `{skill_ctx}`: `examples` must be a list")
        skills.append(
            AgentSkill(
                id=_read_required_string(skill_data, "id", skill_ctx),
                name=_read_required_string(skill_data, "name", skill_ctx),
                description=_read_required_string(skill_data, "description", skill_ctx),
                tags=[str(t) for t in tags],
                examples=[str(e) for e in examples],
            )
        )

    raw_in = entity.get("default_input_modes_json", '["text"]')
    raw_out = entity.get("default_output_modes_json", '["text"]')
    raw_prompts = entity.get("smoke_test_prompts_json", "[]")

    input_modes = tuple(
        str(m) for m in _parse_json_list(raw_in, "default_input_modes_json", context)
    )
    output_modes = tuple(
        str(m) for m in _parse_json_list(raw_out, "default_output_modes_json", context)
    )
    smoke_prompts = tuple(
        str(p)
        for p in _parse_json_list(raw_prompts, "smoke_test_prompts_json", context)
    )

    streaming_raw = entity.get("supports_streaming", True)
    if not isinstance(streaming_raw, bool):
        raise ValueError(
            f"Agent record `{context}`: `supports_streaming` must be a boolean"
        )

    return AgentDefinition(
        slug=slug,
        source_path=Path(f"db:{slug}"),
        public_name=_require_str(entity, "public_name", context),
        description=_require_str(entity, "description", context),
        version=_require_str(entity, "version", context),
        health_message=_require_str(entity, "health_message", context),
        foundry_agent_name=_require_str(entity, "foundry_agent_name", context),
        default_input_modes=input_modes,
        default_output_modes=output_modes,
        skills=tuple(skills),
        smoke_test_prompts=smoke_prompts,
        supports_streaming=streaming_raw,
    )


# ---------------------------------------------------------------------------
# Table client factory
# ---------------------------------------------------------------------------


def _make_table_client(
    table_name: str,
    connection_string: str | None,
    account_url: str | None,
) -> TableClient:
    """Return a synchronous TableClient from either a connection string or a
    storage account URL (the latter uses DefaultAzureCredential).

    Raises ValueError when neither is provided.
    """
    if connection_string:
        return TableClient.from_connection_string(
            conn_str=connection_string,
            table_name=table_name,
        )
    if account_url:
        from azure.identity import DefaultAzureCredential  # import lazily

        return TableClient(
            endpoint=account_url,
            table_name=table_name,
            credential=DefaultAzureCredential(),
        )
    raise ValueError(
        "A database connection is required but neither "
        "AZURE_STORAGE_CONNECTION_STRING nor AZURE_STORAGE_ACCOUNT_URL is set."
    )


def _make_service_client(
    connection_string: str | None,
    account_url: str | None,
) -> TableServiceClient:
    """Return a synchronous TableServiceClient (used to create the table)."""
    if connection_string:
        return TableServiceClient.from_connection_string(conn_str=connection_string)
    if account_url:
        from azure.identity import DefaultAzureCredential  # import lazily

        return TableServiceClient(
            endpoint=account_url,
            credential=DefaultAzureCredential(),
        )
    raise ValueError(
        "A database connection is required but neither "
        "AZURE_STORAGE_CONNECTION_STRING nor AZURE_STORAGE_ACCOUNT_URL is set."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_agent_definitions_from_db(
    *,
    connection_string: str | None = None,
    account_url: str | None = None,
    table_name: str = DEFAULT_TABLE_NAME,
) -> tuple[AgentDefinition, ...]:
    """Load agent definitions from Azure Table Storage.

    Queries all entities in the agents partition, deserialises each one, and
    validates that no two agents share the same slug or Foundry agent name.

    Args:
        connection_string: Azure Storage connection string.
        account_url: Azure Storage account URL (used with DefaultAzureCredential
                     when *connection_string* is not given).
        table_name: Name of the Azure Storage table. Defaults to ``a2aagents``.

    Returns:
        A tuple of :class:`AgentDefinition` objects sorted by slug.

    Raises:
        ValueError: If any record is malformed or duplicates are detected.
    """
    client = _make_table_client(table_name, connection_string, account_url)

    entities = list(
        client.query_entities(
            query_filter="PartitionKey eq @pk",
            parameters={"pk": _PARTITION_KEY},
        )
    )

    if not entities:
        raise ValueError(
            f"No agent definitions found in table `{table_name}` "
            f"(partition `{_PARTITION_KEY}`). "
            "Run `python -m a2a_servers seed-db` to populate from local TOML files."
        )

    definitions: list[AgentDefinition] = []
    errors: list[str] = []

    for entity in entities:
        slug_raw = str(entity.get("RowKey", "<unknown>"))
        try:
            definitions.append(_definition_from_entity(dict(entity)))
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"  - {slug_raw}: {exc}")

    if errors:
        raise ValueError(
            f"Failed to load {len(errors)} agent record(s) from `{table_name}`:\n"
            + "\n".join(errors)
        )

    # Deduplication checks (belt-and-suspenders; slugs are unique in Table Storage
    # by RowKey, but foundry names have no DB-level uniqueness constraint).
    seen_slugs: set[str] = set()
    seen_foundry_names: dict[str, str] = {}

    for definition in definitions:
        if definition.slug in seen_slugs:
            raise ValueError(
                f"Duplicate agent slug `{definition.slug}` in table `{table_name}`"
            )
        seen_slugs.add(definition.slug)

        previous = seen_foundry_names.get(definition.foundry_agent_name)
        if previous is not None:
            raise ValueError(
                f"Duplicate Foundry agent name `{definition.foundry_agent_name}` "
                f"shared by slugs `{previous}` and `{definition.slug}`"
            )
        seen_foundry_names[definition.foundry_agent_name] = definition.slug

    definitions.sort(key=lambda d: d.slug)
    logger.info(
        "Loaded %d agent definition(s) from table `%s`", len(definitions), table_name
    )
    return tuple(definitions)


def seed_agents_to_db(
    definitions: tuple[AgentDefinition, ...],
    *,
    connection_string: str | None = None,
    account_url: str | None = None,
    table_name: str = DEFAULT_TABLE_NAME,
) -> None:
    """Upsert agent definitions into Azure Table Storage.

    Creates the table if it does not already exist, then upserts one entity
    per definition.  Existing records are replaced (merge=False) so that
    every field is up-to-date after seeding.

    Args:
        definitions: The agent definitions to persist.
        connection_string: Azure Storage connection string.
        account_url: Azure Storage account URL (uses DefaultAzureCredential).
        table_name: Name of the Azure Storage table. Defaults to ``a2aagents``.
    """
    svc = _make_service_client(connection_string, account_url)
    svc.create_table_if_not_exists(table_name=table_name)
    logger.info("Ensured table `%s` exists", table_name)

    client = _make_table_client(table_name, connection_string, account_url)

    for definition in definitions:
        entity = _entity_from_definition(definition)
        client.upsert_entity(entity=entity, mode="replace")
        logger.info("Upserted agent `%s` into table `%s`", definition.slug, table_name)

    logger.info(
        "Seeded %d agent definition(s) into table `%s`", len(definitions), table_name
    )
