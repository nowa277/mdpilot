"""Tests for comprehensive workflow analyzer"""
import pytest
import time
from pathlib import Path
from profiling.analyze_workflow import WorkflowAnalyzer


def sample_workflow():
    """Sample workflow for testing"""
    total = 0
    for i in range(100000):
        total += i
    time.sleep(0.05)
    return total


def test_workflow_analyzer_initialization():
    """Test WorkflowAnalyzer initialization"""
    analyzer = WorkflowAnalyzer()
    assert analyzer.output_dir.exists()
    assert analyzer.profile_runner is not None
    assert analyzer.resource_monitor is not None
    assert analyzer.memory_profiler is not None
    assert analyzer.report_generator is not None


def test_workflow_analyzer_custom_output_dir(tmp_path):
    """Test WorkflowAnalyzer with custom output directory"""
    output_dir = tmp_path / "custom_results"
    analyzer = WorkflowAnalyzer(output_dir=output_dir)
    assert analyzer.output_dir == output_dir
    assert output_dir.exists()


def test_analyze_workflow(tmp_path):
    """Test comprehensive workflow analysis"""
    output_dir = tmp_path / "analysis_results"
    analyzer = WorkflowAnalyzer(output_dir=output_dir)

    results = analyzer.analyze(sample_workflow, "test_workflow")

    # Check return structure
    assert 'result' in results
    assert 'top_functions' in results
    assert 'resource_summary' in results
    assert 'output_dir' in results

    # Check result value
    assert results['result'] == sum(range(100000))

    # Check top functions
    assert len(results['top_functions']) > 0

    # Check resource summary
    summary = results['resource_summary']
    assert 'duration_seconds' in summary
    assert 'cpu_mean' in summary
    assert 'memory_max_mb' in summary
    assert summary['duration_seconds'] >= 0


def test_analyze_generates_files(tmp_path):
    """Test that analysis generates expected output files"""
    output_dir = tmp_path / "file_check"
    analyzer = WorkflowAnalyzer(output_dir=output_dir)

    analyzer.analyze(sample_workflow, "file_test")

    # Check for generated files
    expected_files = [
        "file_test_profile.txt",
        "file_test_resources.csv",
        "file_test_resource_usage.png",
        "file_test_function_times.png",
        "file_test_summary.txt",
    ]

    for filename in expected_files:
        file_path = output_dir / filename
        assert file_path.exists(), f"Expected file not found: {filename}"


def test_analyze_with_function_args(tmp_path):
    """Test analysis with function arguments"""
    def add_numbers(a, b, c=0):
        time.sleep(0.01)
        return a + b + c

    output_dir = tmp_path / "args_test"
    analyzer = WorkflowAnalyzer(output_dir=output_dir)

    results = analyzer.analyze(add_numbers, "add_test", 10, 20, c=5)

    assert results['result'] == 35


def test_analyze_with_exception(tmp_path):
    """Test that exceptions are propagated"""
    def failing_workflow():
        raise ValueError("Test error")

    output_dir = tmp_path / "error_test"
    analyzer = WorkflowAnalyzer(output_dir=output_dir)

    with pytest.raises(ValueError, match="Test error"):
        analyzer.analyze(failing_workflow, "error_workflow")


def test_multiple_analyses(tmp_path):
    """Test running multiple analyses with same analyzer"""
    output_dir = tmp_path / "multiple"
    analyzer = WorkflowAnalyzer(output_dir=output_dir)

    # Run first analysis
    results1 = analyzer.analyze(sample_workflow, "workflow1")
    assert results1['result'] == sum(range(100000))

    # Run second analysis
    results2 = analyzer.analyze(sample_workflow, "workflow2")
    assert results2['result'] == sum(range(100000))

    # Check both sets of files exist
    assert (output_dir / "workflow1_summary.txt").exists()
    assert (output_dir / "workflow2_summary.txt").exists()


def test_analyze_empty_workflow(tmp_path):
    """Test analysis of minimal workflow"""
    def empty_workflow():
        return None

    output_dir = tmp_path / "empty"
    analyzer = WorkflowAnalyzer(output_dir=output_dir)

    results = analyzer.analyze(empty_workflow, "empty")

    assert results['result'] is None
    assert 'resource_summary' in results
    assert 'top_functions' in results
