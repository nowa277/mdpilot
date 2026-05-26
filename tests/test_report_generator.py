"""Tests for ReportGenerator (matplotlib visualization)"""
import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for report output"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_resource_data():
    """Sample resource monitoring data"""
    return [
        {'timestamp': 1000.0, 'cpu_percent': 10.5, 'memory_mb': 100.0, 'memory_percent': 5.0},
        {'timestamp': 1000.1, 'cpu_percent': 15.2, 'memory_mb': 105.0, 'memory_percent': 5.2},
        {'timestamp': 1000.2, 'cpu_percent': 20.8, 'memory_mb': 110.0, 'memory_percent': 5.5},
        {'timestamp': 1000.3, 'cpu_percent': 18.5, 'memory_mb': 108.0, 'memory_percent': 5.4},
        {'timestamp': 1000.4, 'cpu_percent': 12.3, 'memory_mb': 102.0, 'memory_percent': 5.1},
    ]


@pytest.fixture
def sample_function_data():
    """Sample function profiling data"""
    return [
        {
            'function': ('file1.py', 10, 'function_a'),
            'calls': 100,
            'total_time': 0.5,
            'cumulative_time': 1.5,
        },
        {
            'function': ('file2.py', 20, 'function_b'),
            'calls': 50,
            'total_time': 0.3,
            'cumulative_time': 0.8,
        },
        {
            'function': ('file3.py', 30, 'function_c'),
            'calls': 200,
            'total_time': 0.2,
            'cumulative_time': 0.6,
        },
    ]


def test_report_generator_import():
    """Test ReportGenerator can be imported"""
    from profiling.report_generator import ReportGenerator
    assert ReportGenerator is not None


def test_report_generator_initialization(temp_output_dir):
    """Test ReportGenerator initialization"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)
    assert generator.output_dir == temp_output_dir
    assert temp_output_dir.exists()


def test_report_generator_default_output_dir():
    """Test ReportGenerator creates default output directory"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator()
    assert generator.output_dir == Path("profiling/results")


def test_plot_resource_usage(temp_output_dir, sample_resource_data):
    """Test plotting resource usage over time"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)
    output_path = generator.plot_resource_usage(sample_resource_data)

    assert output_path.exists()
    assert output_path.name == "resource_usage.png"
    assert output_path.suffix == ".png"
    assert output_path.stat().st_size > 0


def test_plot_resource_usage_custom_filename(temp_output_dir, sample_resource_data):
    """Test plotting with custom output filename"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)
    output_path = generator.plot_resource_usage(
        sample_resource_data,
        output_file="custom_resource.png"
    )

    assert output_path.exists()
    assert output_path.name == "custom_resource.png"


def test_plot_resource_usage_empty_samples(temp_output_dir):
    """Test plotting with empty samples raises error"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)

    with pytest.raises(ValueError, match="No samples to plot"):
        generator.plot_resource_usage([])


def test_plot_function_times(temp_output_dir, sample_function_data):
    """Test plotting function times"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)
    output_path = generator.plot_function_times(sample_function_data)

    assert output_path.exists()
    assert output_path.name == "function_times.png"
    assert output_path.suffix == ".png"
    assert output_path.stat().st_size > 0


def test_plot_function_times_custom_filename(temp_output_dir, sample_function_data):
    """Test plotting functions with custom filename"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)
    output_path = generator.plot_function_times(
        sample_function_data,
        output_file="custom_functions.png"
    )

    assert output_path.exists()
    assert output_path.name == "custom_functions.png"


def test_plot_function_times_empty_functions(temp_output_dir):
    """Test plotting with empty functions raises error"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)

    with pytest.raises(ValueError, match="No functions to plot"):
        generator.plot_function_times([])


def test_plot_function_times_many_functions(temp_output_dir):
    """Test plotting with more than 10 functions (should take top 10)"""
    from profiling.report_generator import ReportGenerator

    # Create 15 functions
    many_functions = [
        {
            'function': (f'file{i}.py', i*10, f'function_{i}'),
            'calls': 100 - i,
            'total_time': 0.1 * i,
            'cumulative_time': 1.0 - (i * 0.05),
        }
        for i in range(15)
    ]

    generator = ReportGenerator(output_dir=temp_output_dir)
    output_path = generator.plot_function_times(many_functions)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_generate_summary_report(temp_output_dir, sample_function_data):
    """Test generating text summary report"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)

    profile_data = sample_function_data
    resource_data = {
        'duration_seconds': 5.5,
        'samples_count': 55,
        'cpu_mean': 15.5,
        'cpu_max': 25.0,
        'memory_mean_mb': 105.0,
        'memory_max_mb': 120.0,
    }

    output_path = generator.generate_summary_report(profile_data, resource_data)

    assert output_path.exists()
    assert output_path.name == "summary_report.txt"

    content = output_path.read_text()
    assert "PERFORMANCE ANALYSIS SUMMARY" in content
    assert "Resource Usage:" in content
    assert "Duration: 5.50 seconds" in content
    assert "Samples: 55" in content
    assert "CPU Mean: 15.5%" in content
    assert "Top Functions" in content
    assert "function_a" in content


def test_generate_summary_report_custom_filename(temp_output_dir, sample_function_data):
    """Test generating summary with custom filename"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)

    output_path = generator.generate_summary_report(
        sample_function_data,
        {},
        output_file="custom_summary.txt"
    )

    assert output_path.exists()
    assert output_path.name == "custom_summary.txt"


def test_generate_summary_report_no_resource_data(temp_output_dir, sample_function_data):
    """Test generating summary without resource data"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)

    output_path = generator.generate_summary_report(sample_function_data, {})

    assert output_path.exists()
    content = output_path.read_text()
    assert "PERFORMANCE ANALYSIS SUMMARY" in content
    assert "Top Functions" in content
    assert "Resource Usage:" not in content


def test_generate_summary_report_no_profile_data(temp_output_dir):
    """Test generating summary without profile data"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)

    resource_data = {
        'duration_seconds': 5.5,
        'samples_count': 55,
        'cpu_mean': 15.5,
        'cpu_max': 25.0,
        'memory_mean_mb': 105.0,
        'memory_max_mb': 120.0,
    }

    output_path = generator.generate_summary_report([], resource_data)

    assert output_path.exists()
    content = output_path.read_text()
    assert "PERFORMANCE ANALYSIS SUMMARY" in content
    assert "Resource Usage:" in content
    assert "Top Functions" not in content


def test_generate_summary_report_empty_data(temp_output_dir):
    """Test generating summary with no data"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)

    output_path = generator.generate_summary_report([], {})

    assert output_path.exists()
    content = output_path.read_text()
    assert "PERFORMANCE ANALYSIS SUMMARY" in content


def test_multiple_reports_same_generator(temp_output_dir, sample_resource_data, sample_function_data):
    """Test generating multiple reports with same generator instance"""
    from profiling.report_generator import ReportGenerator

    generator = ReportGenerator(output_dir=temp_output_dir)

    # Generate all three types of reports
    resource_plot = generator.plot_resource_usage(sample_resource_data, "report1_resource.png")
    function_plot = generator.plot_function_times(sample_function_data, "report1_functions.png")
    summary = generator.generate_summary_report(
        sample_function_data,
        {'duration_seconds': 1.0, 'samples_count': 10, 'cpu_mean': 10.0,
         'cpu_max': 20.0, 'memory_mean_mb': 100.0, 'memory_max_mb': 110.0},
        "report1_summary.txt"
    )

    assert resource_plot.exists()
    assert function_plot.exists()
    assert summary.exists()

    # All in same directory
    assert resource_plot.parent == temp_output_dir
    assert function_plot.parent == temp_output_dir
    assert summary.parent == temp_output_dir
