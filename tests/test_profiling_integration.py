"""Integration test for profiling components"""
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


def test_full_profiling_workflow(temp_output_dir):
    """Test complete profiling workflow: profile, monitor, generate reports"""
    from profiling.profile_runner import ProfileRunner
    from profiling.resource_monitor import ResourceMonitor
    from profiling.report_generator import ReportGenerator

    # Initialize components
    runner = ProfileRunner(output_dir=temp_output_dir)
    monitor = ResourceMonitor(interval=0.05, output_dir=temp_output_dir)
    generator = ReportGenerator(output_dir=temp_output_dir)

    # Start resource monitoring
    monitor.start()

    # Profile a sample workload
    def sample_workload():
        """Sample computation to profile"""
        result = 0
        for i in range(10000):
            result += i ** 2
        time.sleep(0.1)
        return result

    with runner.profile("integration_test"):
        result = sample_workload()

    # Stop monitoring
    time.sleep(0.2)  # Let monitor collect some samples
    monitor.stop()

    # Get profiling data
    top_functions = runner.get_top_functions("integration_test", n=10)
    resource_samples = monitor.get_samples()
    resource_summary = monitor.get_summary()

    # Generate reports
    assert len(top_functions) > 0
    assert len(resource_samples) > 0

    resource_plot = generator.plot_resource_usage(resource_samples, "integration_resource.png")
    function_plot = generator.plot_function_times(top_functions, "integration_functions.png")
    summary_report = generator.generate_summary_report(
        top_functions,
        resource_summary,
        "integration_summary.txt"
    )

    # Verify all outputs exist
    assert resource_plot.exists()
    assert function_plot.exists()
    assert summary_report.exists()

    # Verify summary content
    summary_content = summary_report.read_text()
    assert "PERFORMANCE ANALYSIS SUMMARY" in summary_content
    assert "Resource Usage:" in summary_content
    assert "Top Functions" in summary_content
    assert "Duration:" in summary_content
    assert "CPU Mean:" in summary_content
    assert "Memory Mean:" in summary_content

    # Verify workload executed correctly
    assert result == sum(i ** 2 for i in range(10000))


def test_report_generator_with_real_profile_data(temp_output_dir):
    """Test ReportGenerator with real ProfileRunner output"""
    from profiling.profile_runner import ProfileRunner
    from profiling.report_generator import ReportGenerator

    runner = ProfileRunner(output_dir=temp_output_dir)
    generator = ReportGenerator(output_dir=temp_output_dir)

    # Profile a simple function
    with runner.profile("real_data_test"):
        _ = [x ** 2 for x in range(1000)]

    # Get real function data
    functions = runner.get_top_functions("real_data_test", n=5)

    # Generate plot with real data
    output_path = generator.plot_function_times(functions, "real_functions.png")

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_report_generator_with_real_resource_data(temp_output_dir):
    """Test ReportGenerator with real ResourceMonitor output"""
    from profiling.resource_monitor import ResourceMonitor
    from profiling.report_generator import ReportGenerator

    monitor = ResourceMonitor(interval=0.05, output_dir=temp_output_dir)
    generator = ReportGenerator(output_dir=temp_output_dir)

    # Collect real resource samples
    monitor.start()
    time.sleep(0.3)  # Collect samples for 300ms
    monitor.stop()

    samples = monitor.get_samples()
    assert len(samples) > 0

    # Generate plot with real data
    output_path = generator.plot_resource_usage(samples, "real_resource.png")

    assert output_path.exists()
    assert output_path.stat().st_size > 0
