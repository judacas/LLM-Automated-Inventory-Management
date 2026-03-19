from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from a2a.types import AgentSkill

from a2a_servers.agent_definition import (
    _normalize_agent_slug,
    _read_required_string,
    _read_string_list,
    resolve_agent_config_dir,
)

GROUP_CONFIG_GLOB = "*_group.toml"


@dataclass(frozen=True)
class GroupDefinition:
    """Config for a grouped A2A endpoint that routes to individual agent endpoints."""

    slug: str
    source_path: Path
    public_name: str
    description: str
    version: str
    health_message: str
    # Slugs of individual agents this group is allowed to route to.
    member_slugs: frozenset[str]
    default_input_modes: tuple[str, ...]
    default_output_modes: tuple[str, ...]
    skills: tuple[AgentSkill, ...]
    smoke_test_prompts: tuple[str, ...]


def _derive_group_slug(path: Path) -> str:
    """Derive a URL slug from a group config filename, stripping the `_group` suffix."""
    stem = path.stem
    for suffix in ("_group", "-group"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return _normalize_agent_slug(stem)


def discover_group_definition_paths(config_dir: str | None = None) -> tuple[Path, ...]:
    """Return sorted paths of all `*_group.toml` files in the config directory."""
    directory = resolve_agent_config_dir(config_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Agent config directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Agent config path is not a directory: {directory}")
    return tuple(sorted(path.resolve() for path in directory.glob(GROUP_CONFIG_GLOB)))


def load_group_definition(config_path: str | Path) -> GroupDefinition:
    """Load and validate a single `*_group.toml` file."""
    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Group config file not found: {path}. "
            "Create one from `agents/group.template.toml`."
        )

    with path.open("rb") as handle:
        document = tomllib.load(handle)

    a2a = document.get("a2a")
    if not isinstance(a2a, dict):
        raise ValueError("Group config must define an `[a2a]` section")

    group = document.get("group")
    if not isinstance(group, dict):
        raise ValueError("Group config must define a `[group]` section")

    agents_list = group.get("agents", [])
    if not isinstance(agents_list, list) or not agents_list:
        raise ValueError("`group.agents` must be a non-empty list of agent slugs")
    for item in agents_list:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("`group.agents` must be a list of non-empty strings")
    member_slugs = frozenset(_normalize_agent_slug(s) for s in agents_list)

    skills_table = document.get("skills", [])
    if not isinstance(skills_table, list) or not skills_table:
        raise ValueError("Group config must define at least one `[[skills]]` entry")

    smoke_tests = document.get("smoke_tests")
    if smoke_tests is None:
        smoke_tests = {}
    if not isinstance(smoke_tests, dict):
        raise ValueError("`[smoke_tests]` must be a table if provided")

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

    slug_value = a2a.get("slug")
    if slug_value is not None and not isinstance(slug_value, str):
        raise ValueError("`a2a.slug` must be a string if provided")

    slug = (
        _normalize_agent_slug(slug_value)
        if isinstance(slug_value, str) and slug_value.strip()
        else _derive_group_slug(path)
    )

    return GroupDefinition(
        slug=slug,
        source_path=path,
        public_name=_read_required_string(a2a, "name", "a2a"),
        description=_read_required_string(a2a, "description", "a2a"),
        version=_read_required_string(a2a, "version", "a2a"),
        health_message=_read_required_string(a2a, "health_message", "a2a"),
        member_slugs=member_slugs,
        default_input_modes=_read_string_list(
            a2a, "default_input_modes", default=["text"]
        ),
        default_output_modes=_read_string_list(
            a2a, "default_output_modes", default=["text"]
        ),
        skills=tuple(skills),
        smoke_test_prompts=_read_string_list(smoke_tests, "prompts"),
    )


def load_group_definitions(
    config_dir: str | None = None,
) -> tuple[GroupDefinition, ...]:
    """Load all `*_group.toml` files from the config directory.

    Returns an empty tuple if no group configs are found (groups are optional).
    """
    paths = discover_group_definition_paths(config_dir)
    definitions = tuple(load_group_definition(path) for path in paths)

    seen_slugs: dict[str, Path] = {}
    for definition in definitions:
        previous = seen_slugs.get(definition.slug)
        if previous is not None:
            raise ValueError(
                f"Duplicate group slug `{definition.slug}` in "
                f"{previous} and {definition.source_path}"
            )
        seen_slugs[definition.slug] = definition.source_path

    return definitions
