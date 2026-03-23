"""Unit tests for src/a2a_servers/agent_definition.py."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agent_definition import (
    AgentDefinition,
    _derive_agent_slug,
    _normalize_agent_slug,
    load_agent_definition,
    load_agent_definition_from_content,
    load_agent_definitions,
    load_agent_definitions_from_blob,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_TOML = textwrap.dedent("""\
    [a2a]
    name = "Math Agent"
    description = "Solves math problems"
    version = "1.0.0"
    health_message = "OK"
    default_input_modes = ["text"]
    default_output_modes = ["text"]

    [foundry]
    agent_name = "math-foundry-agent"

    [[skills]]
    id = "math"
    name = "Math"
    description = "Performs arithmetic"
    tags = ["math"]
    examples = ["2 + 2"]

    [smoke_tests]
    prompts = ["What is 1+1?"]
""")


def _write_toml(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _normalize_agent_slug
# ---------------------------------------------------------------------------


def test_normalize_slug_basic() -> None:
    assert _normalize_agent_slug("hello world") == "hello-world"


def test_normalize_slug_uppercase() -> None:
    assert _normalize_agent_slug("MyAgent") == "myagent"


def test_normalize_slug_special_chars() -> None:
    assert _normalize_agent_slug("  math!@#agent  ") == "math-agent"


def test_normalize_slug_multiple_separators() -> None:
    assert _normalize_agent_slug("math---agent") == "math-agent"


def test_normalize_slug_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one letter or number"):
        _normalize_agent_slug("---")


def test_normalize_slug_whitespace_only_raises() -> None:
    with pytest.raises(ValueError, match="at least one letter or number"):
        _normalize_agent_slug("   ")


# ---------------------------------------------------------------------------
# _derive_agent_slug
# ---------------------------------------------------------------------------


def test_derive_slug_strips_agent_suffix() -> None:
    assert _derive_agent_slug(Path("math_agent.toml")) == "math"


def test_derive_slug_strips_dash_agent_suffix() -> None:
    assert _derive_agent_slug(Path("quote-agent.toml")) == "quote"


def test_derive_slug_no_suffix() -> None:
    assert _derive_agent_slug(Path("assistant.toml")) == "assistant"


def test_derive_slug_case_insensitive_suffix() -> None:
    assert _derive_agent_slug(Path("MATH_AGENT.toml")) == "math"


# ---------------------------------------------------------------------------
# load_agent_definition – happy path
# ---------------------------------------------------------------------------


def test_load_valid_definition(tmp_path: Path) -> None:
    p = _write_toml(tmp_path, "math_agent.toml", _VALID_TOML)
    defn = load_agent_definition(p)

    assert isinstance(defn, AgentDefinition)
    assert defn.slug == "math"  # derived from filename
    assert defn.public_name == "Math Agent"
    assert defn.foundry_agent_name == "math-foundry-agent"
    assert defn.version == "1.0.0"
    assert len(defn.skills) == 1
    assert defn.skills[0].id == "math"
    assert defn.smoke_test_prompts == ("What is 1+1?",)
    assert defn.supports_streaming is True


def test_load_explicit_slug_overrides_filename(tmp_path: Path) -> None:
    # Re-write a fresh file; the explicit slug key overrides the filename
    content = textwrap.dedent("""\
        [a2a]
        name = "Math Agent"
        description = "Solves math problems"
        version = "1.0.0"
        health_message = "OK"
        slug = "custom-slug"

        [foundry]
        agent_name = "math-foundry-agent"

        [[skills]]
        id = "math"
        name = "Math"
        description = "Performs arithmetic"
    """)
    p = _write_toml(tmp_path, "math_agent.toml", content)
    defn = load_agent_definition(p)
    assert defn.slug == "custom-slug"


def test_load_streaming_defaults_to_true(tmp_path: Path) -> None:
    p = _write_toml(tmp_path, "math_agent.toml", _VALID_TOML)
    defn = load_agent_definition(p)
    assert defn.supports_streaming is True


def test_load_streaming_can_be_disabled(tmp_path: Path) -> None:
    content = _VALID_TOML.replace("[a2a]", "[a2a]\nstreaming = false", 1)
    p = _write_toml(tmp_path, "math_agent.toml", content)
    defn = load_agent_definition(p)
    assert defn.supports_streaming is False


# ---------------------------------------------------------------------------
# load_agent_definition – missing required sections
# ---------------------------------------------------------------------------


def test_missing_a2a_section_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        [foundry]
        agent_name = "x"

        [[skills]]
        id = "s"
        name = "S"
        description = "desc"
    """)
    p = _write_toml(tmp_path, "math_agent.toml", content)
    with pytest.raises(ValueError, match=r"\[a2a\]"):
        load_agent_definition(p)


def test_missing_foundry_section_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        [a2a]
        name = "X"
        description = "d"
        version = "1"
        health_message = "ok"

        [[skills]]
        id = "s"
        name = "S"
        description = "desc"
    """)
    p = _write_toml(tmp_path, "math_agent.toml", content)
    with pytest.raises(ValueError, match=r"\[foundry\]"):
        load_agent_definition(p)


def test_missing_skills_section_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        [a2a]
        name = "X"
        description = "d"
        version = "1"
        health_message = "ok"

        [foundry]
        agent_name = "x"
    """)
    p = _write_toml(tmp_path, "math_agent.toml", content)
    with pytest.raises(ValueError, match=r"\[\[skills\]\]"):
        load_agent_definition(p)


# ---------------------------------------------------------------------------
# load_agent_definition – missing required keys inside sections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_key", ["name", "description", "version", "health_message"]
)
def test_missing_required_a2a_key_raises(tmp_path: Path, missing_key: str) -> None:
    lines = [
        line
        for line in _VALID_TOML.splitlines()
        if not line.startswith(missing_key + " =")
    ]
    p = _write_toml(tmp_path, "math_agent.toml", "\n".join(lines))
    with pytest.raises(ValueError):
        load_agent_definition(p)


def test_missing_foundry_agent_name_raises(tmp_path: Path) -> None:
    content = _VALID_TOML.replace('agent_name = "math-foundry-agent"\n', "")
    p = _write_toml(tmp_path, "math_agent.toml", content)
    with pytest.raises(ValueError, match="foundry.agent_name"):
        load_agent_definition(p)


# ---------------------------------------------------------------------------
# load_agent_definition – type validation
# ---------------------------------------------------------------------------


def test_streaming_must_be_bool_raises(tmp_path: Path) -> None:
    content = _VALID_TOML.replace("[a2a]", "[a2a]\nstreaming = 1", 1)
    p = _write_toml(tmp_path, "math_agent.toml", content)
    with pytest.raises(ValueError, match="streaming"):
        load_agent_definition(p)


def test_slug_must_be_string_raises(tmp_path: Path) -> None:
    content = _VALID_TOML.replace("[a2a]", "[a2a]\nslug = 123", 1)
    p = _write_toml(tmp_path, "math_agent.toml", content)
    with pytest.raises(ValueError, match="slug"):
        load_agent_definition(p)


def test_file_not_found_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_agent_definition(tmp_path / "nonexistent_agent.toml")


# ---------------------------------------------------------------------------
# load_agent_definitions – duplicate detection
# ---------------------------------------------------------------------------


def test_duplicate_slugs_raises(tmp_path: Path) -> None:
    # Both files have an explicit slug = "math" and both match *_agent.toml
    for name, foundry in (
        ("alpha_agent.toml", "alpha-foundry"),
        ("beta_agent.toml", "beta-foundry"),
    ):
        toml_content = textwrap.dedent(f"""\
            [a2a]
            name = "Math Agent"
            description = "desc"
            version = "1.0.0"
            health_message = "ok"
            slug = "math"

            [foundry]
            agent_name = "{foundry}"

            [[skills]]
            id = "s"
            name = "S"
            description = "desc"
        """)
        _write_toml(tmp_path, name, toml_content)

    with pytest.raises(ValueError, match="Duplicate agent slug"):
        load_agent_definitions(str(tmp_path))


def test_duplicate_foundry_names_raises(tmp_path: Path) -> None:
    for name, slug in (("alpha_agent.toml", "alpha"), ("beta_agent.toml", "beta")):
        toml_content = textwrap.dedent(f"""\
            [a2a]
            name = "Agent {slug}"
            description = "desc"
            version = "1.0.0"
            health_message = "ok"

            [foundry]
            agent_name = "shared-foundry-agent"

            [[skills]]
            id = "s"
            name = "S"
            description = "desc"
        """)
        _write_toml(tmp_path, name, toml_content)

    with pytest.raises(ValueError, match="Duplicate Foundry agent name"):
        load_agent_definitions(str(tmp_path))


def test_load_multiple_valid_definitions(tmp_path: Path) -> None:
    for slug, foundry in (("math", "math-agent"), ("quote", "quote-agent")):
        toml_content = textwrap.dedent(f"""\
            [a2a]
            name = "{slug.title()} Agent"
            description = "desc"
            version = "1.0.0"
            health_message = "ok"

            [foundry]
            agent_name = "{foundry}"

            [[skills]]
            id = "skill-{slug}"
            name = "Skill"
            description = "desc"
        """)
        _write_toml(tmp_path, f"{slug}_agent.toml", toml_content)

    definitions = load_agent_definitions(str(tmp_path))
    assert len(definitions) == 2
    slugs = {d.slug for d in definitions}
    assert slugs == {"math", "quote"}


def test_empty_config_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No agent config files"):
        load_agent_definitions(str(tmp_path))


def test_nonexistent_config_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        load_agent_definitions(str(tmp_path / "does_not_exist"))


# ---------------------------------------------------------------------------
# load_agent_definition_from_content
# ---------------------------------------------------------------------------


def test_load_from_content_happy_path() -> None:
    """Content-based loading produces the same result as file-based loading."""
    virtual_path = Path("math_agent.toml")
    defn = load_agent_definition_from_content(_VALID_TOML.encode(), virtual_path)

    assert isinstance(defn, AgentDefinition)
    assert defn.slug == "math"
    assert defn.public_name == "Math Agent"
    assert defn.foundry_agent_name == "math-foundry-agent"
    assert defn.source_path == virtual_path
    assert len(defn.skills) == 1
    assert defn.smoke_test_prompts == ("What is 1+1?",)


def test_load_from_content_explicit_slug() -> None:
    content = _VALID_TOML.replace("[a2a]", "[a2a]\nslug = \"custom\"", 1)
    defn = load_agent_definition_from_content(content.encode(), Path("math_agent.toml"))
    assert defn.slug == "custom"


def test_load_from_content_invalid_toml_raises() -> None:
    with pytest.raises(Exception):
        load_agent_definition_from_content(b"this is not toml!!!", Path("bad_agent.toml"))


def test_load_from_content_missing_a2a_section_raises() -> None:
    content = textwrap.dedent("""\
        [foundry]
        agent_name = "x"

        [[skills]]
        id = "s"
        name = "S"
        description = "desc"
    """)
    with pytest.raises(ValueError, match=r"\[a2a\]"):
        load_agent_definition_from_content(content.encode(), Path("bad_agent.toml"))


# ---------------------------------------------------------------------------
# load_agent_definitions_from_blob
# ---------------------------------------------------------------------------

_MATH_TOML = _VALID_TOML.encode()
_QUOTE_TOML = textwrap.dedent("""\
    [a2a]
    name = "Quote Agent"
    description = "Handles quotes"
    version = "1.0.0"
    health_message = "OK"

    [foundry]
    agent_name = "quote-foundry-agent"

    [[skills]]
    id = "quoting"
    name = "Quoting"
    description = "Creates quotes"
""").encode()


def _make_blob_mock(name: str) -> MagicMock:
    blob = MagicMock()
    blob.name = name
    return blob


def _make_blob_client_mock(content: bytes) -> MagicMock:
    downloader = MagicMock()
    downloader.readall.return_value = content
    blob_client = MagicMock()
    blob_client.download_blob.return_value = downloader
    return blob_client


def _build_container_client_mock(blobs: dict[str, bytes]) -> MagicMock:
    """Build a ContainerClient mock that lists *blobs* and serves their content."""
    container_mock = MagicMock()
    container_mock.list_blobs.return_value = [_make_blob_mock(n) for n in blobs]

    def get_blob_client(name: str) -> MagicMock:
        return _make_blob_client_mock(blobs[name])

    container_mock.get_blob_client.side_effect = get_blob_client
    return container_mock


def test_load_from_blob_with_default_credential() -> None:
    """DefaultAzureCredential path is used when no connection string is set."""
    container_mock = _build_container_client_mock({"math_agent.toml": _MATH_TOML})

    with (
        patch("azure.storage.blob.ContainerClient.from_container_url", return_value=container_mock),
        patch("azure.identity.DefaultAzureCredential"),
    ):
        definitions = load_agent_definitions_from_blob("https://fake.blob.core.windows.net/configs")

    assert len(definitions) == 1
    assert definitions[0].slug == "math"
    assert definitions[0].public_name == "Math Agent"


def test_load_from_blob_with_conn_str() -> None:
    """Connection-string path is used when conn_str is provided."""
    container_mock = _build_container_client_mock(
        {
            "math_agent.toml": _MATH_TOML,
            "quote_agent.toml": _QUOTE_TOML,
        }
    )

    blob_service_mock = MagicMock()
    blob_service_mock.get_container_client.return_value = container_mock

    with patch(
        "azure.storage.blob.BlobServiceClient.from_connection_string",
        return_value=blob_service_mock,
    ):
        definitions = load_agent_definitions_from_blob(
            "http://127.0.0.1:10000/devstoreaccount1/agent-configs",
            conn_str="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=fake",
        )

    assert len(definitions) == 2
    slugs = {d.slug for d in definitions}
    assert slugs == {"math", "quote"}
    # Container name is derived from the last segment of the URL
    blob_service_mock.get_container_client.assert_called_once_with("agent-configs")


def test_load_from_blob_skips_sample_files() -> None:
    """Blobs named *_agent.sample.toml are not loaded."""
    container_mock = _build_container_client_mock(
        {
            "math_agent.toml": _MATH_TOML,
            "example_agent.sample.toml": _QUOTE_TOML,
        }
    )

    with (
        patch("azure.storage.blob.ContainerClient.from_container_url", return_value=container_mock),
        patch("azure.identity.DefaultAzureCredential"),
    ):
        definitions = load_agent_definitions_from_blob("https://fake.blob.core.windows.net/configs")

    assert len(definitions) == 1
    assert definitions[0].slug == "math"


def test_load_from_blob_empty_container_raises() -> None:
    """FileNotFoundError is raised when the container has no matching blobs."""
    container_mock = _build_container_client_mock({})

    with (
        patch("azure.storage.blob.ContainerClient.from_container_url", return_value=container_mock),
        patch("azure.identity.DefaultAzureCredential"),
        pytest.raises(FileNotFoundError, match="No agent config files"),
    ):
        load_agent_definitions_from_blob("https://fake.blob.core.windows.net/empty-container")


def test_load_from_blob_duplicate_slugs_raises() -> None:
    """Duplicate slug detection works across blobs loaded remotely."""
    duplicate_toml = textwrap.dedent("""\
        [a2a]
        name = "Math Agent 2"
        description = "Another math agent"
        version = "1.0.0"
        health_message = "OK"
        slug = "math"

        [foundry]
        agent_name = "different-foundry-agent"

        [[skills]]
        id = "math2"
        name = "Math2"
        description = "Also math"
    """).encode()

    container_mock = _build_container_client_mock(
        {
            "math_agent.toml": _MATH_TOML,
            "math2_agent.toml": duplicate_toml,
        }
    )

    with (
        patch("azure.storage.blob.ContainerClient.from_container_url", return_value=container_mock),
        patch("azure.identity.DefaultAzureCredential"),
        pytest.raises(ValueError, match="Duplicate agent slug"),
    ):
        load_agent_definitions_from_blob("https://fake.blob.core.windows.net/configs")
