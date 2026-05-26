"""Tests for ResourceMonitor"""
import pytest
import time
from pathlib import Path
from profiling.resource_monitor import ResourceMonitor


def test_monitor_initialization():
    """Test monitor can be initialized"""
    monitor = ResourceMonitor(interval=0.1)
    assert monitor.interval == 0.1
    assert monitor.output_dir.exists()
    assert not monitor._monitoring


def test_monitor_start_stop():
    """Test monitor can start and stop"""
    monitor = ResourceMonitor(interval=0.1)

    monitor.start()
    assert monitor._monitoring
    assert monitor._thread is not None

    time.sleep(0.3)  # Let it collect some samples

    monitor.stop()
    assert not monitor._monitoring


def test_monitor_collects_samples():
    """Test monitor collects resource samples"""
    monitor = ResourceMonitor(interval=0.1)

    monitor.start()
    time.sleep(0.3)  # Collect ~3 samples
    monitor.stop()

    samples = monitor.get_samples()
    assert len(samples) >= 2

    # Check sample structure
    sample = samples[0]
    assert 'timestamp' in sample
    assert 'cpu_percent' in sample
    assert 'memory_mb' in sample
    assert 'memory_percent' in sample


def test_monitor_summary():
    """Test monitor generates summary statistics"""
    monitor = ResourceMonitor(interval=0.1)

    # Empty summary
    assert monitor.get_summary() == {}

    monitor.start()
    time.sleep(0.3)
    monitor.stop()

    summary = monitor.get_summary()
    assert 'duration_seconds' in summary
    assert 'samples_count' in summary
    assert 'cpu_mean' in summary
    assert 'cpu_max' in summary
    assert 'memory_mean_mb' in summary
    assert 'memory_max_mb' in summary

    assert summary['samples_count'] >= 2
    assert summary['duration_seconds'] > 0


def test_monitor_save_samples(tmp_path):
    """Test monitor saves samples to CSV"""
    monitor = ResourceMonitor(interval=0.1, output_dir=tmp_path)

    monitor.start()
    time.sleep(0.3)
    monitor.stop()

    output_path = monitor.save_samples("test_samples.csv")
    assert output_path.exists()

    # Check CSV content
    content = output_path.read_text()
    lines = content.strip().split('\n')

    assert lines[0] == "timestamp,cpu_percent,memory_mb,memory_percent"
    assert len(lines) >= 3  # Header + at least 2 samples


def test_monitor_cannot_start_twice():
    """Test monitor raises error if started twice"""
    monitor = ResourceMonitor(interval=0.1)

    monitor.start()

    with pytest.raises(RuntimeError, match="Monitor already running"):
        monitor.start()

    monitor.stop()


def test_monitor_stop_when_not_running():
    """Test stop is safe when monitor not running"""
    monitor = ResourceMonitor(interval=0.1)
    monitor.stop()  # Should not raise
