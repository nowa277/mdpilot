"""Tests for ProfileRunner (cProfile wrapper)"""
import pytest
import time
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for profiling output"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_profile_runner_import():
    """Test ProfileRunner can be imported"""
    from profiling.profile_runner import ProfileRunner
    assert ProfileRunner is not None


def test_profile_runner_initialization(temp_output_dir):
    """Test ProfileRunner initialization"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)
    assert runner.output_dir == temp_output_dir
    assert temp_output_dir.exists()
    assert runner.profiles == {}
    assert runner.stats == {}


def test_profile_runner_default_output_dir():
    """Test ProfileRunner creates default output directory"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner()
    assert runner.output_dir == Path("profiling/results")


def test_profile_context_manager(temp_output_dir):
    """Test profile context manager captures execution"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)

    def sample_function():
        """Sample function to profile"""
        total = 0
        for i in range(1000):
            total += i
        return total

    with runner.profile("test_profile"):
        result = sample_function()

    assert result == sum(range(1000))
    assert "test_profile" in runner.profiles
    assert "test_profile" in runner.stats


def test_save_stats(temp_output_dir):
    """Test saving profiling stats to file"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)

    with runner.profile("save_test"):
        time.sleep(0.01)  # Small delay to ensure measurable time

    output_path = runner.save_stats("save_test")

    assert output_path.exists()
    assert output_path.name == "save_test_profile.txt"
    assert output_path.parent == temp_output_dir

    # Check file contains profiling data
    content = output_path.read_text()
    assert len(content) > 0
    assert "function calls" in content.lower() or "ncalls" in content.lower()


def test_save_stats_custom_filename(temp_output_dir):
    """Test saving stats with custom filename"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)

    with runner.profile("custom_test"):
        pass

    output_path = runner.save_stats("custom_test", filename="custom_output.txt")

    assert output_path.exists()
    assert output_path.name == "custom_output.txt"


def test_save_stats_nonexistent_profile(temp_output_dir):
    """Test saving stats for non-existent profile raises error"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)

    with pytest.raises(ValueError, match="No stats found for 'nonexistent'"):
        runner.save_stats("nonexistent")


def test_get_top_functions(temp_output_dir):
    """Test getting top functions by cumulative time"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)

    def func_a():
        time.sleep(0.01)

    def func_b():
        func_a()
        time.sleep(0.01)

    with runner.profile("top_funcs_test"):
        func_b()

    top_funcs = runner.get_top_functions("top_funcs_test", n=5)

    assert isinstance(top_funcs, list)
    assert len(top_funcs) <= 5

    # Check structure of returned data
    if len(top_funcs) > 0:
        func_info = top_funcs[0]
        assert 'function' in func_info
        assert 'calls' in func_info
        assert 'total_time' in func_info
        assert 'cumulative_time' in func_info


def test_get_top_functions_custom_n(temp_output_dir):
    """Test getting custom number of top functions"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)

    with runner.profile("custom_n_test"):
        for i in range(10):
            _ = i ** 2

    top_funcs = runner.get_top_functions("custom_n_test", n=3)

    assert len(top_funcs) <= 3


def test_get_top_functions_nonexistent_profile(temp_output_dir):
    """Test getting top functions for non-existent profile raises error"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)

    with pytest.raises(ValueError, match="No stats found for 'nonexistent'"):
        runner.get_top_functions("nonexistent")


def test_multiple_profiles(temp_output_dir):
    """Test running multiple profiles in same runner"""
    from profiling.profile_runner import ProfileRunner

    runner = ProfileRunner(output_dir=temp_output_dir)

    with runner.profile("profile1"):
        time.sleep(0.01)

    with runner.profile("profile2"):
        time.sleep(0.01)

    assert "profile1" in runner.profiles
    assert "profile2" in runner.profiles
    assert len(runner.profiles) == 2

    # Both can save stats
    path1 = runner.save_stats("profile1")
    path2 = runner.save_stats("profile2")

    assert path1.exists()
    assert path2.exists()
    assert path1 != path2
