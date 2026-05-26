"""SSH execution tools for remote compute nodes."""

from __future__ import annotations

import logging
from typing import Optional

from mdpilot.tools.decorator import tool

logger = logging.getLogger(__name__)

_executor_instance = None


def _get_executor():
    global _executor_instance
    if _executor_instance is None:
        from mdpilot.agent.ssh_executor import SSHExecutor
        _executor_instance = SSHExecutor()
    return _executor_instance


@tool(
    name="ssh_exec",
    description=(
        "Execute a command on a remote compute node (lab02 or lab06). "
        "Working directory defaults to the node's changshengjie directory. "
        "Available nodes: lab02 (9x TITAN V), lab06 (9x RTX 3090)."
    ),
    category="system",
)
async def ssh_exec(
    node: str,
    command: str,
    workdir: Optional[str] = None,
    timeout: int = 600,
) -> str:
    """Execute a command on a remote node via SSH."""
    executor = _get_executor()
    try:
        result = await executor.execute(
            node_id=node,
            command=command,
            workdir=workdir,
            timeout=float(timeout),
        )
    except KeyError:
        return f"Error: Unknown node '{node}'. Available: lab02, lab03, lab06"
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error executing on {node}: {e}"

    if result.exit_code == 0:
        return result.stdout
    else:
        output = result.stdout + result.stderr
        return f"Error (exit code {result.exit_code}):\n{output}"
