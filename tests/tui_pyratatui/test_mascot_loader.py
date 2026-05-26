"""Tests for mascot loader."""
import pytest
from mdpilot.tui_pyratatui.utils.mascot_loader import (
    load_mascot_pixels,
    get_mascot_dimensions,
)


def test_load_mascot_pixels():
    """Test loading mascot pixel data."""
    pixels = load_mascot_pixels()
    
    # Check dimensions
    assert len(pixels) == 32, "Should have 32 rows"
    assert all(len(row) == 32 for row in pixels), "Each row should have 32 pixels"


def test_mascot_dimensions():
    """Test get_mascot_dimensions returns correct size."""
    width, height = get_mascot_dimensions()
    
    assert width == 32
    assert height == 32


def test_mascot_has_content():
    """Test mascot has non-transparent pixels."""
    pixels = load_mascot_pixels()
    
    # Count non-transparent pixels
    non_transparent = sum(
        1 for row in pixels for pixel in row if pixel is not None
    )
    
    # Mascot should have significant content (at least 100 pixels)
    assert non_transparent > 100, f"Expected >100 pixels, got {non_transparent}"


def test_mascot_pixel_format():
    """Test pixels are RGB tuples."""
    pixels = load_mascot_pixels()
    
    # Find first non-transparent pixel
    for row in pixels:
        for pixel in row:
            if pixel is not None:
                # Check it's an RGB tuple
                assert isinstance(pixel, tuple)
                assert len(pixel) == 3
                assert all(isinstance(c, int) for c in pixel)
                assert all(0 <= c <= 255 for c in pixel)
                return  # Test passed
    
    pytest.fail("No non-transparent pixels found")


def test_mascot_blue_dominant():
    """Test mascot uses blue colors (matching theme)."""
    pixels = load_mascot_pixels()
    
    blue_pixels = 0
    total_pixels = 0
    
    for row in pixels:
        for pixel in row:
            if pixel is not None:
                total_pixels += 1
                r, g, b = pixel
                # Consider it "blue" if blue component is highest
                if b >= r and b >= g:
                    blue_pixels += 1
    
    # At least 30% should be blue-ish
    blue_ratio = blue_pixels / total_pixels if total_pixels > 0 else 0
    assert blue_ratio > 0.3, f"Expected >30% blue pixels, got {blue_ratio:.1%}"
