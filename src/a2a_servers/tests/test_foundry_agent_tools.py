from __future__ import annotations

from pathlib import Path

import pytest
from foundry_agent_tools import _build_discovered_a2a_tool, _select_agent_definitions
from settings import load_server_settings


def test_select_agent_definitions_loads_all_matching_configs(tmp_path: Path) -> None:
    _write_agent_config(tmp_path / "alpha_agent.toml", "Alpha Agent", "alpha-foundry")
    _write_agent_config(tmp_path / "beta_agent.toml", "Beta Agent", "beta-foundry")

    definitions = _select_agent_definitions(config_dir=str(tmp_path), agent_slugs=())

    assert [definition.slug for definition in definitions] == ["alpha", "beta"]


def test_select_agent_definitions_filters_by_slug(tmp_path: Path) -> None:
    _write_agent_config(tmp_path / "alpha_agent.toml", "Alpha Agent", "alpha-foundry")
    _write_agent_config(tmp_path / "beta_agent.toml", "Beta Agent", "beta-foundry")

    definitions = _select_agent_definitions(
        config_dir=str(tmp_path),
        agent_slugs=("beta",),
    )

    assert [definition.slug for definition in definitions] == ["beta"]


def test_select_agent_definitions_rejects_missing_slug(tmp_path: Path) -> None:
    _write_agent_config(tmp_path / "alpha_agent.toml", "Alpha Agent", "alpha-foundry")

    with pytest.raises(ValueError, match="missing"):
        _select_agent_definitions(config_dir=str(tmp_path), agent_slugs=("missing",))


def test_build_discovered_a2a_tool_uses_server_route_and_slug(tmp_path: Path) -> None:
    config_path = tmp_path / "quote_agent.toml"
    _write_agent_config(config_path, "Quote Agent", "quote-foundry")

    definition = _select_agent_definitions(
        config_dir=str(tmp_path),
        agent_slugs=("quote",),
    )[0]
    settings = load_server_settings(
        host="localhost",
        port=10007,
        url_mode="forwarded",
        forwarded_base_url="https://a2a.example.com",
        require_project_endpoint=False,
    )

    tool = _build_discovered_a2a_tool(
        definition=definition,
        settings=settings,
        connection_id="conn-123",
    )

    assert tool["name"] == "quote"
    assert tool.base_url == "https://a2a.example.com/quote"
    assert tool.project_connection_id == "conn-123"


def _write_agent_config(path: Path, public_name: str, foundry_agent_name: str) -> None:
    path.write_text(
        "\n".join(
            [
                "[a2a]",
                f'name = "{public_name}"',
                'description = "Example description"',
                'version = "1.0.0"',
                'health_message = "ok"',
                "",
                "[foundry]",
                f'agent_name = "{foundry_agent_name}"',
                "",
                "[[skills]]",
                'id = "test_skill"',
                'name = "Test Skill"',
                'description = "A test skill"',
                'tags = ["test"]',
                'examples = ["example"]',
            ]
        ),
        encoding="utf-8",
    )
