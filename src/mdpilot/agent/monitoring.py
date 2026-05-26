"""MD simulation monitoring — progress parsing and anomaly detection."""

import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MDProgress:
    """MD simulation progress information."""

    current_step: int
    total_steps: int
    progress_pct: float
    energy: dict[str, float]  # {"Etot": ..., "EKtot": ..., "EPtot": ...}
    temperature: float | None
    pressure: float | None
    speed_ns_per_day: float | None
    eta_hours: float | None
    last_update: float  # timestamp


@dataclass
class Anomaly:
    """Simulation anomaly."""

    type: str  # "ENERGY_EXPLOSION", "SIMULATION_STUCK", "NAN_VALUE", "TEMP_PRESSURE_ANOMALY"
    severity: str  # "WARNING", "ERROR", "CRITICAL"
    message: str
    timestamp: float
    details: dict[str, Any]


@dataclass
class AnomalyConfig:
    """Anomaly detection configuration."""

    energy_threshold: float = 1e6
    stuck_timeout_sec: int = 3600
    temp_range: tuple[float, float] = (0, 500)
    pressure_range: tuple[float, float] = (-1000, 1000)


def parse_output_file(out_file: Path) -> MDProgress | None:
    """Parse pmemd.cuda output file and return latest progress.

    Args:
        out_file: Path to .out file

    Returns:
        MDProgress object, or None if file is empty or cannot be parsed
    """
    if not out_file.exists():
        return None

    try:
        content = out_file.read_text()
    except Exception:
        return None

    if not content.strip():
        return None

    # Parse NSTEP lines to get current step, energy, temp, pressure
    # Pattern: NSTEP =     1000   TIME(PS) =       2.000  TEMP(K) =   310.15  PRESS =     1.2
    nstep_pattern = re.compile(
        r"NSTEP\s+=\s+(\d+)\s+TIME\(PS\)\s+=\s+([\d.]+)\s+TEMP\(K\)\s+=\s+([\d.-]+)\s+PRESS\s+=\s+([\d.-]+)"
    )

    # Pattern for minimization (no TEMP/PRESS)
    # NSTEP       ENERGY          RMS            GMAX         NAME    NUMBER
    #  5000      -1.4567E+05     5.6789E-04     1.2345E-02     CD       4567
    min_nstep_pattern = re.compile(r"^\s+(\d+)\s+([-+]?\d+\.\d+E[+-]\d+)", re.MULTILINE)

    # Pattern for energy lines (production MD)
    # Etot   =   -123456.7890  EKtot   =     12345.6789  EPtot      =   -135802.4679
    energy_pattern = re.compile(
        r"Etot\s+=\s+([-\d.]+)\s+EKtot\s+=\s+([-\d.]+)\s+EPtot\s+=\s+([-\d.]+)"
    )

    # Pattern for minimization energy lines
    # BOND    =     1234.5678  ANGLE   =     2345.6789  DIHED      =     3456.7890
    # VDWAALS =    12345.6789  EEL     =  -145678.9012  HBOND      =        0.0000
    min_energy_pattern = re.compile(
        r"BOND\s+=\s+([-\d.]+)\s+ANGLE\s+=\s+([-\d.]+)\s+DIHED\s+=\s+([-\d.]+)\s+"
        r"VDWAALS\s+=\s+([-\d.]+)\s+EEL\s+=\s+([-\d.]+)"
    )

    # Pattern for timing info
    # ns/day =      16.52   seconds/ns =    5229.12
    timing_pattern = re.compile(r"ns/day\s+=\s+([\d.]+)")

    # Find all NSTEP entries
    nstep_matches = list(nstep_pattern.finditer(content))
    min_nstep_matches = list(min_nstep_pattern.finditer(content))

    current_step = None
    temperature = None
    pressure = None
    is_minimization = False

    if nstep_matches:
        # Production MD with temp/pressure
        last_match = nstep_matches[-1]
        current_step = int(last_match.group(1))
        temperature = float(last_match.group(3))
        pressure = float(last_match.group(4))
    elif min_nstep_matches:
        # Minimization without temp/pressure
        last_match = min_nstep_matches[-1]
        current_step = int(last_match.group(1))
        is_minimization = True

    if current_step is None:
        return None

    # Find last energy values
    energy = None
    energy_matches = list(energy_pattern.finditer(content))
    if energy_matches:
        last_energy = energy_matches[-1]
        energy = {
            "Etot": float(last_energy.group(1)),
            "EKtot": float(last_energy.group(2)),
            "EPtot": float(last_energy.group(3)),
        }
    elif is_minimization:
        # Try minimization energy format
        min_energy_matches = list(min_energy_pattern.finditer(content))
        if min_energy_matches:
            last_min_energy = min_energy_matches[-1]
            # Calculate total energy from components
            bond = float(last_min_energy.group(1))
            angle = float(last_min_energy.group(2))
            dihed = float(last_min_energy.group(3))
            vdwaals = float(last_min_energy.group(4))
            eel = float(last_min_energy.group(5))

            # Look for 1-4 terms on next line
            one_four_pattern = re.compile(r"1-4 VDW\s+=\s+([-\d.]+)\s+1-4 EEL\s+=\s+([-\d.]+)")
            one_four_matches = list(one_four_pattern.finditer(content))
            vdw_14 = 0.0
            eel_14 = 0.0
            if one_four_matches:
                last_14 = one_four_matches[-1]
                vdw_14 = float(last_14.group(1))
                eel_14 = float(last_14.group(2))

            etot = bond + angle + dihed + vdwaals + eel + vdw_14 + eel_14
            energy = {
                "Etot": etot,
                "EKtot": 0.0,  # No kinetic energy in minimization
                "EPtot": etot,
            }

    if energy is None:
        return None

    # Find timing info
    timing_matches = list(timing_pattern.finditer(content))
    speed_ns_per_day = None
    if timing_matches:
        speed_ns_per_day = float(timing_matches[-1].group(1))

    # Try to get total_steps from input file or embedded input
    total_steps = current_step  # Default to current step

    # First try to find embedded input in the output file
    nstlim_match = re.search(r"nstlim\s*=\s*(\d+)", content)
    maxcyc_match = re.search(r"maxcyc\s*=\s*(\d+)", content)

    if nstlim_match:
        total_steps = int(nstlim_match.group(1))
    elif maxcyc_match:
        total_steps = int(maxcyc_match.group(1))
    else:
        # Try separate input file
        input_file = out_file.with_suffix(".in")
        if input_file.exists():
            try:
                input_content = input_file.read_text()
                nstlim_match = re.search(r"nstlim\s*=\s*(\d+)", input_content)
                maxcyc_match = re.search(r"maxcyc\s*=\s*(\d+)", input_content)
                if nstlim_match:
                    total_steps = int(nstlim_match.group(1))
                elif maxcyc_match:
                    total_steps = int(maxcyc_match.group(1))
            except Exception:
                pass

    # Calculate progress percentage
    progress_pct = (current_step / total_steps * 100) if total_steps > 0 else 0.0

    # Calculate ETA if we have speed
    eta_hours = None
    if speed_ns_per_day and speed_ns_per_day > 0:
        eta_hours = estimate_eta(current_step, total_steps, speed_ns_per_day)

    return MDProgress(
        current_step=current_step,
        total_steps=total_steps,
        progress_pct=progress_pct,
        energy=energy,
        temperature=temperature,
        pressure=pressure,
        speed_ns_per_day=speed_ns_per_day,
        eta_hours=eta_hours,
        last_update=time.time(),
    )


def calculate_speed(steps: int, elapsed_time: float, dt: float = 0.002) -> float:
    """Calculate simulation speed in ns/day.

    Args:
        steps: Number of steps completed
        elapsed_time: Elapsed time in seconds
        dt: Timestep in ps (default: 0.002)

    Returns:
        Simulation speed in ns/day
    """
    if elapsed_time <= 0:
        return 0.0

    # Calculate nanoseconds simulated
    ns_simulated = steps * dt / 1000.0  # dt is in ps, convert to ns

    # Calculate ns per second
    ns_per_sec = ns_simulated / elapsed_time

    # Convert to ns per day
    ns_per_day = ns_per_sec * 86400  # 86400 seconds in a day

    return ns_per_day


def estimate_eta(current_step: int, total_steps: int, speed: float) -> float:
    """Estimate remaining time in hours.

    Args:
        current_step: Current step number
        total_steps: Total number of steps
        speed: Simulation speed in ns/day

    Returns:
        Estimated remaining time in hours
    """
    if current_step >= total_steps:
        return 0.0

    if speed <= 0:
        return float("inf")

    # Calculate remaining steps
    remaining_steps = total_steps - current_step

    # Assuming dt = 0.002 ps (standard for AMBER)
    dt = 0.002  # ps per step

    # Calculate remaining time in ns
    remaining_ps = remaining_steps * dt
    remaining_ns = remaining_ps / 1000.0

    # Calculate days needed at given speed (ns/day)
    days_needed = remaining_ns / speed

    # Convert to hours
    hours_needed = days_needed * 24.0

    return hours_needed


def detect_anomalies(
    progress: MDProgress, config: AnomalyConfig = AnomalyConfig()
) -> list[Anomaly]:
    """Detect simulation anomalies.

    Args:
        progress: Current simulation progress
        config: Detection configuration

    Returns:
        List of detected anomalies
    """
    anomalies = []
    current_time = time.time()

    # 1. Check for energy explosion
    for energy_key in ["Etot", "EKtot", "EPtot"]:
        energy_value = progress.energy.get(energy_key, 0.0)
        if abs(energy_value) > config.energy_threshold:
            anomalies.append(
                Anomaly(
                    type="ENERGY_EXPLOSION",
                    severity="CRITICAL",
                    message=f"Energy explosion detected: {energy_key} = {energy_value:.2f}",
                    timestamp=current_time,
                    details={"energy": energy_value, "field": energy_key},
                )
            )

    # 2. Check for simulation stuck (strictly greater than threshold)
    time_since_update = current_time - progress.last_update
    if time_since_update > config.stuck_timeout_sec and time_since_update - config.stuck_timeout_sec > 0.001:
        anomalies.append(
            Anomaly(
                type="SIMULATION_STUCK",
                severity="ERROR",
                message=f"Simulation appears stuck: no update for {time_since_update:.0f} seconds",
                timestamp=current_time,
                details={"seconds_since_update": time_since_update},
            )
        )

    # 3. Check for NaN values
    nan_fields = []

    # Check energy values
    for key, value in progress.energy.items():
        if math.isnan(value):
            nan_fields.append(key)

    # Check temperature
    if progress.temperature is not None and math.isnan(progress.temperature):
        nan_fields.append("temperature")

    # Check pressure
    if progress.pressure is not None and math.isnan(progress.pressure):
        nan_fields.append("pressure")

    if nan_fields:
        anomalies.append(
            Anomaly(
                type="NAN_VALUE",
                severity="CRITICAL",
                message=f"NaN values detected in: {', '.join(nan_fields)}",
                timestamp=current_time,
                details={"fields": nan_fields},
            )
        )

    # 4. Check temperature anomaly
    if progress.temperature is not None and not math.isnan(progress.temperature):
        temp_min, temp_max = config.temp_range
        if progress.temperature < temp_min or progress.temperature > temp_max:
            anomalies.append(
                Anomaly(
                    type="TEMP_PRESSURE_ANOMALY",
                    severity="WARNING",
                    message=f"Temperature out of range: {progress.temperature:.2f} K (expected {temp_min}-{temp_max} K)",
                    timestamp=current_time,
                    details={"value": progress.temperature, "range": config.temp_range},
                )
            )

    # 5. Check pressure anomaly
    if progress.pressure is not None and not math.isnan(progress.pressure):
        press_min, press_max = config.pressure_range
        if progress.pressure < press_min or progress.pressure > press_max:
            anomalies.append(
                Anomaly(
                    type="TEMP_PRESSURE_ANOMALY",
                    severity="WARNING",
                    message=f"Pressure out of range: {progress.pressure:.2f} bar (expected {press_min}-{press_max} bar)",
                    timestamp=current_time,
                    details={"value": progress.pressure, "range": config.pressure_range},
                )
            )

    return anomalies


__all__ = [
    "MDProgress",
    "parse_output_file",
    "calculate_speed",
    "estimate_eta",
    "Anomaly",
    "AnomalyConfig",
    "detect_anomalies",
]
