"""Serialize agent configuration dicts back to TOML text.

This is intentionally simple and hand-rolled — the TOML structure for agent
configs is fixed and well-understood, so we do not need a full TOML library
just for writing.
"""

from __future__ import annotations


def _esc(s: str) -> str:
    """Escape backslashes and double-quotes for a TOML basic string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _toml_str(s: str) -> str:
    return f'"{_esc(s)}"'


def _toml_str_array(items: list[str]) -> str:
    return "[" + ", ".join(_toml_str(x) for x in items) + "]"


def agent_config_to_toml(config: dict[str, object]) -> str:
    """Convert an agent config dict to TOML text.

    The *config* dict must have the same shape returned by the dashboard API
    (and accepted by the PUT/POST endpoints):

    .. code-block:: json

        {
            "a2a": {
                "name": "...",
                "description": "...",
                "version": "...",
                "health_message": "...",
                "slug": "...",            // optional
                "default_input_modes": ["text"],
                "default_output_modes": ["text"],
                "streaming": true
            },
            "foundry": {"agent_name": "..."},
            "smoke_tests": {"prompts": ["..."]},   // optional
            "skills": [
                {
                    "id": "...", "name": "...", "description": "...",
                    "tags": ["..."], "examples": ["..."]
                }
            ]
        }

    Raises ``KeyError`` or ``TypeError`` if required keys are missing or have
    the wrong type.
    """
    a2a = config["a2a"]
    if not isinstance(a2a, dict):
        raise TypeError("'a2a' must be a dict")

    foundry = config["foundry"]
    if not isinstance(foundry, dict):
        raise TypeError("'foundry' must be a dict")

    skills_raw = config["skills"]
    if not isinstance(skills_raw, list):
        raise TypeError("'skills' must be a list")

    smoke_tests_raw = config.get("smoke_tests", {})
    if not isinstance(smoke_tests_raw, dict):
        raise TypeError("'smoke_tests' must be a dict if provided")

    lines: list[str] = []

    # --- [a2a] ---------------------------------------------------------------
    lines.append("[a2a]")
    lines.append(f"name = {_toml_str(str(a2a['name']))}")
    lines.append(f"description = {_toml_str(str(a2a['description']))}")
    lines.append(f"version = {_toml_str(str(a2a['version']))}")
    lines.append(f"health_message = {_toml_str(str(a2a['health_message']))}")

    slug = a2a.get("slug")
    if slug and str(slug).strip():
        lines.append(f"slug = {_toml_str(str(slug))}")

    input_modes = a2a.get("default_input_modes", ["text"])
    if not isinstance(input_modes, list):
        input_modes = ["text"]
    lines.append(
        f"default_input_modes = {_toml_str_array([str(m) for m in input_modes])}"
    )

    output_modes = a2a.get("default_output_modes", ["text"])
    if not isinstance(output_modes, list):
        output_modes = ["text"]
    lines.append(
        f"default_output_modes = {_toml_str_array([str(m) for m in output_modes])}"
    )

    streaming = a2a.get("streaming", True)
    lines.append(f"streaming = {'true' if streaming else 'false'}")
    lines.append("")

    # --- [foundry] -----------------------------------------------------------
    lines.append("[foundry]")
    lines.append(f"agent_name = {_toml_str(str(foundry['agent_name']))}")
    lines.append("")

    # --- [smoke_tests] -------------------------------------------------------
    prompts = smoke_tests_raw.get("prompts", [])
    if isinstance(prompts, list) and prompts:
        lines.append("[smoke_tests]")
        lines.append(f"prompts = {_toml_str_array([str(p) for p in prompts])}")
        lines.append("")

    # --- [[skills]] ----------------------------------------------------------
    for skill in skills_raw:
        if not isinstance(skill, dict):
            raise TypeError("Each entry in 'skills' must be a dict")
        lines.append("[[skills]]")
        lines.append(f"id = {_toml_str(str(skill['id']))}")
        lines.append(f"name = {_toml_str(str(skill['name']))}")
        lines.append(f"description = {_toml_str(str(skill['description']))}")

        tags = skill.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        lines.append(f"tags = {_toml_str_array([str(t) for t in tags])}")

        examples = skill.get("examples", [])
        if not isinstance(examples, list):
            examples = []
        lines.append(f"examples = {_toml_str_array([str(e) for e in examples])}")
        lines.append("")

    return "\n".join(lines)
