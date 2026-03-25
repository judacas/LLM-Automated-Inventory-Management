from __future__ import annotations

from pathlib import Path

from a2a.types import AgentSkill
from agent_definition import AgentDefinition
from app_factory import _build_composite_description, _build_composite_skills
from composite_definition import CompositeAgentDefinition, CompositeMemberDefinition


def _make_agent_definition(name: str, slug: str, skill_id: str) -> AgentDefinition:
    return AgentDefinition(
        slug=slug,
        source_path=Path(f"{slug}_agent.toml"),
        public_name=name,
        description=f"{name} description",
        version="1.0.0",
        health_message="ok",
        foundry_agent_name=f"{slug}-foundry",
        default_input_modes=("text",),
        default_output_modes=("text",),
        skills=(
            AgentSkill(
                id=skill_id,
                name=f"{name} Skill",
                description=f"{name} skill description",
                tags=["test"],
                examples=["example"],
            ),
        ),
        smoke_test_prompts=(),
        supports_streaming=False,
    )


def test_composite_description_includes_route_hints_and_internal_agents() -> None:
    quote = _make_agent_definition("AI Foundry Quote Agent", "quote", "quote-skill")
    purchase = _make_agent_definition(
        "AI Foundry Purchase Order Agent", "purchase", "purchase-skill"
    )

    definition = CompositeAgentDefinition(
        slug="combined",
        source_path=Path("combined_composite.toml"),
        public_name="Combined Agent",
        description="Original composite description.",
        version="1.0.0",
        health_message="ok",
        default_input_modes=("text",),
        default_output_modes=("text",),
        supports_streaming=False,
        members=(
            CompositeMemberDefinition(
                agent_definition=quote,
                route_label="Quote Agent",
                keyword_patterns=(),
            ),
            CompositeMemberDefinition(
                agent_definition=purchase,
                route_label="Purchase Order Agent",
                keyword_patterns=(),
            ),
        ),
    )

    description = _build_composite_description(definition)

    assert "Original composite description." in description
    assert "composite endpoint" in description
    assert "Route to Quote Agent" in description
    assert "Route to Purchase Order Agent" in description
    assert "AI Foundry Quote Agent" in description
    assert "AI Foundry Purchase Order Agent" in description


def test_composite_skills_include_internal_agent_owner() -> None:
    email = _make_agent_definition("AI Foundry Email Agent", "email", "email-skill")

    definition = CompositeAgentDefinition(
        slug="combined",
        source_path=Path("combined_composite.toml"),
        public_name="Combined Agent",
        description="Original composite description.",
        version="1.0.0",
        health_message="ok",
        default_input_modes=("text",),
        default_output_modes=("text",),
        supports_streaming=False,
        members=(
            CompositeMemberDefinition(
                agent_definition=email,
                route_label="Email Agent",
                keyword_patterns=(),
            ),
        ),
    )

    skills = _build_composite_skills(definition)

    assert len(skills) == 1
    assert skills[0].id == "email-skill"
    assert "Executed by: AI Foundry Email Agent" in skills[0].description
