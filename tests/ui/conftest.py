"""Shared fixtures for UI tests."""

import pytest
from rich.console import Console
import io


@pytest.fixture
def test_console():
    """Create a console optimized for testing."""
    return Console(
        file=io.StringIO(),
        force_terminal=True,
        width=80,
        color_system="truecolor",
        legacy_windows=False,
        _environ={},
    )
