"""Tests for pytest configuration."""

import subprocess


def test_pytest_markers_configured():
    """测试 pytest 标记已配置"""
    result = subprocess.run(
        ["pytest", "--markers"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "integration" in result.stdout
    assert "slow" in result.stdout
