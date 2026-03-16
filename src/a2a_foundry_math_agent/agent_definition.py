from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from a2a.types import AgentSkill


@dataclass(frozen=True)
class AgentDefinition:
    source_path: Path
    public_name: str
    description: str
    version: str
    health_message: str
    foundry_agent_name: str
    default_input_modes: tuple[str, ...]
    default_output_modes: tuple[str, ...]
    skills: tuple[AgentSkill, ...]
    smoke_test_prompts: tuple[str, ...]
    supports_streaming: bool = True


def _read_required_string(mapping: dict[str, object], key: str, section: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required string `{section}.{key}` in agent config")
    return value.strip()


def _read_string_list(
    mapping: dict[str, object],
    key: str,
    *,
    default: list[str] | None = None,
) -> tuple[str, ...]:
    value = mapping.get(key, default if default is not None else [])
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"`{key}` must be a list of non-empty strings")
    return tuple(item.strip() for item in value)


def resolve_agent_definition_path(config_path: str | None = None) -> Path:
    raw_path = (
        config_path or os.getenv("A2A_AGENT_DEFINITION") or "agent.toml"
    ).strip()
    return Path(raw_path).expanduser()


def load_agent_definition(config_path: str | None = None) -> AgentDefinition:
    path = resolve_agent_definition_path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Agent config file not found: {path}. "
            "Create one from `agent.template.toml` or set A2A_AGENT_DEFINITION."
        )

    with path.open("rb") as handle:
        document = tomllib.load(handle)

    a2a = document.get("a2a")
    if not isinstance(a2a, dict):
        raise ValueError("Agent config must define an `[a2a]` section")

    foundry = document.get("foundry")
    if not isinstance(foundry, dict):
        foundry = {}

    skills_table = document.get("skills", [])
    if not isinstance(skills_table, list) or not skills_table:
        raise ValueError("Agent config must define at least one `[[skills]]` entry")

    smoke_tests = document.get("smoke_tests")
    if smoke_tests is None:
        smoke_tests = {}
    if not isinstance(smoke_tests, dict):
        raise ValueError("`[smoke_tests]` must be a table if provided")

    foundry_agent_name = (
        foundry.get("agent_name")
        if isinstance(foundry.get("agent_name"), str)
        else os.getenv("AZURE_AI_AGENT_NAME", "").strip()
    )
    if not foundry_agent_name:
        raise ValueError(
            "Agent config must define `foundry.agent_name` or set AZURE_AI_AGENT_NAME."
        )

    skills: list[AgentSkill] = []
    for index, skill_data in enumerate(skills_table, start=1):
        if not isinstance(skill_data, dict):
            raise ValueError(f"`[[skills]]` entry #{index} must be a table")

        skill = AgentSkill(
            id=_read_required_string(skill_data, "id", f"skills[{index}]"),
            name=_read_required_string(skill_data, "name", f"skills[{index}]"),
            description=_read_required_string(
                skill_data, "description", f"skills[{index}]"
            ),
            tags=list(_read_string_list(skill_data, "tags")),
            examples=list(_read_string_list(skill_data, "examples")),
        )
        skills.append(skill)

    streaming_value = a2a.get("streaming", True)
    if not isinstance(streaming_value, bool):
        raise ValueError("`a2a.streaming` must be a boolean")

    return AgentDefinition(
        source_path=path,
        public_name=_read_required_string(a2a, "name", "a2a"),
        description=_read_required_string(a2a, "description", "a2a"),
        version=_read_required_string(a2a, "version", "a2a"),
        health_message=_read_required_string(a2a, "health_message", "a2a"),
        foundry_agent_name=foundry_agent_name,
        default_input_modes=_read_string_list(
            a2a, "default_input_modes", default=["text"]
        ),
        default_output_modes=_read_string_list(
            a2a, "default_output_modes", default=["text"]
        ),
        skills=tuple(skills),
        smoke_test_prompts=_read_string_list(smoke_tests, "prompts"),
        supports_streaming=streaming_value,
    )
