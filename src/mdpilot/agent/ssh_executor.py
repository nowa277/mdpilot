"""SSHExecutor: asyncssh-based remote command execution with connection pooling."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import asyncssh

from mdpilot.agent.file_policy import FileAccessPolicy
from mdpilot.agent.node_config import NODES

@dataclass
class ExecutionResult:
    """Result of a remote command execution."""

    stdout: str
    stderr: str
    exit_code: int
    node: str


class SSHExecutor:
    """Execute commands on remote compute nodes via SSH with connection pooling."""

    def __init__(self) -> None:
        self._connections: dict[str, asyncssh.SSHClientConnection] = {}

    def get_node_config(self, node_id: str) -> dict:
        """Return config dict for node_id. Raises KeyError for unknown nodes."""
        node = NODES[node_id]  # intentional KeyError on unknown node
        return {
         "host": node.host,
            "user": node.user,
            "writable_dir": node.writable_dir,
      }

    async def _get_connection(self, node_id: str) -> asyncssh.SSHClientConnection:
        """Return a cached connection, creating one if needed."""
        if node_id not in self._connections:
            cfg = self.get_node_config(node_id)
            self._connections[node_id] = await asyncssh.connect(
           cfg["host"],
                username=cfg["user"],
                known_hosts=None,
            )
        return self._connections[node_id]

    async def execute(
        self,
        node_id: str,
        command: str,
        workdir: Optional[str] = None,
        timeout: int = 600,
    ) -> ExecutionResult:
        """Run command on node_id inside workdir.

        workdir defaults to the node changshengjie directory.
        Raises PermissionError if workdir is outside changshengjie.
        """
        cfg = self.get_node_config(node_id)

        if workdir is None:
            workdir = cfg["writable_dir"]

        policy = FileAccessPolicy(node_id)
        if not policy.can_write(workdir):
            raise PermissionError(
          f"workdir {workdir!r} is outside the writable directory for {node_id}"
            )

        full_command = f"cd {workdir} && {command}"

        conn = await self._get_connection(node_id)
        result = await asyncio.wait_for(conn.run(full_command), timeout=timeout)

        return ExecutionResult(
            stdout=result.stdout,
         stderr=result.stderr,
         exit_code=result.exit_status,
         node=node_id,
        )

    async def close(self) -> None:
        """Close all pooled SSH connections."""
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()
