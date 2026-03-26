"""Unit tests for composite_definition.py and CompositeAgentExecutor routing."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest
from a2a.types import AgentCapabilities, AgentCard
from composite_definition import (
    CompositeAgentDefinition,
    CompositeMemberDefinition,
    _compile_keyword_patterns,
    discover_composite_agent_definition_paths,
    load_composite_agent_definition,
    load_composite_agent_definitions,
)
from foundry_agent_executor import StreamingConversationBackend

# ---------------------------------------------------------------------------
# Shared TOML helpers
# ---------------------------------------------------------------------------

_VALID_AGENT_TOML = textwrap.dedent("""\
    [a2a]
    name = "{name}"
    description = "desc"
    version = "1.0.0"
    health_message = "ok"

    [foundry]
    agent_name = "{foundry_name}"

    [[skills]]
    id = "skill-{slug}"
    name = "Skill {slug}"
    description = "Does something"
""")


def _write_agent(
    tmp_path: Path,
    slug: str,
    foundry_name: str | None = None,
    filename: str | None = None,
) -> Path:
    """Write a minimal agent TOML and return its path."""
    fname = filename or f"{slug}_agent.toml"
    content = _VALID_AGENT_TOML.format(
        name=f"{slug.title()} Agent",
        slug=slug,
        foundry_name=foundry_name or f"{slug}-foundry",
    )
    p = tmp_path / fname
    p.write_text(content, encoding="utf-8")
    return p


def _write_composite(
    tmp_path: Path,
    content: str,
    filename: str = "all_composite.toml",
) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _compile_keyword_patterns
# ---------------------------------------------------------------------------


def test_compile_keyword_patterns_basic() -> None:
    patterns = _compile_keyword_patterns(["\\bemail\\b", "send"], "test")
    assert len(patterns) == 2
    assert all(isinstance(p, re.Pattern) for p in patterns)


def test_compile_keyword_patterns_case_insensitive() -> None:
    (pattern,) = _compile_keyword_patterns(["hello"], "test")
    assert pattern.search("Hello World") is not None


def test_compile_keyword_patterns_invalid_regex_raises() -> None:
    with pytest.raises(ValueError, match="invalid regex"):
        _compile_keyword_patterns(["[unclosed"], "test")


def test_compile_keyword_patterns_empty_list() -> None:
    assert _compile_keyword_patterns([], "test") == ()


# ---------------------------------------------------------------------------
# load_composite_agent_definition – happy path
# ---------------------------------------------------------------------------


def test_load_valid_composite(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email", "email-foundry")
    _write_agent(tmp_path, "quote", "quote-foundry")

    content = textwrap.dedent("""\
        [composite]
        name = "Combined Agent"
        description = "Handles email and quotes"
        version = "1.0.0"
        health_message = "Running!"

        [[composite.members]]
        config = "email_agent.toml"
        keywords = ["\\\\bemail\\\\b", "send"]

        [[composite.members]]
        config = "quote_agent.toml"
        keywords = ["\\\\bquote\\\\b"]
    """)
    p = _write_composite(tmp_path, content)
    defn = load_composite_agent_definition(p)

    assert isinstance(defn, CompositeAgentDefinition)
    assert defn.slug == "all"  # derived from filename "all_composite.toml"
    assert defn.public_name == "Combined Agent"
    assert defn.version == "1.0.0"
    assert len(defn.members) == 2
    assert defn.members[0].agent_definition.slug == "email"
    assert defn.members[1].agent_definition.slug == "quote"
    assert defn.members[0].route_label == "Email Agent"
    assert defn.members[0].keyword_patterns[0].search("Route to Email Agent")


def test_composite_slug_derived_from_filename(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"

        [[composite.members]]
        config = "email_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content, "contoso_composite.toml")
    defn = load_composite_agent_definition(p)
    assert defn.slug == "contoso"


def test_composite_explicit_slug_overrides_filename(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"
        slug = "my-custom"

        [[composite.members]]
        config = "email_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content)
    defn = load_composite_agent_definition(p)
    assert defn.slug == "my-custom"


def test_composite_streaming_defaults_true(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"

        [[composite.members]]
        config = "email_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content)
    defn = load_composite_agent_definition(p)
    assert defn.supports_streaming is True


def test_composite_streaming_can_be_disabled(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"
        streaming = false

        [[composite.members]]
        config = "email_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content)
    defn = load_composite_agent_definition(p)
    assert defn.supports_streaming is False


def test_composite_skills_aggregated(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    _write_agent(tmp_path, "quote")
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"

        [[composite.members]]
        config = "email_agent.toml"
        keywords = []

        [[composite.members]]
        config = "quote_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content)
    defn = load_composite_agent_definition(p)
    skill_ids = {s.id for s in defn.skills}
    assert "skill-email" in skill_ids
    assert "skill-quote" in skill_ids


def test_composite_no_keywords_allowed(tmp_path: Path) -> None:
    """Members without keywords are valid and get name-derived route patterns."""
    _write_agent(tmp_path, "email")
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"

        [[composite.members]]
        config = "email_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content)
    defn = load_composite_agent_definition(p)
    assert defn.members[0].route_label == "Email Agent"
    assert defn.members[0].keyword_patterns
    assert any(
        pattern.search("Route to Email Agent")
        for pattern in defn.members[0].keyword_patterns
    )


# ---------------------------------------------------------------------------
# load_composite_agent_definition – error cases
# ---------------------------------------------------------------------------


def test_file_not_found_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_composite_agent_definition(tmp_path / "nonexistent_composite.toml")


def test_missing_composite_section_raises(tmp_path: Path) -> None:
    p = _write_composite(tmp_path, "[other]\nfoo = 1\n")
    with pytest.raises(ValueError, match=r"\[composite\]"):
        load_composite_agent_definition(p)


def test_missing_members_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"
    """)
    p = _write_composite(tmp_path, content)
    with pytest.raises(ValueError, match=r"\[\[composite\.members\]\]"):
        load_composite_agent_definition(p)


def test_missing_required_composite_key_raises(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    # Missing 'name'
    content = textwrap.dedent("""\
        [composite]
        description = "d"
        version = "1"
        health_message = "ok"

        [[composite.members]]
        config = "email_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content)
    with pytest.raises(ValueError):
        load_composite_agent_definition(p)


def test_member_missing_config_key_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"

        [[composite.members]]
        keywords = ["foo"]
    """)
    p = _write_composite(tmp_path, content)
    with pytest.raises(ValueError, match="config"):
        load_composite_agent_definition(p)


def test_member_config_not_found_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"

        [[composite.members]]
        config = "missing_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content)
    with pytest.raises(FileNotFoundError):
        load_composite_agent_definition(p)


def test_keywords_are_ignored_when_present(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"

        [[composite.members]]
        config = "email_agent.toml"
        keywords = ["[unclosed"]
    """)
    p = _write_composite(tmp_path, content)
    defn = load_composite_agent_definition(p)
    assert defn.members[0].keyword_patterns


def test_streaming_must_be_bool_raises(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    content = textwrap.dedent("""\
        [composite]
        name = "N"
        description = "d"
        version = "1"
        health_message = "ok"
        streaming = 1

        [[composite.members]]
        config = "email_agent.toml"
        keywords = []
    """)
    p = _write_composite(tmp_path, content)
    with pytest.raises(ValueError, match="streaming"):
        load_composite_agent_definition(p)


# ---------------------------------------------------------------------------
# discover_composite_agent_definition_paths
# ---------------------------------------------------------------------------


def test_discover_finds_composite_files(tmp_path: Path) -> None:
    (tmp_path / "foo_composite.toml").write_text("", encoding="utf-8")
    (tmp_path / "bar_composite.toml").write_text("", encoding="utf-8")
    (tmp_path / "baz_agent.toml").write_text("", encoding="utf-8")  # should be ignored
    paths = discover_composite_agent_definition_paths(str(tmp_path))
    filenames = {p.name for p in paths}
    assert "foo_composite.toml" in filenames
    assert "bar_composite.toml" in filenames
    assert "baz_agent.toml" not in filenames


def test_discover_returns_empty_when_none(tmp_path: Path) -> None:
    paths = discover_composite_agent_definition_paths(str(tmp_path))
    assert paths == ()


def test_discover_nonexistent_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_composite_agent_definition_paths(str(tmp_path / "missing"))


# ---------------------------------------------------------------------------
# load_composite_agent_definitions – duplicate detection
# ---------------------------------------------------------------------------


def _make_composite_content(slug: str, member_config: str) -> str:
    return textwrap.dedent(f"""\
        [composite]
        name = "Agent {slug}"
        description = "d"
        version = "1"
        health_message = "ok"
        slug = "{slug}"

        [[composite.members]]
        config = "{member_config}"
        keywords = []
    """)


def test_duplicate_composite_slugs_raises(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    _write_composite(
        tmp_path,
        _make_composite_content("shared-slug", "email_agent.toml"),
        "alpha_composite.toml",
    )
    _write_composite(
        tmp_path,
        _make_composite_content("shared-slug", "email_agent.toml"),
        "beta_composite.toml",
    )
    with pytest.raises(ValueError, match="Duplicate composite agent slug"):
        load_composite_agent_definitions(str(tmp_path))


def test_load_multiple_composite_definitions(tmp_path: Path) -> None:
    _write_agent(tmp_path, "email")
    _write_agent(tmp_path, "quote")

    _write_composite(
        tmp_path,
        _make_composite_content("alpha", "email_agent.toml"),
        "alpha_composite.toml",
    )
    _write_composite(
        tmp_path,
        _make_composite_content("beta", "quote_agent.toml"),
        "beta_composite.toml",
    )

    defs = load_composite_agent_definitions(str(tmp_path))
    assert len(defs) == 2
    slugs = {d.slug for d in defs}
    assert slugs == {"alpha", "beta"}


def test_load_returns_empty_when_no_composite_files(tmp_path: Path) -> None:
    # Only regular agent files present
    _write_agent(tmp_path, "email")
    defs = load_composite_agent_definitions(str(tmp_path))
    assert defs == ()


# ---------------------------------------------------------------------------
# Routing logic (via CompositeMemberDefinition)
# ---------------------------------------------------------------------------


def _make_member(keywords: list[str]) -> CompositeMemberDefinition:
    """Build a stub CompositeMemberDefinition with the given keyword patterns."""
    from a2a.types import AgentSkill
    from agent_definition import AgentDefinition

    stub_def = AgentDefinition(
        slug="stub",
        source_path=Path("stub_agent.toml"),
        public_name="Stub",
        description="stub",
        version="1.0",
        health_message="ok",
        foundry_agent_name="stub-foundry",
        default_input_modes=("text",),
        default_output_modes=("text",),
        skills=(
            AgentSkill(id="s", name="S", description="desc", tags=[], examples=[]),
        ),
        smoke_test_prompts=(),
    )
    patterns = tuple(re.compile(k, re.IGNORECASE) for k in keywords)
    return CompositeMemberDefinition(
        agent_definition=stub_def, keyword_patterns=patterns
    )


def _make_test_card() -> AgentCard:
    return AgentCard(
        name="test",
        description="test",
        url="http://localhost/test/",
        version="1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[],
    )


def test_routing_first_match_wins() -> None:
    """A message that matches exactly one member is routed to that member."""
    from unittest.mock import AsyncMock

    from composite_agent_executor import CompositeAgentExecutor, CompositeMemberBackend

    card = _make_test_card()

    async def dummy_factory() -> StreamingConversationBackend:
        return AsyncMock()

    members = [
        CompositeMemberBackend(
            backend_factory=dummy_factory,
            keyword_patterns=(re.compile(r"\bemail\b", re.IGNORECASE),),
            route_label="Email Agent",
        ),
        CompositeMemberBackend(
            backend_factory=dummy_factory,
            keyword_patterns=(re.compile(r"\bquote\b", re.IGNORECASE),),
            route_label="Quote Agent",
        ),
    ]
    executor = CompositeAgentExecutor(card=card, members=members)

    assert executor._route_message("Send an email to someone") == 0
    assert executor._route_message("Create a quote for the order") == 1


def test_routing_raises_when_no_member_matches() -> None:
    from unittest.mock import AsyncMock

    from composite_agent_executor import CompositeAgentExecutor, CompositeMemberBackend

    card = _make_test_card()

    async def dummy_factory() -> StreamingConversationBackend:
        return AsyncMock()

    members = [
        CompositeMemberBackend(
            backend_factory=dummy_factory,
            keyword_patterns=(re.compile(r"\bemail\b", re.IGNORECASE),),
            route_label="Email Agent",
        ),
        CompositeMemberBackend(
            backend_factory=dummy_factory,
            keyword_patterns=(re.compile(r"\bquote\b", re.IGNORECASE),),
            route_label="Quote Agent",
        ),
    ]
    executor = CompositeAgentExecutor(card=card, members=members)
    with pytest.raises(ValueError, match="target agent to be specified"):
        executor._route_message("hello there")


def test_routing_is_case_insensitive() -> None:
    from unittest.mock import AsyncMock

    from composite_agent_executor import CompositeAgentExecutor, CompositeMemberBackend

    card = _make_test_card()

    async def dummy_factory() -> StreamingConversationBackend:
        return AsyncMock()

    members = [
        CompositeMemberBackend(
            backend_factory=dummy_factory,
            keyword_patterns=(re.compile(r"\bemail\b", re.IGNORECASE),),
            route_label="Email Agent",
        ),
    ]
    executor = CompositeAgentExecutor(card=card, members=members)
    assert executor._route_message("EMAIL me the report") == 0
    assert executor._route_message("Please Email this") == 0


def test_routing_raises_when_multiple_members_match() -> None:
    from unittest.mock import AsyncMock

    from composite_agent_executor import CompositeAgentExecutor, CompositeMemberBackend

    card = _make_test_card()

    async def dummy_factory() -> StreamingConversationBackend:
        return AsyncMock()

    members = [
        CompositeMemberBackend(
            backend_factory=dummy_factory,
            keyword_patterns=(re.compile(r"route to", re.IGNORECASE),),
            route_label="Email Agent",
        ),
        CompositeMemberBackend(
            backend_factory=dummy_factory,
            keyword_patterns=(re.compile(r"route to", re.IGNORECASE),),
            route_label="Quote Agent",
        ),
    ]

    executor = CompositeAgentExecutor(card=card, members=members)
    with pytest.raises(ValueError, match="exactly one target agent"):
        executor._route_message("Route to Email Agent")


def test_composite_executor_requires_at_least_one_member() -> None:
    from composite_agent_executor import CompositeAgentExecutor

    card = _make_test_card()
    with pytest.raises(ValueError, match="at least one member"):
        CompositeAgentExecutor(card=card, members=[])
