import subprocess

def test_pytest_benchmark_installed():
    """测试 pytest-benchmark 已安装"""
    result = subprocess.run(
        ["pytest", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--benchmark" in result.stdout, "pytest-benchmark not installed"
