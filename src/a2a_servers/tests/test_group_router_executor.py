"""Unit tests for src/a2a_servers/group_router_executor.py."""

from __future__ import annotations

from a2a.types import FilePart, FileWithUri, Part, TextPart

from a2a_servers.group_router_executor import GroupRouterExecutor

# ---------------------------------------------------------------------------
# _parse_target_slug
# ---------------------------------------------------------------------------


def test_parse_target_slug_basic() -> None:
    assert GroupRouterExecutor._parse_target_slug("[target:quote]") == "quote"


def test_parse_target_slug_in_sentence() -> None:
    assert (
        GroupRouterExecutor._parse_target_slug(
            "Please handle this. [target:purchase-order] Create a PO."
        )
        == "purchase-order"
    )


def test_parse_target_slug_at_end() -> None:
    assert (
        GroupRouterExecutor._parse_target_slug("Do something useful. [target:email]")
        == "email"
    )


def test_parse_target_slug_case_insensitive() -> None:
    assert GroupRouterExecutor._parse_target_slug("[Target:Quote]") == "quote"


def test_parse_target_slug_with_whitespace() -> None:
    assert GroupRouterExecutor._parse_target_slug("[target:  math  ]") == "math"


def test_parse_target_slug_returns_first_match() -> None:
    # Only the first marker is used
    assert (
        GroupRouterExecutor._parse_target_slug("[target:quote] [target:email]")
        == "quote"
    )


def test_parse_target_slug_missing_marker_returns_none() -> None:
    assert GroupRouterExecutor._parse_target_slug("No marker here.") is None


def test_parse_target_slug_empty_string_returns_none() -> None:
    assert GroupRouterExecutor._parse_target_slug("") is None


def test_parse_target_slug_partial_marker_returns_none() -> None:
    # Malformed marker with no slug body — must have at least one alphanumeric
    assert GroupRouterExecutor._parse_target_slug("[target:]") is None


# ---------------------------------------------------------------------------
# _parts_to_text (static helper)
# ---------------------------------------------------------------------------


def _text_part(text: str) -> Part:
    return Part(root=TextPart(text=text))


def _file_part(uri: str) -> Part:
    return Part(root=FilePart(file=FileWithUri(uri=uri)))


def test_parts_to_text_single_text_part() -> None:
    assert GroupRouterExecutor._parts_to_text([_text_part("hello")]) == "hello"


def test_parts_to_text_multiple_text_parts() -> None:
    result = GroupRouterExecutor._parts_to_text(
        [_text_part("hello"), _text_part("world")]
    )
    assert result == "hello world"


def test_parts_to_text_file_part_included() -> None:
    result = GroupRouterExecutor._parts_to_text(
        [_text_part("see"), _file_part("http://example.com/file.txt")]
    )
    assert "see" in result
    assert "http://example.com/file.txt" in result


def test_parts_to_text_empty_parts() -> None:
    assert GroupRouterExecutor._parts_to_text([]) == ""
