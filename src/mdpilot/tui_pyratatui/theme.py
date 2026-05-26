"""
Theme system for MDPilot TUI.

Provides a blue color palette with TrueColor support for PyRatatui.
"""
from typing import Tuple, Dict, Any


class Theme:
    """
    Blue theme for MDPilot TUI.
    
    Uses TrueColor (24-bit RGB) for rich visual experience.
    Color palette inspired by ocean/sky themes.
    """
    
    def __init__(self):
        """Initialize theme with blue color palette."""
        # Primary colors (blue tones)
        self.primary: Tuple[int, int, int] = (70, 130, 220)      # Dodger blue
        self.secondary: Tuple[int, int, int] = (100, 149, 237)   # Cornflower blue
        self.accent: Tuple[int, int, int] = (135, 206, 250)      # Light sky blue
        
        # Background colors
        self.background: Tuple[int, int, int] = (15, 23, 42)     # Dark blue-gray
        self.surface: Tuple[int, int, int] = (30, 41, 59)        # Slate
        
        # Text colors
        self.text: Tuple[int, int, int] = (226, 232, 240)        # Light gray
        self.text_dim: Tuple[int, int, int] = (148, 163, 184)    # Muted gray
        self.text_bright: Tuple[int, int, int] = (248, 250, 252) # Almost white
        
        # Semantic colors
        self.success: Tuple[int, int, int] = (34, 197, 94)       # Green
        self.warning: Tuple[int, int, int] = (251, 191, 36)      # Amber
        self.error: Tuple[int, int, int] = (239, 68, 68)         # Red
        self.info: Tuple[int, int, int] = (59, 130, 246)         # Blue
        
        # Border colors
        self.border: Tuple[int, int, int] = (71, 85, 105)        # Slate border
        self.border_focus: Tuple[int, int, int] = (96, 165, 250) # Blue border
    
    def get_style(self, name: str) -> Dict[str, Any]:
        """
        Get style configuration by name.
        
        Args:
            name: Style name (e.g., 'primary', 'error', 'text')
        
        Returns:
            Style configuration dict with fg/bg colors
        """
        styles = {
            'primary': {'fg': self.primary, 'bg': None},
            'secondary': {'fg': self.secondary, 'bg': None},
            'accent': {'fg': self.accent, 'bg': None},
            'text': {'fg': self.text, 'bg': None},
            'text_dim': {'fg': self.text_dim, 'bg': None},
            'text_bright': {'fg': self.text_bright, 'bg': None},
            'success': {'fg': self.success, 'bg': None},
            'warning': {'fg': self.warning, 'bg': None},
            'error': {'fg': self.error, 'bg': None},
            'info': {'fg': self.info, 'bg': None},
            'background': {'fg': None, 'bg': self.background},
            'surface': {'fg': None, 'bg': self.surface},
            'border': {'fg': self.border, 'bg': None},
            'border_focus': {'fg': self.border_focus, 'bg': None},
        }
        
        return styles.get(name, {'fg': self.text, 'bg': None})
    
    def rgb_to_hex(self, rgb: Tuple[int, int, int]) -> str:
        """
        Convert RGB tuple to hex string.
        
        Args:
            rgb: RGB color tuple (r, g, b)
        
        Returns:
            Hex color string (e.g., '#4682DC')
        """
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
