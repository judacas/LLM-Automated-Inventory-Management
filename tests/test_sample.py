"""Sample test to verify test infrastructure is working."""

from typing import Any


def test_sample() -> None:
    """Basic test to ensure pytest is configured correctly."""
    assert True


def test_sample_with_fixture(sample_data: dict[str, Any]) -> None:
    """Test using a fixture from conftest.py."""
    assert sample_data["test_key"] == "test_value"
