"""Integration tests for real SSH execution.

These tests require SSH access to lab02 and lab06.
Skip if SSH is not available.
"""
import subprocess
import pytest

from mdpilot.agent.ssh_executor import SSHExecutor


def ssh_available():
    """Check if SSH to lab02 is available."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "lab02", "echo ok"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not ssh_available(),
    reason="SSH to lab02 not available",
)


@pytest.mark.asyncio
async def test_execute_echo_on_lab02():
    """Execute a simple echo command on lab02."""
    executor = SSHExecutor()
    try:
        result = await executor.execute("lab02", "echo hello_from_lab02")
        assert result.exit_code == 0
        assert "hello_from_lab02" in result.stdout
        assert result.node == "lab02"
    finally:
        await executor.close()


@pytest.mark.asyncio
async def test_execute_pwd_shows_changshengjie():
    """Default workdir is changshengjie."""
    executor = SSHExecutor()
    try:
        result = await executor.execute("lab02", "pwd")
        assert result.exit_code == 0
        assert "changshengjie" in result.stdout
    finally:
        await executor.close()


@pytest.mark.asyncio
async def test_execute_on_lab06():
    """Execute on lab06."""
    executor = SSHExecutor()
    try:
        result = await executor.execute("lab06", "echo hello_from_lab06")
        assert result.exit_code == 0
        assert "hello_from_lab06" in result.stdout
        assert result.node == "lab06"
    finally:
        await executor.close()


@pytest.mark.asyncio
async def test_file_write_in_changshengjie():
    """Can create and read a file in changshengjie on lab02."""
    executor = SSHExecutor()
    try:
        result = await executor.execute(
            "lab02",
            "echo 'mdpilot_test_marker' > .mdpilot_test && cat .mdpilot_test && rm -f .mdpilot_test",
        )
        assert result.exit_code == 0
        assert "mdpilot_test_marker" in result.stdout
    finally:
        await executor.close()
