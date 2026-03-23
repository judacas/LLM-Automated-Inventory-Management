from __future__ import annotations

import logging
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from a2a.types import AgentSkill

DEFAULT_AGENT_CONFIG_DIR = Path(__file__).resolve().parent / "agents"
AGENT_CONFIG_GLOB = "*_agent.toml"

logger = logging.getLogger(__name__)


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


def _parse_agent_definition(
    document: dict[str, object], path: Path
) -> AgentDefinition:
    """Parse a validated TOML document into an :class:`AgentDefinition`.

    ``path`` is used as the ``source_path`` on the result and for deriving the
    slug when no explicit ``a2a.slug`` is provided.  For configs loaded from
    remote storage it can be a virtual ``Path`` such as
    ``Path("email_agent.toml")`` – it does not need to exist on disk.
    """
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


def load_agent_definition(config_path: str | Path) -> AgentDefinition:
    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Agent config file not found: {path}. "
            "Create one from `agents/agent.template.toml`."
        )

    with path.open("rb") as handle:
        document = tomllib.load(handle)

    return _parse_agent_definition(document, path)


def load_agent_definition_from_content(
    content: bytes, virtual_path: Path
) -> AgentDefinition:
    """Parse an agent definition from raw TOML bytes.

    ``virtual_path`` is used to derive the slug when no explicit ``a2a.slug``
    is set, and is recorded in :attr:`AgentDefinition.source_path`.  It does
    not need to point to a real file on disk.

    This is the loading path used when configs are fetched from remote storage
    (for example Azure Blob Storage) rather than read from local disk.
    """
    document = tomllib.loads(content.decode("utf-8"))
    return _parse_agent_definition(document, virtual_path)


def _validate_no_duplicates(definitions: tuple[AgentDefinition, ...]) -> None:
    """Raise :exc:`ValueError` if any slugs or Foundry agent names are duplicated."""
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


def load_agent_definitions(
    config_dir: str | None = None,
) -> tuple[AgentDefinition, ...]:
    definitions = tuple(
        load_agent_definition(path)
        for path in discover_agent_definition_paths(config_dir)
    )
    _validate_no_duplicates(definitions)
    return definitions


def load_agent_definitions_from_blob(
    container_url: str,
    *,
    conn_str: str | None = None,
) -> tuple[AgentDefinition, ...]:
    """Download and load all ``*_agent.toml`` configs from an Azure Blob container.

    Authentication is resolved in this order:

    1. **Connection string** – if ``conn_str`` is provided (or the
       ``A2A_AGENT_CONFIG_BLOB_CONN_STR`` environment variable is set), a
       ``BlobServiceClient`` is built from it and the container name is
       derived from the last path segment of *container_url*.  This is the
       recommended approach for local testing with the Azurite emulator.

    2. **DefaultAzureCredential** – used in all other cases, including managed
       identity in Azure App Service.

    Only blobs whose names end with ``_agent.toml`` are loaded.  Blobs ending
    with ``_agent.sample.toml`` are silently skipped, matching the local
    discovery convention.

    Raises :exc:`FileNotFoundError` if no matching blobs are found.
    Raises :exc:`ValueError` if duplicate slugs or Foundry agent names are
    detected across the loaded definitions.
    """
    from azure.storage.blob import BlobServiceClient, ContainerClient

    resolved_conn_str = (conn_str or os.getenv("A2A_AGENT_CONFIG_BLOB_CONN_STR") or "").strip() or None

    if resolved_conn_str:
        container_name = container_url.rstrip("/").rsplit("/", 1)[-1]
        logger.debug(
            "Connecting to blob container %r via connection string", container_name
        )
        client: ContainerClient = BlobServiceClient.from_connection_string(
            resolved_conn_str
        ).get_container_client(container_name)
    else:
        from azure.identity import DefaultAzureCredential

        logger.debug(
            "Connecting to blob container %r via DefaultAzureCredential", container_url
        )
        client = ContainerClient.from_container_url(
            container_url, credential=DefaultAzureCredential()
        )

    paths_and_contents: list[tuple[Path, bytes]] = []
    for blob in client.list_blobs():
        name: str = blob.name  # type: ignore[assignment]
        if not name.endswith("_agent.toml"):
            continue
        if name.endswith("_agent.sample.toml"):
            continue
        blob_client = client.get_blob_client(name)
        raw = blob_client.download_blob().readall()
        virtual_path = Path(name)
        paths_and_contents.append((virtual_path, raw))
        logger.debug("Downloaded agent config blob: %s", name)

    if not paths_and_contents:
        raise FileNotFoundError(
            f"No agent config files matching `{AGENT_CONFIG_GLOB}` "
            f"found in blob container: {container_url}"
        )

    definitions = tuple(
        load_agent_definition_from_content(content, path)
        for path, content in sorted(paths_and_contents, key=lambda x: x[0].name)
    )
    _validate_no_duplicates(definitions)
    logger.info(
        "Loaded %d agent definition(s) from blob storage: %s",
        len(definitions),
        container_url,
    )
    return definitions
