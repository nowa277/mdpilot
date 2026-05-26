"""Tests for anomaly_detector module."""

import time
from pathlib import Path

import pytest

from mdpilot.agent.monitoring import (
    Anomaly,
    AnomalyConfig,
    detect_anomalies,
)
from mdpilot.agent.monitoring import MDProgress


@pytest.fixture
def normal_progress():
    """Create a normal MDProgress object."""
    return MDProgress(
        current_step=5000,
        total_steps=500000,
        progress_pct=1.0,
        energy={"Etot": -123456.78, "EKtot": 12345.67, "EPtot": -135802.45},
        temperature=310.15,
        pressure=1.2,
        speed_ns_per_day=16.52,
        eta_hours=1424.4,
        last_update=time.time(),
    )


@pytest.fixture
def default_config():
    """Create default anomaly config."""
    return AnomalyConfig()


class TestAnomalyDataclass:
    """Test Anomaly dataclass."""

    def test_anomaly_creation(self):
        """Test creating Anomaly object."""
        anomaly = Anomaly(
            type="ENERGY_EXPLOSION",
            severity="CRITICAL",
            message="Energy exploded",
            timestamp=time.time(),
            details={"energy": 1e10},
        )
        assert anomaly.type == "ENERGY_EXPLOSION"
        assert anomaly.severity == "CRITICAL"
        assert anomaly.message == "Energy exploded"
        assert "energy" in anomaly.details


class TestAnomalyConfig:
    """Test AnomalyConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AnomalyConfig()
        assert config.energy_threshold == 1e6
        assert config.stuck_timeout_sec == 3600
        assert config.temp_range == (0, 500)
        assert config.pressure_range == (-1000, 1000)

    def test_custom_config(self):
        """Test custom configuration."""
        config = AnomalyConfig(
            energy_threshold=1e5,
            stuck_timeout_sec=1800,
            temp_range=(250, 350),
            pressure_range=(-500, 500),
        )
        assert config.energy_threshold == 1e5
        assert config.stuck_timeout_sec == 1800
        assert config.temp_range == (250, 350)
        assert config.pressure_range == (-500, 500)


class TestEnergyExplosion:
    """Test energy explosion detection."""

    def test_no_energy_explosion(self, normal_progress, default_config):
        """Test normal energy values."""
        anomalies = detect_anomalies(normal_progress, default_config)
        energy_anomalies = [a for a in anomalies if a.type == "ENERGY_EXPLOSION"]
        assert len(energy_anomalies) == 0

    def test_positive_energy_explosion(self, normal_progress, default_config):
        """Test positive energy explosion."""
        normal_progress.energy["Etot"] = 2e6
        anomalies = detect_anomalies(normal_progress, default_config)
        energy_anomalies = [a for a in anomalies if a.type == "ENERGY_EXPLOSION"]
        assert len(energy_anomalies) == 1
        assert energy_anomalies[0].severity == "CRITICAL"
        assert "2000000" in energy_anomalies[0].message or "2e+06" in energy_anomalies[0].message

    def test_negative_energy_explosion(self, normal_progress, default_config):
        """Test negative energy explosion."""
        normal_progress.energy["Etot"] = -2e6
        anomalies = detect_anomalies(normal_progress, default_config)
        energy_anomalies = [a for a in anomalies if a.type == "ENERGY_EXPLOSION"]
        assert len(energy_anomalies) == 1
        assert energy_anomalies[0].severity == "CRITICAL"

    def test_energy_at_threshold(self, normal_progress, default_config):
        """Test energy exactly at threshold."""
        normal_progress.energy["Etot"] = 1e6
        anomalies = detect_anomalies(normal_progress, default_config)
        energy_anomalies = [a for a in anomalies if a.type == "ENERGY_EXPLOSION"]
        # At threshold should not trigger (only > threshold)
        assert len(energy_anomalies) == 0

    def test_custom_energy_threshold(self, normal_progress):
        """Test custom energy threshold."""
        config = AnomalyConfig(energy_threshold=1e5)
        normal_progress.energy["Etot"] = 2e5
        normal_progress.energy["EPtot"] = -50000.0  # Below threshold
        normal_progress.energy["EKtot"] = 50000.0  # Below threshold
        anomalies = detect_anomalies(normal_progress, config)
        energy_anomalies = [a for a in anomalies if a.type == "ENERGY_EXPLOSION"]
        assert len(energy_anomalies) == 1


class TestSimulationStuck:
    """Test simulation stuck detection."""

    def test_no_stuck_recent_update(self, normal_progress, default_config):
        """Test with recent update."""
        normal_progress.last_update = time.time()
        anomalies = detect_anomalies(normal_progress, default_config)
        stuck_anomalies = [a for a in anomalies if a.type == "SIMULATION_STUCK"]
        assert len(stuck_anomalies) == 0

    def test_stuck_old_update(self, normal_progress, default_config):
        """Test with old update."""
        normal_progress.last_update = time.time() - 3700  # Over 1 hour ago
        anomalies = detect_anomalies(normal_progress, default_config)
        stuck_anomalies = [a for a in anomalies if a.type == "SIMULATION_STUCK"]
        assert len(stuck_anomalies) == 1
        assert stuck_anomalies[0].severity == "ERROR"
        assert "3700" in stuck_anomalies[0].message or "3.7e+03" in stuck_anomalies[0].message

    def test_stuck_at_threshold(self, normal_progress, default_config):
        """Test at exact threshold."""
        normal_progress.last_update = time.time() - 3600
        anomalies = detect_anomalies(normal_progress, default_config)
        stuck_anomalies = [a for a in anomalies if a.type == "SIMULATION_STUCK"]
        # At threshold should not trigger
        assert len(stuck_anomalies) == 0

    def test_custom_stuck_timeout(self, normal_progress):
        """Test custom stuck timeout."""
        config = AnomalyConfig(stuck_timeout_sec=1800)
        normal_progress.last_update = time.time() - 2000
        anomalies = detect_anomalies(normal_progress, config)
        stuck_anomalies = [a for a in anomalies if a.type == "SIMULATION_STUCK"]
        assert len(stuck_anomalies) == 1


class TestNaNValues:
    """Test NaN value detection."""

    def test_no_nan_values(self, normal_progress, default_config):
        """Test with normal values."""
        anomalies = detect_anomalies(normal_progress, default_config)
        nan_anomalies = [a for a in anomalies if a.type == "NAN_VALUE"]
        assert len(nan_anomalies) == 0

    def test_nan_in_etot(self, normal_progress, default_config):
        """Test NaN in total energy."""
        normal_progress.energy["Etot"] = float("nan")
        anomalies = detect_anomalies(normal_progress, default_config)
        nan_anomalies = [a for a in anomalies if a.type == "NAN_VALUE"]
        assert len(nan_anomalies) == 1
        assert nan_anomalies[0].severity == "CRITICAL"
        assert "Etot" in nan_anomalies[0].message

    def test_nan_in_ektot(self, normal_progress, default_config):
        """Test NaN in kinetic energy."""
        normal_progress.energy["EKtot"] = float("nan")
        anomalies = detect_anomalies(normal_progress, default_config)
        nan_anomalies = [a for a in anomalies if a.type == "NAN_VALUE"]
        assert len(nan_anomalies) == 1
        assert "EKtot" in nan_anomalies[0].message

    def test_nan_in_eptot(self, normal_progress, default_config):
        """Test NaN in potential energy."""
        normal_progress.energy["EPtot"] = float("nan")
        anomalies = detect_anomalies(normal_progress, default_config)
        nan_anomalies = [a for a in anomalies if a.type == "NAN_VALUE"]
        assert len(nan_anomalies) == 1
        assert "EPtot" in nan_anomalies[0].message

    def test_nan_in_temperature(self, normal_progress, default_config):
        """Test NaN in temperature."""
        normal_progress.temperature = float("nan")
        anomalies = detect_anomalies(normal_progress, default_config)
        nan_anomalies = [a for a in anomalies if a.type == "NAN_VALUE"]
        assert len(nan_anomalies) == 1
        assert "temperature" in nan_anomalies[0].message.lower()

    def test_nan_in_pressure(self, normal_progress, default_config):
        """Test NaN in pressure."""
        normal_progress.pressure = float("nan")
        anomalies = detect_anomalies(normal_progress, default_config)
        nan_anomalies = [a for a in anomalies if a.type == "NAN_VALUE"]
        assert len(nan_anomalies) == 1
        assert "pressure" in nan_anomalies[0].message.lower()

    def test_multiple_nan_values(self, normal_progress, default_config):
        """Test multiple NaN values."""
        normal_progress.energy["Etot"] = float("nan")
        normal_progress.temperature = float("nan")
        anomalies = detect_anomalies(normal_progress, default_config)
        nan_anomalies = [a for a in anomalies if a.type == "NAN_VALUE"]
        # Should detect multiple NaN values
        assert len(nan_anomalies) >= 1


class TestTemperatureAnomaly:
    """Test temperature anomaly detection."""

    def test_normal_temperature(self, normal_progress, default_config):
        """Test normal temperature."""
        anomalies = detect_anomalies(normal_progress, default_config)
        temp_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "temperature" in a.message.lower()]
        assert len(temp_anomalies) == 0

    def test_temperature_too_low(self, normal_progress, default_config):
        """Test temperature below range."""
        normal_progress.temperature = -10.0
        anomalies = detect_anomalies(normal_progress, default_config)
        temp_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "temperature" in a.message.lower()]
        assert len(temp_anomalies) == 1
        assert temp_anomalies[0].severity == "WARNING"

    def test_temperature_too_high(self, normal_progress, default_config):
        """Test temperature above range."""
        normal_progress.temperature = 600.0
        anomalies = detect_anomalies(normal_progress, default_config)
        temp_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "temperature" in a.message.lower()]
        assert len(temp_anomalies) == 1
        assert temp_anomalies[0].severity == "WARNING"

    def test_temperature_at_lower_bound(self, normal_progress, default_config):
        """Test temperature at lower bound."""
        normal_progress.temperature = 0.0
        anomalies = detect_anomalies(normal_progress, default_config)
        temp_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "temperature" in a.message.lower()]
        assert len(temp_anomalies) == 0

    def test_temperature_at_upper_bound(self, normal_progress, default_config):
        """Test temperature at upper bound."""
        normal_progress.temperature = 500.0
        anomalies = detect_anomalies(normal_progress, default_config)
        temp_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "temperature" in a.message.lower()]
        assert len(temp_anomalies) == 0

    def test_temperature_none(self, normal_progress, default_config):
        """Test with None temperature (minimization)."""
        normal_progress.temperature = None
        anomalies = detect_anomalies(normal_progress, default_config)
        temp_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "temperature" in a.message.lower()]
        assert len(temp_anomalies) == 0

    def test_custom_temperature_range(self, normal_progress):
        """Test custom temperature range."""
        config = AnomalyConfig(temp_range=(250, 350))
        normal_progress.temperature = 400.0
        anomalies = detect_anomalies(normal_progress, config)
        temp_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "temperature" in a.message.lower()]
        assert len(temp_anomalies) == 1


class TestPressureAnomaly:
    """Test pressure anomaly detection."""

    def test_normal_pressure(self, normal_progress, default_config):
        """Test normal pressure."""
        anomalies = detect_anomalies(normal_progress, default_config)
        press_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "pressure" in a.message.lower()]
        assert len(press_anomalies) == 0

    def test_pressure_too_low(self, normal_progress, default_config):
        """Test pressure below range."""
        normal_progress.pressure = -1500.0
        anomalies = detect_anomalies(normal_progress, default_config)
        press_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "pressure" in a.message.lower()]
        assert len(press_anomalies) == 1
        assert press_anomalies[0].severity == "WARNING"

    def test_pressure_too_high(self, normal_progress, default_config):
        """Test pressure above range."""
        normal_progress.pressure = 1500.0
        anomalies = detect_anomalies(normal_progress, default_config)
        press_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "pressure" in a.message.lower()]
        assert len(press_anomalies) == 1
        assert press_anomalies[0].severity == "WARNING"

    def test_pressure_at_bounds(self, normal_progress, default_config):
        """Test pressure at bounds."""
        normal_progress.pressure = -1000.0
        anomalies = detect_anomalies(normal_progress, default_config)
        press_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "pressure" in a.message.lower()]
        assert len(press_anomalies) == 0

        normal_progress.pressure = 1000.0
        anomalies = detect_anomalies(normal_progress, default_config)
        press_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "pressure" in a.message.lower()]
        assert len(press_anomalies) == 0

    def test_pressure_none(self, normal_progress, default_config):
        """Test with None pressure (minimization)."""
        normal_progress.pressure = None
        anomalies = detect_anomalies(normal_progress, default_config)
        press_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "pressure" in a.message.lower()]
        assert len(press_anomalies) == 0

    def test_custom_pressure_range(self, normal_progress):
        """Test custom pressure range."""
        config = AnomalyConfig(pressure_range=(-500, 500))
        normal_progress.pressure = 800.0
        anomalies = detect_anomalies(normal_progress, config)
        press_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "pressure" in a.message.lower()]
        assert len(press_anomalies) == 1


class TestMultipleAnomalies:
    """Test detection of multiple anomalies."""

    def test_multiple_anomalies_detected(self, normal_progress, default_config):
        """Test detecting multiple anomalies at once."""
        normal_progress.energy["Etot"] = 2e6  # Energy explosion
        normal_progress.temperature = 600.0  # Temperature too high
        normal_progress.pressure = -1500.0  # Pressure too low
        normal_progress.last_update = time.time() - 3700  # Stuck

        anomalies = detect_anomalies(normal_progress, default_config)
        assert len(anomalies) >= 4

        types = {a.type for a in anomalies}
        assert "ENERGY_EXPLOSION" in types
        assert "TEMP_PRESSURE_ANOMALY" in types
        assert "SIMULATION_STUCK" in types

    def test_no_anomalies(self, normal_progress, default_config):
        """Test with no anomalies."""
        anomalies = detect_anomalies(normal_progress, default_config)
        assert len(anomalies) == 0

    def test_all_critical_anomalies(self, normal_progress, default_config):
        """Test all critical anomalies."""
        normal_progress.energy["Etot"] = float("nan")
        normal_progress.energy["EKtot"] = 2e6

        anomalies = detect_anomalies(normal_progress, default_config)
        critical = [a for a in anomalies if a.severity == "CRITICAL"]
        assert len(critical) >= 2


class TestAnomalyDetails:
    """Test anomaly details field."""

    def test_energy_explosion_details(self, normal_progress, default_config):
        """Test energy explosion includes details."""
        normal_progress.energy["Etot"] = 2e6
        anomalies = detect_anomalies(normal_progress, default_config)
        energy_anomalies = [a for a in anomalies if a.type == "ENERGY_EXPLOSION"]
        assert len(energy_anomalies) == 1
        assert "energy" in energy_anomalies[0].details
        assert energy_anomalies[0].details["energy"] == 2e6

    def test_stuck_details(self, normal_progress, default_config):
        """Test stuck simulation includes details."""
        normal_progress.last_update = time.time() - 3700
        anomalies = detect_anomalies(normal_progress, default_config)
        stuck_anomalies = [a for a in anomalies if a.type == "SIMULATION_STUCK"]
        assert len(stuck_anomalies) == 1
        assert "seconds_since_update" in stuck_anomalies[0].details

    def test_temperature_anomaly_details(self, normal_progress, default_config):
        """Test temperature anomaly includes details."""
        normal_progress.temperature = 600.0
        anomalies = detect_anomalies(normal_progress, default_config)
        temp_anomalies = [a for a in anomalies if a.type == "TEMP_PRESSURE_ANOMALY" and "temperature" in a.message.lower()]
        assert len(temp_anomalies) == 1
        assert "value" in temp_anomalies[0].details
        assert temp_anomalies[0].details["value"] == 600.0
