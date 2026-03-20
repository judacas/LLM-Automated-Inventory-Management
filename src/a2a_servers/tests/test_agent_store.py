"""Unit tests for src/a2a_servers/agent_store.py.

These tests exercise serialisation/deserialisation, validation, and
duplicate-detection logic entirely in-process.  The Azure Table Storage
client is replaced with a ``MagicMock`` at the module boundary so no real
storage account or emulator is required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from a2a.types import AgentSkill

from a2a_servers.agent_definition import AgentDefinition
from a2a_servers.agent_store import (
    _PARTITION_KEY,
    DEFAULT_TABLE_NAME,
    _definition_from_entity,
    _entity_from_definition,
    load_agent_definitions_from_db,
    seed_agents_to_db,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKILL = AgentSkill(
    id="math_computation",
    name="Math Computation",
    description="Solve math problems.",
    tags=["math"],
    examples=["2 + 2"],
)

_DEFINITION = AgentDefinition(
    slug="math",
    source_path=Path("agents/math_agent.toml"),
    public_name="Math Agent",
    description="Solves math problems",
    version="1.0.0",
    health_message="Math Agent is running!",
    foundry_agent_name="Math-Agent",
    default_input_modes=("text",),
    default_output_modes=("text",),
    skills=(_SKILL,),
    smoke_test_prompts=("What is 1+1?",),
    supports_streaming=True,
)


def _make_entity(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid Table Storage entity dict."""
    base: dict[str, Any] = {
        "PartitionKey": _PARTITION_KEY,
        "RowKey": "math",
        "public_name": "Math Agent",
        "description": "Solves math problems",
        "version": "1.0.0",
        "health_message": "Math Agent is running!",
        "foundry_agent_name": "Math-Agent",
        "default_input_modes_json": '["text"]',
        "default_output_modes_json": '["text"]',
        "skills_json": json.dumps(
            [
                {
                    "id": "math_computation",
                    "name": "Math Computation",
                    "description": "Solve math problems.",
                    "tags": ["math"],
                    "examples": ["2 + 2"],
                }
            ]
        ),
        "smoke_test_prompts_json": '["What is 1+1?"]',
        "supports_streaming": True,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _entity_from_definition
# ---------------------------------------------------------------------------


def test_entity_from_definition_round_trips_slug() -> None:
    entity = _entity_from_definition(_DEFINITION)
    assert entity["RowKey"] == "math"
    assert entity["PartitionKey"] == _PARTITION_KEY


def test_entity_from_definition_serialises_skills() -> None:
    entity = _entity_from_definition(_DEFINITION)
    skills = json.loads(entity["skills_json"])
    assert len(skills) == 1
    assert skills[0]["id"] == "math_computation"
    assert skills[0]["tags"] == ["math"]


def test_entity_from_definition_serialises_modes() -> None:
    entity = _entity_from_definition(_DEFINITION)
    assert json.loads(entity["default_input_modes_json"]) == ["text"]
    assert json.loads(entity["default_output_modes_json"]) == ["text"]


def test_entity_from_definition_serialises_smoke_prompts() -> None:
    entity = _entity_from_definition(_DEFINITION)
    assert json.loads(entity["smoke_test_prompts_json"]) == ["What is 1+1?"]


def test_entity_from_definition_preserves_streaming_flag() -> None:
    entity = _entity_from_definition(_DEFINITION)
    assert entity["supports_streaming"] is True


# ---------------------------------------------------------------------------
# _definition_from_entity – happy path
# ---------------------------------------------------------------------------


def test_definition_from_entity_basic() -> None:
    entity = _make_entity()
    defn = _definition_from_entity(entity)

    assert defn.slug == "math"
    assert defn.public_name == "Math Agent"
    assert defn.foundry_agent_name == "Math-Agent"
    assert defn.version == "1.0.0"
    assert defn.supports_streaming is True
    assert defn.source_path == Path("db:math")


def test_definition_from_entity_skills_deserialized() -> None:
    entity = _make_entity()
    defn = _definition_from_entity(entity)

    assert len(defn.skills) == 1
    skill = defn.skills[0]
    assert skill.id == "math_computation"
    assert skill.tags == ["math"]
    assert skill.examples == ["2 + 2"]


def test_definition_from_entity_modes_deserialized() -> None:
    entity = _make_entity()
    defn = _definition_from_entity(entity)

    assert defn.default_input_modes == ("text",)
    assert defn.default_output_modes == ("text",)


def test_definition_from_entity_smoke_prompts() -> None:
    entity = _make_entity()
    defn = _definition_from_entity(entity)

    assert defn.smoke_test_prompts == ("What is 1+1?",)


def test_definition_from_entity_defaults_modes_when_missing() -> None:
    entity = _make_entity()
    del entity["default_input_modes_json"]
    del entity["default_output_modes_json"]
    defn = _definition_from_entity(entity)

    assert defn.default_input_modes == ("text",)
    assert defn.default_output_modes == ("text",)


def test_definition_from_entity_empty_smoke_prompts_when_missing() -> None:
    entity = _make_entity()
    del entity["smoke_test_prompts_json"]
    defn = _definition_from_entity(entity)

    assert defn.smoke_test_prompts == ()


# ---------------------------------------------------------------------------
# _definition_from_entity – validation errors
# ---------------------------------------------------------------------------


def test_definition_from_entity_missing_public_name_raises() -> None:
    entity = _make_entity()
    del entity["public_name"]
    with pytest.raises(ValueError, match="public_name"):
        _definition_from_entity(entity)


def test_definition_from_entity_missing_foundry_name_raises() -> None:
    entity = _make_entity()
    del entity["foundry_agent_name"]
    with pytest.raises(ValueError, match="foundry_agent_name"):
        _definition_from_entity(entity)


def test_definition_from_entity_empty_skills_raises() -> None:
    entity = _make_entity(skills_json="[]")
    with pytest.raises(ValueError, match="at least one skill"):
        _definition_from_entity(entity)


def test_definition_from_entity_invalid_skills_json_raises() -> None:
    entity = _make_entity(skills_json="not-json")
    with pytest.raises((ValueError, json.JSONDecodeError)):
        _definition_from_entity(entity)


def test_definition_from_entity_skills_not_list_raises() -> None:
    entity = _make_entity(skills_json='{"id": "x"}')
    with pytest.raises(ValueError, match="JSON array"):
        _definition_from_entity(entity)


def test_definition_from_entity_skill_missing_id_raises() -> None:
    skill = {
        "name": "Math",
        "description": "desc",
        "tags": [],
        "examples": [],
    }
    entity = _make_entity(skills_json=json.dumps([skill]))
    with pytest.raises(ValueError):
        _definition_from_entity(entity)


def test_definition_from_entity_streaming_must_be_bool() -> None:
    entity = _make_entity(supports_streaming="yes")
    with pytest.raises(ValueError, match="supports_streaming"):
        _definition_from_entity(entity)


# ---------------------------------------------------------------------------
# Round-trip: entity → definition → entity
# ---------------------------------------------------------------------------


def test_round_trip_definition() -> None:
    entity = _entity_from_definition(_DEFINITION)
    recovered = _definition_from_entity(entity)

    assert recovered.slug == _DEFINITION.slug
    assert recovered.public_name == _DEFINITION.public_name
    assert recovered.description == _DEFINITION.description
    assert recovered.version == _DEFINITION.version
    assert recovered.health_message == _DEFINITION.health_message
    assert recovered.foundry_agent_name == _DEFINITION.foundry_agent_name
    assert recovered.default_input_modes == _DEFINITION.default_input_modes
    assert recovered.default_output_modes == _DEFINITION.default_output_modes
    assert recovered.supports_streaming == _DEFINITION.supports_streaming
    assert recovered.smoke_test_prompts == _DEFINITION.smoke_test_prompts
    assert len(recovered.skills) == 1
    assert recovered.skills[0].id == _DEFINITION.skills[0].id


# ---------------------------------------------------------------------------
# load_agent_definitions_from_db – with mocked TableClient
# ---------------------------------------------------------------------------


def _mock_table_client(entities: list[dict[str, Any]]) -> MagicMock:
    client = MagicMock()
    client.query_entities.return_value = iter(entities)
    return client


@patch("a2a_servers.agent_store._make_table_client")
def test_load_from_db_happy_path(mock_factory: MagicMock) -> None:
    entity = _make_entity()
    mock_factory.return_value = _mock_table_client([entity])

    definitions = load_agent_definitions_from_db(
        connection_string="fake-connection-string"
    )

    assert len(definitions) == 1
    assert definitions[0].slug == "math"


@patch("a2a_servers.agent_store._make_table_client")
def test_load_from_db_empty_table_raises(mock_factory: MagicMock) -> None:
    mock_factory.return_value = _mock_table_client([])

    with pytest.raises(ValueError, match="No agent definitions found"):
        load_agent_definitions_from_db(connection_string="fake")


@patch("a2a_servers.agent_store._make_table_client")
def test_load_from_db_duplicate_foundry_name_raises(mock_factory: MagicMock) -> None:
    e1 = _make_entity(RowKey="math", foundry_agent_name="shared-foundry")
    e2 = _make_entity(
        RowKey="quote",
        public_name="Quote Agent",
        description="desc",
        version="1.0.0",
        health_message="ok",
        foundry_agent_name="shared-foundry",
    )
    mock_factory.return_value = _mock_table_client([e1, e2])

    with pytest.raises(ValueError, match="Duplicate Foundry agent name"):
        load_agent_definitions_from_db(connection_string="fake")


@patch("a2a_servers.agent_store._make_table_client")
def test_load_from_db_invalid_record_raises(mock_factory: MagicMock) -> None:
    entity = _make_entity()
    del entity["public_name"]  # make it invalid
    mock_factory.return_value = _mock_table_client([entity])

    with pytest.raises(ValueError, match="Failed to load"):
        load_agent_definitions_from_db(connection_string="fake")


@patch("a2a_servers.agent_store._make_table_client")
def test_load_from_db_uses_custom_table_name(mock_factory: MagicMock) -> None:
    entity = _make_entity()
    mock_factory.return_value = _mock_table_client([entity])

    load_agent_definitions_from_db(connection_string="fake", table_name="custom-table")

    mock_factory.assert_called_once_with("custom-table", "fake", None)


# ---------------------------------------------------------------------------
# seed_agents_to_db – with mocked clients
# ---------------------------------------------------------------------------


@patch("a2a_servers.agent_store._make_table_client")
@patch("a2a_servers.agent_store._make_service_client")
def test_seed_creates_table_and_upserts(
    mock_svc_factory: MagicMock, mock_tbl_factory: MagicMock
) -> None:
    svc_client = MagicMock()
    tbl_client = MagicMock()
    mock_svc_factory.return_value = svc_client
    mock_tbl_factory.return_value = tbl_client

    seed_agents_to_db((_DEFINITION,), connection_string="fake")

    svc_client.create_table_if_not_exists.assert_called_once_with(
        table_name=DEFAULT_TABLE_NAME
    )
    tbl_client.upsert_entity.assert_called_once()
    call_kwargs = tbl_client.upsert_entity.call_args
    assert call_kwargs.kwargs["mode"] == "replace"
    entity = call_kwargs.kwargs["entity"]
    assert entity["RowKey"] == "math"


@patch("a2a_servers.agent_store._make_table_client")
@patch("a2a_servers.agent_store._make_service_client")
def test_seed_uses_custom_table_name(
    mock_svc_factory: MagicMock, mock_tbl_factory: MagicMock
) -> None:
    mock_svc_factory.return_value = MagicMock()
    mock_tbl_factory.return_value = MagicMock()

    seed_agents_to_db((_DEFINITION,), connection_string="fake", table_name="my-table")

    mock_svc_factory.return_value.create_table_if_not_exists.assert_called_once_with(
        table_name="my-table"
    )
