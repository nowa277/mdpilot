"""File access policy enforcing per-node read/write/execute rules."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from mdpilot.agent.node_config import NODES

_FORBIDDEN_READ_PATTERNS = [
    "*.env",
    "*/.ssh/*",
    "*.key",
    "*.pem",
    "*.token",
    "/etc/shadow",
    "/etc/passwd",
]


class FileAccessPolicy:
    """Enforce read/write/execute access rules for a specific compute node."""

    def __init__(self, node_id: str) -> None:
        # Raises KeyError for unknown nodes -- intentional.
        self._node = NODES[node_id]
        self._writable = Path(self._node.writable_dir).resolve()

    def can_read(self, path: str) -> bool:
        """Allow all reads except sensitive file patterns."""
        return not self._is_sensitive(path)

    def can_write(self, path: str) -> bool:
        """Allow writes only inside the node changshengjie directory."""
        return self._is_inside_writable(path)

    def can_execute(self, path: str) -> bool:
        """Allow execution only inside the node changshengjie directory."""
        return self._is_inside_writable(path)

    def _is_sensitive(self, path: str) -> bool:
        for pattern in _FORBIDDEN_READ_PATTERNS:
            if fnmatch.fnmatch(path, pattern):
             return True
        return False

    def _is_inside_writable(self, path: str) -> bool:
        try:
            resolved = Path(path).resolve()
            resolved.relative_to(self._writable)
            return True
        except ValueError:
            return False
