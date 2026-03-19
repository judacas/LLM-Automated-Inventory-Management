"""Unit tests for src/a2a_servers/group_definition.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from a2a_servers.group_definition import (
    GroupDefinition,
    _derive_group_slug,
    load_group_definition,
    load_group_definitions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_TOML = textwrap.dedent("""\
    [a2a]
    name = "Inventory Group"
    description = "Routes to quote or math agents"
    version = "1.0.0"
    health_message = "OK"
    default_input_modes = ["text"]
    default_output_modes = ["text"]

    [group]
    agents = ["quote", "math"]

    [[skills]]
    id = "route_to_agent"
    name = "Route to Agent"
    description = "Routes requests to sub-agents"
    tags = ["routing"]
    examples = ["[target:quote] Check stock"]

    [smoke_tests]
    prompts = ["[target:quote] What is in stock?"]
""")


def _write_toml(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _derive_group_slug
# ---------------------------------------------------------------------------


def test_derive_group_slug_strips_group_suffix() -> None:
    assert _derive_group_slug(Path("inventory_group.toml")) == "inventory"


def test_derive_group_slug_strips_dash_group_suffix() -> None:
    assert _derive_group_slug(Path("inventory-group.toml")) == "inventory"


def test_derive_group_slug_no_suffix() -> None:
    assert _derive_group_slug(Path("mygroup.toml")) == "mygroup"


def test_derive_group_slug_case_insensitive() -> None:
    assert _derive_group_slug(Path("INVENTORY_GROUP.toml")) == "inventory"


# ---------------------------------------------------------------------------
# load_group_definition – happy path
# ---------------------------------------------------------------------------


def test_load_valid_group_definition(tmp_path: Path) -> None:
    p = _write_toml(tmp_path, "inventory_group.toml", _VALID_TOML)
    defn = load_group_definition(p)

    assert isinstance(defn, GroupDefinition)
    assert defn.slug == "inventory"  # derived from filename
    assert defn.public_name == "Inventory Group"
    assert defn.member_slugs == frozenset({"quote", "math"})
    assert defn.version == "1.0.0"
    assert len(defn.skills) == 1
    assert defn.skills[0].id == "route_to_agent"
    assert defn.smoke_test_prompts == ("[target:quote] What is in stock?",)


def test_load_explicit_slug_overrides_filename(tmp_path: Path) -> None:
    content = _VALID_TOML.replace("[a2a]", '[a2a]\nslug = "custom-group"', 1)
    p = _write_toml(tmp_path, "inventory_group.toml", content)
    defn = load_group_definition(p)
    assert defn.slug == "custom-group"


def test_member_slugs_are_normalised(tmp_path: Path) -> None:
    content = _VALID_TOML.replace(
        'agents = ["quote", "math"]', 'agents = ["Quote Agent", "Math"]'
    )
    p = _write_toml(tmp_path, "inventory_group.toml", content)
    defn = load_group_definition(p)
    assert defn.member_slugs == frozenset({"quote-agent", "math"})


# ---------------------------------------------------------------------------
# load_group_definition – missing required sections
# ---------------------------------------------------------------------------


def test_missing_a2a_section_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        [group]
        agents = ["quote"]

        [[skills]]
        id = "s"
        name = "S"
        description = "d"
    """)
    p = _write_toml(tmp_path, "x_group.toml", content)
    with pytest.raises(ValueError, match=r"\[a2a\]"):
        load_group_definition(p)


def test_missing_group_section_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        [a2a]
        name = "G"
        description = "d"
        version = "1"
        health_message = "ok"

        [[skills]]
        id = "s"
        name = "S"
        description = "d"
    """)
    p = _write_toml(tmp_path, "x_group.toml", content)
    with pytest.raises(ValueError, match=r"\[group\]"):
        load_group_definition(p)


def test_empty_agents_list_raises(tmp_path: Path) -> None:
    content = _VALID_TOML.replace('agents = ["quote", "math"]', "agents = []")
    p = _write_toml(tmp_path, "x_group.toml", content)
    with pytest.raises(ValueError, match="non-empty list"):
        load_group_definition(p)


def test_missing_skills_raises(tmp_path: Path) -> None:
    # Remove the [[skills]] block
    lines = [
        line
        for line in _VALID_TOML.splitlines()
        if not line.startswith("[[skills]]")
        and not line.startswith("id =")
        and not line.startswith("name =")
        and not line.startswith("description =")
        and not line.startswith("tags =")
        and not line.startswith("examples =")
    ]
    p = _write_toml(tmp_path, "x_group.toml", "\n".join(lines))
    with pytest.raises(ValueError, match=r"\[\[skills\]\]"):
        load_group_definition(p)


def test_file_not_found_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_group_definition(tmp_path / "nonexistent_group.toml")


# ---------------------------------------------------------------------------
# load_group_definitions – duplicate slug detection
# ---------------------------------------------------------------------------


def test_duplicate_group_slugs_raises(tmp_path: Path) -> None:
    for name in ("alpha_group.toml", "beta_group.toml"):
        content = textwrap.dedent("""\
            [a2a]
            name = "G"
            description = "d"
            version = "1"
            health_message = "ok"
            slug = "shared"

            [group]
            agents = ["quote"]

            [[skills]]
            id = "s"
            name = "S"
            description = "d"
        """)
        _write_toml(tmp_path, name, content)

    with pytest.raises(ValueError, match="Duplicate group slug"):
        load_group_definitions(str(tmp_path))


def test_no_group_files_returns_empty_tuple(tmp_path: Path) -> None:
    # No *_group.toml files → empty tuple, no error
    result = load_group_definitions(str(tmp_path))
    assert result == ()
