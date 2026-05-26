"""Tests for theme system."""
import pytest
from mdpilot.tui_pyratatui.theme import Theme


def test_theme_initialization():
    """Test Theme class initializes with blue palette."""
    theme = Theme()
    
    # Check primary colors exist
    assert hasattr(theme, 'primary')
    assert hasattr(theme, 'secondary')
    assert hasattr(theme, 'background')
    assert hasattr(theme, 'text')
    
    # Check colors are RGB tuples
    assert isinstance(theme.primary, tuple)
    assert len(theme.primary) == 3
    assert all(0 <= c <= 255 for c in theme.primary)


def test_theme_blue_palette():
    """Test theme uses blue color palette."""
    theme = Theme()
    
    # Primary should be blue-ish (high blue component)
    r, g, b = theme.primary
    assert b > r and b > g, "Primary color should be predominantly blue"


def test_theme_style_methods():
    """Test theme provides style helper methods."""
    theme = Theme()
    
    # Check style methods exist
    assert hasattr(theme, 'get_style')
    assert callable(theme.get_style)


def test_theme_get_style():
    """Test get_style returns valid style configuration."""
    theme = Theme()
    
    # Get a style
    style = theme.get_style('primary')
    
    # Should return a dict or similar structure
    assert style is not None
