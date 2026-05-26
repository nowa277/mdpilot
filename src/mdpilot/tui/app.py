"""MDPilot Terminal User Interface application"""
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from mdpilot.tui.config import TUIConfig


class MDPilotTUI(App):
    """MDPilot Terminal User Interface

    A Textual-based TUI for interacting with MDPilot molecular dynamics
    simulation agent.

    Attributes:
        config: TUI configuration
        title: Application title
    """

    TITLE = "MDPilot"
    CSS = """
    Screen {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        config_path: Optional[Path] = None,
        **kwargs
    ):
        """Initialize MDPilot TUI

        Args:
            config_path: Optional path to configuration file
            **kwargs: Additional arguments passed to App
        """
        super().__init__(**kwargs)
        self.title = self.TITLE

        # Load configuration
        if config_path:
            self.config = TUIConfig.from_file(config_path)
        else:
            self.config = TUIConfig()

    def compose(self) -> ComposeResult:
        """Compose the TUI layout

        Yields:
            Header and Footer widgets based on configuration
        """
        if self.config.layout.show_header:
            yield Header()

        # Future: Add main content widgets here

        if self.config.layout.show_footer:
            yield Footer()

    def action_quit(self) -> None:
        """Quit the application"""
        self.exit()
