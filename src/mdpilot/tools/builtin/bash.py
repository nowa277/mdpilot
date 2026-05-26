"""Bash execution tool for mdpilot."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from mdpilot.tools.security import ValidationError, validate_shell_command
from mdpilot.tools.decorator import tool

logger = logging.getLogger(__name__)


def _validate_command(command: str) -> None:
    """Validate command for dangerous patterns.

    Args:
        command: The command to validate.

    Raises:
        ValueError: If command contains dangerous patterns.
    """
    try:
        validate_shell_command(command)
    except ValidationError as e:
        logger.warning(f"Blocked dangerous command: {e}")
        raise ValueError(str(e)) from e

    # Log all commands for audit trail
    logger.info(f"Executing command: {command[:200]}")


@tool(
    name="bash_run",
    description="Execute a bash command and return its stdout/stderr output. "
                "WARNING: Commands are executed with shell access. Dangerous patterns "
                "(rm -rf /, sudo, disk writes, curl|bash) are blocked.",
    category="system",
)
def bash_run(command: str, timeout: int = 60, workdir: str | None = None) -> str:
    """Run a bash command with timeout and optional working directory.

    Args:
        command: The bash command to execute.
        timeout: Maximum seconds to wait before killing the process.
        workdir: Optional working directory for the command.

    Returns:
        Combined stdout and stderr output from the command.

    Raises:
        ValueError: If command contains dangerous patterns.
        TimeoutError: If command exceeds timeout.
    """
    _validate_command(command)
    return asyncio.run(_bash_run_async(command, timeout, workdir))


async def _bash_run_async(
    command: str, timeout: int = 60, workdir: str | None = None
) -> str:
    """Async implementation of bash execution."""
    env = os.environ.copy()
    proc = await asyncio.create_subprocess_shell(
    command,
        stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.STDOUT,
        cwd=workdir,
      env=env,
    )

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0 and not output:
            output = f"[Process exited with code {proc.returncode}]"
        return output
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"Command timed out after {timeout}s: {command}")


@tool(
    name="ssh_bash",
    description="Execute bash command on a remote node via SSH. "
    "Use this to run commands on lab02 (AlphaFold2) or lab06 (BioReason). "
    "Supports reading files, listing directories, running scripts, etc. "
  "Example: ssh_bash(node='lab02', command='cat /home/2-BB/changshengjie/predictions/result.json')",
    category="system",
)
def ssh_bash(node: str, command: str, timeout: int = 600, workdir: str | None = None) -> str:
    """Execute bash command on remote node via SSH.

    Args:
        node: Target node ID (lab02, lab03, lab06)
        command: Bash command to execute
        timeout: Maximum seconds to wait (default 600)
        workdir: Optional working directory on remote node

    Returns:
        Command output (stdout + stderr)

    Raises:
        ValueError: If command contains dangerous patterns
        TimeoutError: If command exceeds timeout
    """
    _validate_command(command)
    return asyncio.run(_ssh_bash_async(node, command, timeout, workdir))


async def _ssh_bash_async(
    node: str, command: str, timeout: int, workdir: Optional[str]
) -> str:
    """Async implementation of SSH bash execution."""
    from mdpilot.agent.ssh_executor import SSHExecutor

    executor = SSHExecutor()
    try:
        result = await executor.execute(
            node_id=node, command=command, workdir=workdir, timeout=timeout
     )

        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        if result.exit_code != 0:
          output += f"\n[Exit code: {result.exit_code}]"

        return output
    finally:
        await executor.close()
