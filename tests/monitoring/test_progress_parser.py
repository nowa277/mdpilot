"""Tests for progress_parser module."""

import time
from pathlib import Path

import pytest

from mdpilot.agent.monitoring import (
    MDProgress,
    calculate_speed,
    estimate_eta,
    parse_output_file,
)


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures."""
    return Path(__file__).parent.parent / "fixtures" / "pmemd_outputs"


class TestMDProgress:
    """Test MDProgress dataclass."""

    def test_mdprogress_creation(self):
        """Test creating MDProgress object."""
        progress = MDProgress(
            current_step=1000,
            total_steps=5000,
            progress_pct=20.0,
            energy={"Etot": -123456.78, "EKtot": 12345.67, "EPtot": -135802.45},
            temperature=310.15,
            pressure=1.2,
            speed_ns_per_day=16.52,
            eta_hours=2.5,
            last_update=time.time(),
        )
        assert progress.current_step == 1000
        assert progress.total_steps == 5000
        assert progress.progress_pct == 20.0
        assert progress.energy["Etot"] == -123456.78
        assert progress.temperature == 310.15
        assert progress.pressure == 1.2
        assert progress.speed_ns_per_day == 16.52
        assert progress.eta_hours == 2.5


class TestParseOutputFile:
    """Test parse_output_file function."""

    def test_parse_minimization_output(self, fixtures_dir):
        """Test parsing minimization output file."""
        out_file = fixtures_dir / "minimization.out"
        progress = parse_output_file(out_file)

        assert progress is not None
        assert progress.current_step == 5000
        assert progress.total_steps == 5000
        assert progress.progress_pct == 100.0
        # Minimization doesn't have temperature/pressure in NSTEP lines
        assert progress.temperature is None
        assert progress.pressure is None

    def test_parse_production_output(self, fixtures_dir):
        """Test parsing production MD output file."""
        out_file = fixtures_dir / "production.out"
        progress = parse_output_file(out_file)

        assert progress is not None
        assert progress.current_step == 5000
        assert progress.total_steps == 500000
        assert progress.progress_pct == 1.0
        assert progress.energy["Etot"] == pytest.approx(-123501.2345, rel=1e-6)
        assert progress.energy["EKtot"] == pytest.approx(12323.4567, rel=1e-6)
        assert progress.energy["EPtot"] == pytest.approx(-135824.6912, rel=1e-6)
        assert progress.temperature == pytest.approx(309.78, rel=1e-6)
        assert progress.pressure == pytest.approx(-1.2, rel=1e-6)
        assert progress.speed_ns_per_day == pytest.approx(16.68, rel=1e-6)

    def test_parse_incomplete_output(self, fixtures_dir):
        """Test parsing incomplete output file."""
        out_file = fixtures_dir / "incomplete.out"
        progress = parse_output_file(out_file)

        assert progress is not None
        assert progress.current_step == 1000
        assert progress.total_steps == 500000
        assert progress.progress_pct == pytest.approx(0.2, rel=1e-6)
        assert progress.speed_ns_per_day is None  # No timing info yet

    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing non-existent file."""
        out_file = tmp_path / "nonexistent.out"
        progress = parse_output_file(out_file)
        assert progress is None

    def test_parse_empty_file(self, tmp_path):
        """Test parsing empty file."""
        out_file = tmp_path / "empty.out"
        out_file.write_text("")
        progress = parse_output_file(out_file)
        assert progress is None

    def test_parse_malformed_file(self, tmp_path):
        """Test parsing malformed file."""
        out_file = tmp_path / "malformed.out"
        out_file.write_text("This is not a valid AMBER output file\n")
        progress = parse_output_file(out_file)
        assert progress is None

    def test_parse_without_input_file(self, tmp_path):
        """Test parsing output when input file doesn't exist."""
        out_file = tmp_path / "test.out"
        out_file.write_text(
            """
 NSTEP =     1000   TIME(PS) =       2.000  TEMP(K) =   310.15  PRESS =     1.2
 Etot   =   -123456.7890  EKtot   =     12345.6789  EPtot      =   -135802.4679
"""
        )
        progress = parse_output_file(out_file)
        # Should still parse but total_steps will be unknown
        assert progress is not None
        assert progress.current_step == 1000
        # When input file is missing, we can't determine total_steps
        # Implementation should handle this gracefully


class TestCalculateSpeed:
    """Test calculate_speed function."""

    def test_calculate_speed_basic(self):
        """Test basic speed calculation."""
        # 1000 steps, 5.23 seconds, dt=0.002 ps
        # 1000 * 0.002 = 2 ps = 0.002 ns
        # 0.002 ns / 5.23 s = 0.000382 ns/s
        # 0.000382 * 86400 = 33.02 ns/day
        speed = calculate_speed(steps=1000, elapsed_time=5.23, dt=0.002)
        assert speed == pytest.approx(33.02, rel=1e-2)

    def test_calculate_speed_zero_time(self):
        """Test speed calculation with zero elapsed time."""
        speed = calculate_speed(steps=1000, elapsed_time=0.0, dt=0.002)
        assert speed == 0.0

    def test_calculate_speed_different_dt(self):
        """Test speed calculation with different timestep."""
        # 1000 steps, 5.23 seconds, dt=0.001 ps
        speed = calculate_speed(steps=1000, elapsed_time=5.23, dt=0.001)
        assert speed == pytest.approx(16.51, rel=1e-2)


class TestEstimateETA:
    """Test estimate_eta function."""

    def test_estimate_eta_basic(self):
        """Test basic ETA estimation."""
        # Current: 5000, Total: 500000, Speed: 16.68 ns/day
        # Remaining: 495000 steps
        # At 495000 steps * 0.002 ps = 990 ps = 0.99 ns
        # At 16.68 ns/day: 0.99 / 16.68 = 0.0594 days = 1.42 hours
        eta = estimate_eta(current_step=5000, total_steps=500000, speed=16.68)
        assert eta == pytest.approx(1.42, rel=1e-2)

    def test_estimate_eta_near_completion(self):
        """Test ETA when near completion."""
        eta = estimate_eta(current_step=4900, total_steps=5000, speed=16.68)
        assert eta < 1.0  # Should be less than 1 hour

    def test_estimate_eta_zero_speed(self):
        """Test ETA with zero speed."""
        eta = estimate_eta(current_step=1000, total_steps=5000, speed=0.0)
        assert eta == float("inf")

    def test_estimate_eta_completed(self):
        """Test ETA when already completed."""
        eta = estimate_eta(current_step=5000, total_steps=5000, speed=16.68)
        assert eta == 0.0


class TestIntegration:
    """Integration tests for progress parsing."""

    def test_full_workflow_production(self, fixtures_dir):
        """Test full workflow with production output."""
        out_file = fixtures_dir / "production.out"
        progress = parse_output_file(out_file)

        assert progress is not None
        assert progress.current_step > 0
        assert progress.total_steps > progress.current_step
        assert 0 <= progress.progress_pct <= 100
        assert progress.energy["Etot"] < 0  # Energy should be negative
        assert progress.temperature is not None
        assert progress.temperature > 0
        assert progress.speed_ns_per_day is not None
        assert progress.speed_ns_per_day > 0

        # Verify ETA calculation
        if progress.speed_ns_per_day and progress.speed_ns_per_day > 0:
            eta = estimate_eta(
                progress.current_step, progress.total_steps, progress.speed_ns_per_day
            )
            assert eta > 0

    def test_timestamp_is_recent(self, fixtures_dir):
        """Test that parsed timestamp is recent."""
        out_file = fixtures_dir / "production.out"
        progress = parse_output_file(out_file)

        assert progress is not None
        # Timestamp should be within last few seconds
        assert time.time() - progress.last_update < 5.0
