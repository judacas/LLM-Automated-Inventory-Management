from __future__ import annotations

import pytest
from azure.ai.projects.models import A2APreviewTool
from foundry_tool_schema import (
    ensure_unique_tool_names,
    parse_a2a_tool_spec,
    summarize_tool,
)


def test_ensure_unique_tool_names_adds_missing_and_normalises() -> None:
    tools = [
        A2APreviewTool(base_url="https://one"),
        A2APreviewTool(base_url="https://two"),
    ]

    updated, rename_map = ensure_unique_tool_names(tools, prefix="agent")

    names = {tool.get("name") for tool in updated}
    assert names == {"https-one", "https-two"}
    assert rename_map["https://one"] == "https-one"
    assert rename_map["https://two"] == "https-two"


def test_ensure_unique_tool_names_updates_server_label() -> None:
    tools = [{"server_label": "remote protocol", "type": "mcp"}]

    updated, rename_map = ensure_unique_tool_names(tools, prefix="quote")

    assert updated[0]["name"] == "remote-protocol"
    assert updated[0]["server_label"] == "remote-protocol"
    assert rename_map == {"remote protocol": "remote-protocol"}


def test_ensure_unique_tool_names_no_changes_when_unique() -> None:
    tools = [
        {"name": "alpha", "type": "a2a_preview"},
        {"server_label": "beta", "type": "mcp"},
    ]

    updated, rename_map = ensure_unique_tool_names(tools, prefix="ignored")

    assert [tool.get("name") for tool in updated] == ["alpha", "beta"]
    assert rename_map == {}


def test_parse_a2a_tool_spec_validates_required_fields() -> None:
    with pytest.raises(ValueError):
        parse_a2a_tool_spec(
            "name=bad,connection_id=missing_base", default_card_path="/card"
        )

    with pytest.raises(ValueError):
        parse_a2a_tool_spec("base_url=https://x", default_card_path="/card")


def test_parse_a2a_tool_spec_populates_fields() -> None:
    tool = parse_a2a_tool_spec(
        "name=Quote,base_url=https://api.example.com/a2a,connection_id=abc123",
        default_card_path="/card",
    )

    assert tool["name"] == "quote"
    assert tool.base_url == "https://api.example.com/a2a"
    assert tool.agent_card_path == "/card"
    assert tool.project_connection_id == "abc123"


def test_summarize_tool_includes_raw_snapshot() -> None:
    tool = A2APreviewTool(base_url="https://example.com")
    tool["name"] = "example"

    summary = summarize_tool(tool, index=0)
    assert summary["name"] == "example"
    assert summary["raw"]["base_url"] == "https://example.com"
