"""Tests for MemoryProfiler wrapper"""
import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for profiling output"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_memory_profiler_import():
    """Test MemoryProfiler can be imported"""
    from profiling.memory_profiler_wrapper import MemoryProfiler
    assert MemoryProfiler is not None


def test_memory_profiler_initialization(temp_output_dir):
    """Test MemoryProfiler initialization"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler(output_dir=temp_output_dir)
    assert profiler.output_dir == temp_output_dir
    assert temp_output_dir.exists()


def test_memory_profiler_default_output_dir():
    """Test MemoryProfiler creates default output directory"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler()
    assert profiler.output_dir == Path("profiling/results")


def test_profile_function_basic(temp_output_dir):
    """Test profiling a simple function"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler(output_dir=temp_output_dir)

    def sample_function(n):
        """Sample function that allocates memory"""
        data = [i for i in range(n)]
        return sum(data)

    result, report = profiler.profile_function(sample_function, 1000)

    # Check result is correct
    assert result == sum(range(1000))

    # Check report is generated
    assert isinstance(report, str)
    assert len(report) > 0
    assert 'Line #' in report or 'Mem usage' in report


def test_profile_function_with_kwargs(temp_output_dir):
    """Test profiling function with keyword arguments"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler(output_dir=temp_output_dir)

    def func_with_kwargs(a, b=10):
        return a + b

    result, report = profiler.profile_function(func_with_kwargs, 5, b=20)

    assert result == 25
    assert isinstance(report, str)


def test_save_report(temp_output_dir):
    """Test saving memory profile report to file"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler(output_dir=temp_output_dir)

    def sample_function():
        data = [i ** 2 for i in range(100)]
        return len(data)

    result, report = profiler.profile_function(sample_function)

    output_path = profiler.save_report(report)

    assert output_path.exists()
    assert output_path.name == "memory_profile.txt"
    assert output_path.parent == temp_output_dir

    # Check file contains the report
    content = output_path.read_text()
    assert content == report
    assert len(content) > 0


def test_save_report_custom_filename(temp_output_dir):
    """Test saving report with custom filename"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler(output_dir=temp_output_dir)

    report = "Sample memory report"
    output_path = profiler.save_report(report, filename="custom_memory.txt")

    assert output_path.exists()
    assert output_path.name == "custom_memory.txt"
    assert output_path.read_text() == report


def test_parse_report_valid(temp_output_dir):
    """Test parsing a valid memory profile report"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler(output_dir=temp_output_dir)

    # Sample report format from memory_profiler
    sample_report = """Filename: test.py

Line #    Mem usage    Increment  Occurrences   Line Contents
=============================================================
     1     50.5 MiB     50.5 MiB           1   def sample_function():
     2     52.3 MiB      1.8 MiB           1       data = [i for i in range(1000)]
     3     52.3 MiB      0.0 MiB           1       return sum(data)
"""

    parsed = profiler.parse_report(sample_report)

    assert 'lines' in parsed
    assert 'peak_memory_mb' in parsed

    assert len(parsed['lines']) == 3
    assert parsed['peak_memory_mb'] == 52.3

    # Check first line
    line1 = parsed['lines'][0]
    assert line1['line_number'] == 1
    assert line1['memory_mb'] == 50.5
    assert line1['increment_mb'] == 50.5


def test_parse_report_empty():
    """Test parsing empty report"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler()

    parsed = profiler.parse_report("")

    assert parsed == {'lines': [], 'peak_memory_mb': 0}


def test_parse_report_no_table():
    """Test parsing report without table"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler()

    report = "Some text without a table"
    parsed = profiler.parse_report(report)

    assert parsed == {'lines': [], 'peak_memory_mb': 0}


def test_parse_report_malformed_lines():
    """Test parsing report with some malformed lines"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler()

    sample_report = """Line #    Mem usage    Increment   Line Contents
=============================================================
     1     50.5 MiB      0.5 MiB   def func():
     invalid line here
     2     51.0 MiB      0.5 MiB       return 1
"""

    parsed = profiler.parse_report(sample_report)

    # Should parse valid lines and skip invalid ones
    assert len(parsed['lines']) == 2
    assert parsed['lines'][0]['line_number'] == 1
    assert parsed['lines'][1]['line_number'] == 2


def test_full_workflow(temp_output_dir):
    """Test complete workflow: profile, save, parse"""
    from profiling.memory_profiler_wrapper import MemoryProfiler

    profiler = MemoryProfiler(output_dir=temp_output_dir)

    def memory_intensive_function(size):
        """Function that allocates memory"""
        data = [0] * size
        for i in range(len(data)):
            data[i] = i ** 2
        return sum(data)

    # Profile the function
    result, report = profiler.profile_function(memory_intensive_function, 10000)

    # Verify result
    expected = sum(i ** 2 for i in range(10000))
    assert result == expected

    # Save report
    output_path = profiler.save_report(report, filename="workflow_test.txt")
    assert output_path.exists()

    # Parse report
    parsed = profiler.parse_report(report)
    assert 'lines' in parsed
    assert 'peak_memory_mb' in parsed

    # Should have captured some memory usage
    if len(parsed['lines']) > 0:
        assert parsed['peak_memory_mb'] > 0
