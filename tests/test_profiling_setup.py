"""Test performance profiling dependencies setup."""


def test_profiling_dependencies_installed():
    """测试性能分析依赖已安装"""
    try:
        import psutil
        import memory_profiler
        import matplotlib
        assert True
    except ImportError as e:
        assert False, f"Missing dependency: {e}"
