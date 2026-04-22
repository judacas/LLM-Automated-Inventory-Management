"""Helpers for inspecting and normalising Azure AI Foundry tool schemas.

These functions are intentionally side-effect free so they can be unit-tested
without live Foundry credentials.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, MutableMapping
from typing import Any

from azure.ai.projects.models import A2APreviewTool

ToolMapping = MutableMapping[str, Any]


def _slugify(value: str, fallback: str) -> str:
    """Return a lowercased, hyphenated label suitable for tool names."""
    value = value.strip().lower()
    if not value:
        value = fallback
    slug = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return slug or fallback


def ensure_unique_tool_names(
    tools: Iterable[ToolMapping],
    *,
    prefix: str,
) -> tuple[list[ToolMapping], dict[str, str]]:
    """Ensure each tool has a unique ``name`` (and ``server_label`` if present).

    Returns a tuple of the updated tools list and a mapping of original names
    to the normalised names that were applied. Tools without a starting name
    are keyed as ``"<empty>"`` in the mapping.
    """
    updated: list[ToolMapping] = []
    rename_map: dict[str, str] = {}
    seen: set[str] = set()

    for index, tool in enumerate(tools):
        current_name = _pick_existing_name(tool)
        base_name = current_name or f"{prefix}-{index + 1}"
        desired = _slugify(base_name, fallback=f"{prefix}-{index + 1}")

        candidate = desired
        counter = 2
        while candidate in seen:
            candidate = f"{desired}-{counter}"
            counter += 1

        needs_label_sync = tool.get("name") != candidate or (
            "server_label" in tool and tool.get("server_label") != candidate
        )
        if needs_label_sync:
            if current_name != candidate:
                key = current_name or "<empty>"
                unique_key = key if key not in rename_map else f"{key}-{index + 1}"
                rename_map[unique_key] = candidate
            tool["name"] = candidate
            if "server_label" in tool:
                tool["server_label"] = candidate

        seen.add(candidate)
        updated.append(tool)

    return updated, rename_map


def _pick_existing_name(tool: ToolMapping) -> str | None:
    for key in ("name", "server_label", "label"):
        value = tool.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("base_url", "project_connection_id", "connector_id", "type"):
        value = tool.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def summarize_tool(tool: ToolMapping, index: int) -> dict[str, Any]:
    """Return a minimal summary of a tool's schema for display/debugging."""
    name = tool.get("name") or tool.get("server_label") or ""
    return {
        "index": index,
        "type": tool.get("type"),
        "name": name,
        "base_url": tool.get("base_url"),
        "connection_id": tool.get("project_connection_id") or tool.get("connector_id"),
        "raw": dict(tool),
    }


def parse_a2a_tool_spec(spec: str, *, default_card_path: str) -> A2APreviewTool:
    """Parse ``name=...,base_url=...,connection_id=...`` into an A2A tool."""
    parts = [segment.strip() for segment in spec.split(",") if segment.strip()]
    data: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            raise ValueError(
                "Tool spec entries must be key=value pairs separated by commas"
            )
        key, value = part.split("=", 1)
        data[key.strip()] = value.strip()

    base_url = data.get("base_url")
    connection_id = data.get("connection_id") or data.get("project_connection_id")
    if not base_url:
        raise ValueError("Tool spec is missing required `base_url`")
    if not connection_id:
        raise ValueError("Tool spec is missing required `connection_id`")

    agent_card_path = data.get("agent_card_path", default_card_path)
    tool = A2APreviewTool(
        base_url=base_url,
        agent_card_path=agent_card_path,
        project_connection_id=connection_id,
    )

    name = data.get("name") or data.get("label") or base_url
    tool["name"] = _slugify(name, fallback="a2a-tool")
    return tool
