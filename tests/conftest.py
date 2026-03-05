"""Tests configuration and fixtures."""

from typing import Any

import pytest


@pytest.fixture
def sample_data() -> dict[str, Any]:
    """Provide sample test data."""
    return {"test_key": "test_value"}
