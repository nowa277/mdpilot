"""TUI configuration management"""
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class LayoutConfig(BaseModel):
    """Layout configuration for TUI"""
    show_header: bool = True
    show_footer: bool = True


class TUIConfig(BaseModel):
    """Configuration for MDPilot TUI"""

    api_endpoint: str = Field(
        default="http://localhost:8000",
        description="API endpoint for MDPilot backend"
    )
    theme: Literal["dark", "light"] = Field(
        default="dark",
        description="TUI theme (dark or light)"
    )
    layout: LayoutConfig = Field(
        default_factory=LayoutConfig,
        description="Layout preferences"
    )

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """Validate theme value"""
        if v not in ["dark", "light"]:
            raise ValueError(f"Invalid theme: {v}. Must be 'dark' or 'light'")
        return v

    @classmethod
    def from_file(cls, config_path: Path) -> "TUIConfig":
        """Load configuration from YAML file

        Args:
            config_path: Path to configuration file

        Returns:
            TUIConfig instance with loaded configuration

        Note:
            If file doesn't exist, returns default configuration
        """
        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)

            if config_data is None:
                return cls()

            return cls(**config_data)
        except Exception:
            # Return default config if loading fails
            return cls()
