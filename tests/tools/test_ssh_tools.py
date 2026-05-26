"""Tests for SSH tools."""
import pytest
from unittest.mock import AsyncMock, patch
from mdpilot.tools.builtin.ssh_tools import ssh_exec
from mdpilot.agent.ssh_executor import ExecutionResult


@pytest.mark.asyncio
async def test_ssh_exec_returns_stdout():
    mock_result = ExecutionResult(stdout="hello\n", stderr="", exit_code=0, node="lab02")
    with patch("mdpilot.tools.builtin.ssh_tools._get_executor") as mock_get:
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_executor
        result = await ssh_exec(node="lab02", command="echo hello")
        assert "hello" in result


@pytest.mark.asyncio
async def test_ssh_exec_includes_stderr_on_failure():
    mock_result = ExecutionResult(stdout="", stderr="not found", exit_code=1, node="lab02")
    with patch("mdpilot.tools.builtin.ssh_tools._get_executor") as mock_get:
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_executor
        result = await ssh_exec(node="lab02", command="bad_cmd")
        assert "not found" in result


@pytest.mark.asyncio
async def test_ssh_exec_rejects_invalid_node():
    result = await ssh_exec(node="lab99", command="echo hi")
    assert "Error" in result or "Unknown" in result
