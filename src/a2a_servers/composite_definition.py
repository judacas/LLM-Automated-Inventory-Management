"""Composite agent definitions that group multiple Foundry agents under one A2A endpoint.

This module solves the Azure AI Foundry limitation where a Foundry agent can only connect
to a single A2A remote agent at a time.  A composite agent presents all member agents'
skills under one unified A2A endpoint and routes each incoming request to the correct
Foundry backend based on keyword (regex) matching.

Config files matching ``agents/*_composite.toml`` are auto-discovered by
:func:`discover_composite_agent_definition_paths`.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from a2a.types import AgentSkill
from agent_definition import (
    AgentDefinition,
    _normalize_agent_slug,
    _read_required_string,
    _read_string_list,
    load_agent_definition,
    resolve_agent_config_dir,
)

COMPOSITE_CONFIG_GLOB = "*_composite.toml"


def _derive_composite_slug(path: Path) -> str:
    """Derive a URL slug from a composite config filename.

    Strips the ``_composite`` or ``-composite`` suffix before normalising,
    so ``contoso_composite.toml`` becomes ``contoso``.
    """
    stem = path.stem
    for suffix in ("_composite", "-composite"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    slug: str = _normalize_agent_slug(stem)
    return slug


@dataclass(frozen=True)
class CompositeMemberDefinition:
    """One member of a composite agent: an underlying agent plus its routing keywords."""

    agent_definition: AgentDefinition
    # Compiled regex patterns; a message matching ANY pattern is routed to this member.
    keyword_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class CompositeAgentDefinition:
    """A virtual agent that exposes multiple Foundry agents as a single A2A endpoint.

    Skills are aggregated from all members.  Routing is determined by the first member
    whose keyword patterns match the incoming message text.  If no member matches, the
    first member is used as the default.
    """

    slug: str
    source_path: Path
    public_name: str
    description: str
    version: str
    health_message: str
    default_input_modes: tuple[str, ...]
    default_output_modes: tuple[str, ...]
    supports_streaming: bool
    members: tuple[CompositeMemberDefinition, ...]

    @property
    def skills(self) -> tuple[AgentSkill, ...]:
        """All skills from all member agents, in member order."""
        return tuple(
            skill for member in self.members for skill in member.agent_definition.skills
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compile_keyword_patterns(
    keywords: list[str], entry_label: str
) -> tuple[re.Pattern[str], ...]:
    patterns: list[re.Pattern[str]] = []
    for keyword in keywords:
        try:
            patterns.append(re.compile(keyword.strip(), re.IGNORECASE))
        except re.error as exc:
            raise ValueError(
                f"`{entry_label}` contains an invalid regex pattern {keyword!r}: {exc}"
            ) from exc
    return tuple(patterns)


# ---------------------------------------------------------------------------
# Public loading API
# ---------------------------------------------------------------------------


def load_composite_agent_definition(
    config_path: str | Path,
) -> CompositeAgentDefinition:
    """Parse a ``*_composite.toml`` file and return a :class:`CompositeAgentDefinition`.

    Member agent configs referenced by ``config`` keys are resolved relative to the
    composite config file's directory.
    """
    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Composite agent config file not found: {path}. "
            "Create one from `agents/composite.template.toml`."
        )

    with path.open("rb") as handle:
        document = tomllib.load(handle)

    composite = document.get("composite")
    if not isinstance(composite, dict):
        raise ValueError("Composite agent config must define a `[composite]` section")

    members_raw = composite.get("members", [])
    if not isinstance(members_raw, list) or not members_raw:
        raise ValueError(
            "Composite agent config must define at least one "
            "`[[composite.members]]` entry"
        )

    slug_value = composite.get("slug")
    if slug_value is not None and not isinstance(slug_value, str):
        raise ValueError("`composite.slug` must be a string if provided")

    slug = (
        _normalize_agent_slug(slug_value)
        if isinstance(slug_value, str) and slug_value.strip()
        else _derive_composite_slug(path)
    )

    streaming_value = composite.get("streaming", True)
    if not isinstance(streaming_value, bool):
        raise ValueError("`composite.streaming` must be a boolean")

    members: list[CompositeMemberDefinition] = []
    for index, member_data in enumerate(members_raw, start=1):
        if not isinstance(member_data, dict):
            raise ValueError(f"`[[composite.members]]` entry #{index} must be a table")

        config_value = member_data.get("config")
        if not isinstance(config_value, str) or not config_value.strip():
            raise ValueError(
                f"`[[composite.members]]` entry #{index} is missing the "
                "required `config` key"
            )

        member_config_path = (path.parent / config_value.strip()).resolve()
        agent_def = load_agent_definition(member_config_path)

        keywords_raw = member_data.get("keywords", [])
        if not isinstance(keywords_raw, list):
            raise ValueError(
                f"`[[composite.members]]` entry #{index} "
                "`keywords` must be a list of strings"
            )
        if any(not isinstance(k, str) or not k.strip() for k in keywords_raw):
            raise ValueError(
                f"`[[composite.members]]` entry #{index} "
                "`keywords` must be a list of non-empty strings"
            )

        patterns = _compile_keyword_patterns(
            [str(k) for k in keywords_raw],
            f"composite.members[{index}].keywords",
        )

        members.append(
            CompositeMemberDefinition(
                agent_definition=agent_def,
                keyword_patterns=patterns,
            )
        )

    return CompositeAgentDefinition(
        slug=slug,
        source_path=path,
        public_name=_read_required_string(composite, "name", "composite"),
        description=_read_required_string(composite, "description", "composite"),
        version=_read_required_string(composite, "version", "composite"),
        health_message=_read_required_string(composite, "health_message", "composite"),
        default_input_modes=_read_string_list(
            composite, "default_input_modes", default=["text"]
        ),
        default_output_modes=_read_string_list(
            composite, "default_output_modes", default=["text"]
        ),
        supports_streaming=streaming_value,
        members=tuple(members),
    )


def discover_composite_agent_definition_paths(
    config_dir: str | None = None,
) -> tuple[Path, ...]:
    """Return sorted paths for every ``*_composite.toml`` in *config_dir*.

    Returns an empty tuple (not an error) when no composite configs are found —
    composite agents are optional.
    """
    directory = resolve_agent_config_dir(config_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Agent config directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Agent config path is not a directory: {directory}")

    return tuple(
        sorted(path.resolve() for path in directory.glob(COMPOSITE_CONFIG_GLOB))
    )


def load_composite_agent_definitions(
    config_dir: str | None = None,
) -> tuple[CompositeAgentDefinition, ...]:
    """Load all composite agent definitions from *config_dir*.

    Returns an empty tuple when no composite config files are present.
    Raises :class:`ValueError` on duplicate composite slugs.
    """
    paths = discover_composite_agent_definition_paths(config_dir)
    if not paths:
        return ()

    definitions = tuple(load_composite_agent_definition(path) for path in paths)

    seen_slugs: dict[str, Path] = {}
    for definition in definitions:
        previous = seen_slugs.get(definition.slug)
        if previous is not None:
            raise ValueError(
                f"Duplicate composite agent slug `{definition.slug}` "
                f"in {previous} and {definition.source_path}"
            )
        seen_slugs[definition.slug] = definition.source_path

    return definitions
