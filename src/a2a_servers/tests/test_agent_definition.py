"""Unit tests for src/a2a_servers/agent_definition.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from agent_definition import (
    AgentDefinition,
    _derive_agent_slug,
    _normalize_agent_slug,
    load_agent_definition,
    load_agent_definitions,
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
