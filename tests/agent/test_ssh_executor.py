"""Tests for SSHExecutor with mocked asyncssh connections."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mdpilot.agent.ssh_executor import ExecutionResult, SSHExecutor


# --- get_node_config ---

def test_get_node_config_lab03():
    executor = SSHExecutor()
    cfg = executor.get_node_config("lab03")
    assert cfg["host"] == "lab03"
    assert cfg["user"] == "zhao"
    assert cfg["writable_dir"] == "/home/3-FF/changshengjie"


def test_get_node_config_lab02():
    executor = SSHExecutor()
    cfg = executor.get_node_config("lab02")
    assert cfg["host"] == "lab02"
    assert cfg["user"] == "zhao"
    assert cfg["writable_dir"] == "/home/2-BB/changshengjie"


def test_get_node_config_lab06():
    executor = SSHExecutor()
    cfg = executor.get_node_config("lab06")
    assert cfg["host"] == "lab06"
    assert cfg["user"] == "zhao"
    assert cfg["writable_dir"] == "/home/6-FF/changshengjie"


def test_get_node_config_unknown_raises():
    executor = SSHExecutor()
    with pytest.raises(KeyError):
        executor.get_node_config("lab99")


# --- execute returns ExecutionResult ---

@pytest.mark.asyncio
async def test_execute_returns_execution_result():
    mock_result = MagicMock()
    mock_result.stdout = "hello\n"
    mock_result.stderr = ""
    mock_result.exit_status = 0

    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=mock_result)

    executor = SSHExecutor()

    with patch("asyncssh.connect", new=AsyncMock(return_value=mock_conn)):
        result = await executor.execute(
            "lab03",
            "echo hello",
            workdir="/home/3-FF/changshengjie",
        )

    assert isinstance(result, ExecutionResult)
    assert result.stdout == "hello\n"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.node == "lab03"


# --- default workdir is changshengjie ---

@pytest.mark.asyncio
async def test_execute_default_workdir_is_changshengjie():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.exit_status = 0

    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=mock_result)

    executor = SSHExecutor()

    with patch("asyncssh.connect", new=AsyncMock(return_value=mock_conn)):
        await executor.execute("lab03", "pwd")

    called_cmd = mock_conn.run.call_args[0][0]
    assert called_cmd.startswith("cd /home/3-FF/changshengjie &&")


# --- workdir outside changshengjie raises PermissionError ---

@pytest.mark.asyncio
async def test_execute_workdir_outside_changshengjie_raises():
    executor = SSHExecutor()
    with pytest.raises(PermissionError):
        await executor.execute("lab03", "ls", workdir="/tmp")


@pytest.mark.asyncio
async def test_execute_path_traversal_raises():
    executor = SSHExecutor()
    with pytest.raises(PermissionError):
        await executor.execute(
            "lab03",
            "ls",
            workdir="/home/3-FF/changshengjie/../../etc",
        )


# --- connection pooling reuses existing connection ---

@pytest.mark.asyncio
async def test_connection_is_reused():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.exit_status = 0

    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=mock_result)

    executor = SSHExecutor()

    with patch("asyncssh.connect", new=AsyncMock(return_value=mock_conn)) as mock_connect:
        await executor.execute("lab03", "pwd")
        await executor.execute("lab03", "ls")
        assert mock_connect.call_count == 1


# --- close closes all pooled connections ---

@pytest.mark.asyncio
async def test_close_closes_all_connections():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.exit_status = 0

    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=mock_result)

    executor = SSHExecutor()

    with patch("asyncssh.connect", new=AsyncMock(return_value=mock_conn)):
        await executor.execute("lab03", "pwd")

    await executor.close()
    mock_conn.close.assert_called_once()
