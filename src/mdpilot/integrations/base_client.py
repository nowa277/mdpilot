"""Base client interface for external model integrations."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict


class ClientMode(str, Enum):
    """Client operation mode."""

    LOCAL = "local"
    API = "api"


class ModelClient(ABC):
    """Abstract base class for external model clients."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the client with configuration.

        Args:
            config: Configuration dictionary containing mode and mode-specific settings
        """
        self.config = config
        self._validate_config()

        mode_str = config.get("mode", "").lower()
        if mode_str not in [m.value for m in ClientMode]:
            raise ValueError(f"Invalid mode: {mode_str}. Must be 'local' or 'api'")

        self.mode = ClientMode(mode_str)

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate the configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check if the client is healthy and can communicate with the model.

        Returns:
            Dictionary with status information
        """
        pass
