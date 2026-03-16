from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from a2a.types import AgentSkill

DEFAULT_AGENT_CONFIG_DIR = Path(__file__).resolve().parent / "agents"
AGENT_CONFIG_GLOB = "*_agent.toml"


@dataclass(frozen=True)
class AgentDefinition:
    slug: str
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


def _normalize_agent_slug(raw_slug: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw_slug.strip().lower()).strip("-")
    if not slug:
        raise ValueError("Agent slug must contain at least one letter or number")
    return slug


def _derive_agent_slug(path: Path) -> str:
    stem = path.stem
    for suffix in ("_agent", "-agent"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return _normalize_agent_slug(stem)


def resolve_agent_config_dir(config_dir: str | None = None) -> Path:
    raw_path = (config_dir or os.getenv("A2A_AGENT_CONFIG_DIR") or "").strip()
    if raw_path:
        return Path(raw_path).expanduser()
    return DEFAULT_AGENT_CONFIG_DIR


def discover_agent_definition_paths(config_dir: str | None = None) -> tuple[Path, ...]:
    directory = resolve_agent_config_dir(config_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Agent config directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Agent config path is not a directory: {directory}")

    paths = tuple(sorted(path.resolve() for path in directory.glob(AGENT_CONFIG_GLOB)))
    if not paths:
        raise FileNotFoundError(
            f"No agent config files matching `{AGENT_CONFIG_GLOB}` found in {directory}"
        )
    return paths


def load_agent_definition(config_path: str | Path) -> AgentDefinition:
    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Agent config file not found: {path}. "
            "Create one from `agents/agent.template.toml`."
        )

    with path.open("rb") as handle:
        document = tomllib.load(handle)

    a2a = document.get("a2a")
    if not isinstance(a2a, dict):
        raise ValueError("Agent config must define an `[a2a]` section")

    foundry = document.get("foundry")
    if not isinstance(foundry, dict):
        raise ValueError("Agent config must define a `[foundry]` section")

    skills_table = document.get("skills", [])
    if not isinstance(skills_table, list) or not skills_table:
        raise ValueError("Agent config must define at least one `[[skills]]` entry")

    smoke_tests = document.get("smoke_tests")
    if smoke_tests is None:
        smoke_tests = {}
    if not isinstance(smoke_tests, dict):
        raise ValueError("`[smoke_tests]` must be a table if provided")

    foundry_agent_name = _read_required_string(foundry, "agent_name", "foundry")

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

    slug_value = a2a.get("slug")
    if slug_value is not None and not isinstance(slug_value, str):
        raise ValueError("`a2a.slug` must be a string if provided")

    slug = (
        _normalize_agent_slug(slug_value)
        if isinstance(slug_value, str) and slug_value.strip()
        else _derive_agent_slug(path)
    )

    return AgentDefinition(
        slug=slug,
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


def load_agent_definitions(
    config_dir: str | None = None,
) -> tuple[AgentDefinition, ...]:
    definitions = tuple(
        load_agent_definition(path)
        for path in discover_agent_definition_paths(config_dir)
    )

    seen_slugs: dict[str, Path] = {}
    seen_foundry_names: dict[str, Path] = {}
    seen_paths: set[Path] = set()

    for definition in definitions:
        if definition.source_path in seen_paths:
            raise ValueError(
                f"Duplicate agent config path detected: {definition.source_path}"
            )
        seen_paths.add(definition.source_path)

        previous_slug_path = seen_slugs.get(definition.slug)
        if previous_slug_path is not None:
            raise ValueError(
                "Duplicate agent slug "
                f"`{definition.slug}` in {previous_slug_path} and {definition.source_path}"
            )
        seen_slugs[definition.slug] = definition.source_path

        previous_foundry_path = seen_foundry_names.get(definition.foundry_agent_name)
        if previous_foundry_path is not None:
            raise ValueError(
                "Duplicate Foundry agent name "
                f"`{definition.foundry_agent_name}` in "
                f"{previous_foundry_path} and {definition.source_path}"
            )
        seen_foundry_names[definition.foundry_agent_name] = definition.source_path

    return definitions
