"""
Layout management for MDPilot TUI.

Implements the 7-layer vertical layout system:
1. Title Bar (1 row)
2. Welcome Panel (8-12 rows, collapsible)
3. Messages Area (min 1 row, fills remaining space)
4. Status Row (dynamic 0-1 row)
5. Bottom Status (1 row)
6. Input Area (1-5 rows, dynamic expansion)
7. Footer (1 row)
"""
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class LayoutConstraints:
    """Layout constraints for responsive behavior."""

    # Terminal size thresholds
    min_width: int = 80
    min_height: int = 20

    # Fixed heights
    title_bar_height: int = 1
    status_row_height: int = 1
    bottom_status_height: int = 1
    footer_height: int = 1

    # Dynamic heights
    welcome_panel_min_height: int = 8
    welcome_panel_max_height: int = 12
    messages_area_min_height: int = 1
    input_area_min_height: int = 1
    input_area_max_height: int = 5


class LayoutManager:
    """
    Manages the 7-layer vertical layout.

    Handles:
    - Terminal size detection
    - Responsive layout adjustments
    - Component visibility toggling
    - Height calculations
    """

    def __init__(self, constraints: LayoutConstraints = None):
        """
        Initialize layout manager.

        Args:
            constraints: Layout constraints (uses defaults if None)
        """
        self.constraints = constraints or LayoutConstraints()
        self.terminal_width = 0
        self.terminal_height = 0
        self.welcome_panel_visible = True
        self.status_row_visible = False

    def update_terminal_size(self, width: int, height: int) -> None:
        """
        Update terminal size and adjust layout.

        Args:
            width: Terminal width in columns
            height: Terminal height in rows
        """
        self.terminal_width = width
        self.terminal_height = height

        # Auto-collapse welcome panel if terminal too small
        if width < self.constraints.min_width or height < self.constraints.min_height:
            self.welcome_panel_visible = False

    def calculate_layout(self) -> List[Tuple[str, int]]:
        """
        Calculate layout heights for all layers.

        Returns:
            List of (layer_name, height) tuples
        """
        layout = []
        remaining_height = self.terminal_height

        # 1. Title Bar (fixed)
        layout.append(("title_bar", self.constraints.title_bar_height))
        remaining_height -= self.constraints.title_bar_height

        # 2. Welcome Panel (dynamic)
        if self.welcome_panel_visible:
            welcome_height = min(
                self.constraints.welcome_panel_max_height,
                max(self.constraints.welcome_panel_min_height, remaining_height // 3)
            )
            layout.append(("welcome_panel", welcome_height))
            remaining_height -= welcome_height

        # 3. Status Row (dynamic)
        if self.status_row_visible:
            layout.append(("status_row", self.constraints.status_row_height))
            remaining_height -= self.constraints.status_row_height

        # 4. Bottom Status (fixed)
        layout.append(("bottom_status", self.constraints.bottom_status_height))
        remaining_height -= self.constraints.bottom_status_height

        # 5. Input Area (dynamic, reserve space)
        input_height = min(
            self.constraints.input_area_max_height,
            max(self.constraints.input_area_min_height, 3)
        )
        layout.append(("input_area", input_height))
        remaining_height -= input_height

        # 6. Footer (fixed)
        layout.append(("footer", self.constraints.footer_height))
        remaining_height -= self.constraints.footer_height

        # 7. Messages Area (fills remaining space)
        messages_height = max(self.constraints.messages_area_min_height, remaining_height)
        layout.append(("messages_area", messages_height))

        return layout

    def toggle_welcome_panel(self) -> None:
        """Toggle welcome panel visibility."""
        self.welcome_panel_visible = not self.welcome_panel_visible

    def show_status_row(self) -> None:
        """Show status row (for LLM streaming)."""
        self.status_row_visible = True

    def hide_status_row(self) -> None:
        """Hide status row (when idle)."""
        self.status_row_visible = False
