"""Test profiling fixtures integration with pytest"""
import time
import pytest


def sample_workload():
    """Sample function for profiling tests"""
    total = 0
    for i in range(100000):
        total += i ** 2
    time.sleep(0.05)
    return total


def memory_intensive_workload():
    """Memory-intensive workload for testing"""
    data = []
    for i in range(1000):
        data.append([j for j in range(1000)])
    return len(data)


class TestProfilingFixtures:
    """Test suite demonstrating profiling fixture usage"""

    def test_profile_runner_fixture(self, profile_runner):
        """Test ProfileRunner fixture"""
        # Profile a code block
        with profile_runner.profile("test_workload"):
            result = sample_workload()

        assert result > 0

        # Get profiling results
        top_functions = profile_runner.get_top_functions("test_workload", n=5)
        assert len(top_functions) > 0
        assert all('function' in f for f in top_functions)
        assert all('cumulative_time' in f for f in top_functions)

        # Save stats
        output_path = profile_runner.save_stats("test_workload")
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_resource_monitor_fixture(self, resource_monitor):
        """Test ResourceMonitor fixture"""
        # Start monitoring
        resource_monitor.start()

        # Give monitor time to collect initial sample
        time.sleep(0.15)

        # Run workload
        result = sample_workload()
        assert result > 0

        # Stop monitoring
        resource_monitor.stop()

        # Get samples
        samples = resource_monitor.get_samples()
        assert len(samples) > 0
        assert all('cpu_percent' in s for s in samples)
        assert all('memory_mb' in s for s in samples)

        # Get summary
        summary = resource_monitor.get_summary()
        assert 'duration_seconds' in summary
        assert 'cpu_mean' in summary
        assert 'memory_max_mb' in summary
        assert summary['duration_seconds'] >= 0

        # Save samples
        output_path = resource_monitor.save_samples("test_resources.csv")
        assert output_path.exists()

    def test_memory_profiler_fixture(self, memory_profiler):
        """Test MemoryProfiler fixture"""
        # Profile function
        result, report = memory_profiler.profile_function(memory_intensive_workload)
        assert result == 1000
        assert len(report) > 0

        # Parse report
        parsed = memory_profiler.parse_report(report)
        assert 'lines' in parsed
        assert 'peak_memory_mb' in parsed

        # Save report
        output_path = memory_profiler.save_report(report, "test_memory.txt")
        assert output_path.exists()

    def test_report_generator_fixture(self, report_generator, resource_monitor):
        """Test ReportGenerator fixture"""
        # Generate sample data
        resource_monitor.start()
        sample_workload()
        resource_monitor.stop()

        samples = resource_monitor.get_samples()
        assert len(samples) > 0

        # Generate resource usage plot
        plot_path = report_generator.plot_resource_usage(
            samples,
            "test_resource_plot.png"
        )
        assert plot_path.exists()
        assert plot_path.suffix == '.png'

    def test_workflow_analyzer_fixture(self, workflow_analyzer):
        """Test WorkflowAnalyzer fixture"""
        # Analyze a workflow
        results = workflow_analyzer.analyze(
            sample_workload,
            name="test_workflow"
        )

        # Check results structure
        assert 'result' in results
        assert 'top_functions' in results
        assert 'resource_summary' in results
        assert 'output_dir' in results

        # Verify result
        assert results['result'] > 0

        # Verify profiling data
        assert len(results['top_functions']) > 0
        assert 'duration_seconds' in results['resource_summary']

        # Verify output files
        output_dir = results['output_dir']
        assert output_dir.exists()
        assert (output_dir / "test_workflow_profile.txt").exists()
        assert (output_dir / "test_workflow_resources.csv").exists()
        assert (output_dir / "test_workflow_summary.txt").exists()

    def test_combined_profiling(self, profile_runner, resource_monitor, report_generator):
        """Test combining multiple profiling tools"""
        # Start resource monitoring
        resource_monitor.start()

        # Profile execution
        with profile_runner.profile("combined_test"):
            result = sample_workload()

        # Stop monitoring
        resource_monitor.stop()

        assert result > 0

        # Get all data
        top_functions = profile_runner.get_top_functions("combined_test", n=10)
        resource_summary = resource_monitor.get_summary()
        resource_samples = resource_monitor.get_samples()

        # Generate reports
        report_generator.generate_summary_report(
            top_functions,
            resource_summary,
            "combined_summary.txt"
        )

        if resource_samples:
            report_generator.plot_resource_usage(
                resource_samples,
                "combined_resources.png"
            )

        if top_functions:
            report_generator.plot_function_times(
                top_functions,
                "combined_functions.png"
            )

        # Verify all outputs exist
        assert (report_generator.output_dir / "combined_summary.txt").exists()
        assert (report_generator.output_dir / "combined_resources.png").exists()
        assert (report_generator.output_dir / "combined_functions.png").exists()


class TestProfilingFixturesIsolation:
    """Test that fixtures are properly isolated between tests"""

    def test_fixture_isolation_1(self, profile_runner):
        """First test using profile_runner"""
        with profile_runner.profile("test1"):
            sample_workload()

        assert "test1" in profile_runner.stats
        assert "test2" not in profile_runner.stats

    def test_fixture_isolation_2(self, profile_runner):
        """Second test using profile_runner - should be fresh instance"""
        # This should be a fresh ProfileRunner due to function scope
        assert len(profile_runner.stats) == 0

        with profile_runner.profile("test2"):
            sample_workload()

        assert "test2" in profile_runner.stats
        assert "test1" not in profile_runner.stats


@pytest.mark.parametrize("workload_size", [1000, 10000, 50000])
def test_profiling_with_parametrize(profile_runner, workload_size):
    """Test profiling with parametrized tests"""
    def parametrized_workload():
        total = 0
        for i in range(workload_size):
            total += i
        return total

    with profile_runner.profile(f"workload_{workload_size}"):
        result = parametrized_workload()

    assert result > 0

    top_functions = profile_runner.get_top_functions(f"workload_{workload_size}", n=3)
    assert len(top_functions) > 0
