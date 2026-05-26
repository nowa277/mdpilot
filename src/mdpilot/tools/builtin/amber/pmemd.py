"""pmemd.cuda tool for GPU-accelerated molecular dynamics simulations.

This module provides a wrapper for the pmemd.cuda executable with automatic
GPU selection, real-time progress monitoring, and comprehensive error handling.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from mdpilot.tools.builtin.amber.gpu_selector import (
    select_optimal_gpu,
    validate_gpu,
)
from mdpilot.tools.decorator import tool

logger = logging.getLogger(__name__)

# Regex patterns for pmemd.cuda output parsing
_NSTEP_RE = re.compile(r"^\s*NSTEP\s*=\s*(\d+)")
_TIME_RE = re.compile(r"TIME\(PS\)\s*=\s*([\d.]+)")
_TEMP_RE = re.compile(r"TEMP\(K\)\s*=\s*([\d.]+)")
_ENERGY_RE = re.compile(r"Etot\s*=\s*([-\d.eE+]+)")
_NSDAY_RE = re.compile(r"ns/day\s*=\s*([\d.]+)")


def _parse_progress_line(line: str) -> dict[str, Any] | None:
    """Parse a progress line from pmemd.cuda output.

    Args:
        line: Output line from pmemd.cuda

    Returns:
        Dictionary with parsed values or None if not a progress line
    """
    result: dict[str, Any] = {}

    # Check for NSTEP line
    nstep_match = _NSTEP_RE.search(line)
    if nstep_match:
        result["step"] = int(nstep_match.group(1))

        # Extract other values from the same line
        time_match = _TIME_RE.search(line)
        if time_match:
            result["time_ps"] = float(time_match.group(1))

        temp_match = _TEMP_RE.search(line)
        if temp_match:
            result["temperature"] = float(temp_match.group(1))

    # Check for energy line
    energy_match = _ENERGY_RE.search(line)
    if energy_match:
        try:
            result["energy"] = float(energy_match.group(1))
        except ValueError:
            # Handle asterisks (energy explosion)
            result["energy"] = None

    return result if result else None


def _parse_timing_line(line: str) -> float | None:
    """Parse ns/day from timing output.

    Args:
        line: Output line containing timing information

    Returns:
        ns/day value or None if not found
    """
    match = _NSDAY_RE.search(line)
    if match:
        return float(match.group(1))
    return None


@tool(
    category="amber",
    name="pmemd_cuda",
    description=(
        "Run GPU-accelerated molecular dynamics simulation with pmemd.cuda. "
        "Automatically selects optimal GPU or uses specified GPU ID. "
        "Supports real-time progress monitoring and comprehensive error handling."
    ),
)
def pmemd_cuda(
    input_file: str,
    output_file: str,
    topology_file: str,
    coordinate_file: str,
    restart_file: str | None = None,
    trajectory_file: str | None = None,
    reference_file: str | None = None,
    mdinfo_file: str | None = None,
    gpu_id: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Run AMBER pmemd.cuda molecular dynamics simulation.

    Args:
        input_file: MD input file (.in)
        output_file: Output file (.out)
        topology_file: Topology file (.prmtop)
        coordinate_file: Input coordinate file (.inpcrd or .rst7)
        restart_file: Output restart file (.rst7)
        trajectory_file: Output trajectory file (.nc)
        reference_file: Reference coordinates for restraints
        mdinfo_file: Runtime info file (default: mdinfo)
        gpu_id: GPU ID to use (None = auto-select)
        progress_callback: Callback function for progress updates
        timeout: Maximum execution time in seconds (None = no timeout)

    Returns:
        dict with keys:
            - success: bool
            - return_code: int
            - final_step: int | None
            - final_energy: float | None
            - final_temperature: float | None
            - average_ns_per_day: float | None
            - stdout: str
            - stderr: str
            - error: str (only if success=False)
    """
    logger.debug("Starting pmemd.cuda execution")

    # GPU selection
    if gpu_id is None:
        gpu_id = select_optimal_gpu()
        logger.debug("Auto-selected GPU %d", gpu_id)
    else:
        if not validate_gpu(gpu_id):
            error_msg = f"GPU {gpu_id} not available"
            logger.error(error_msg)
            return {
                "success": False,
                "return_code": -1,
                "final_step": None,
                "final_energy": None,
                "final_temperature": None,
                "average_ns_per_day": None,
                "stdout": "",
                "stderr": "",
                "error": error_msg,
            }
        logger.debug("Using specified GPU %d", gpu_id)

    # Validate input files
    input_path = Path(input_file)
    topology_path = Path(topology_file)
    coordinate_path = Path(coordinate_file)

    for path, name in [
        (input_path, "input file"),
        (topology_path, "topology file"),
        (coordinate_path, "coordinate file"),
    ]:
        if not path.exists():
            error_msg = f"Missing {name}: {path}"
            logger.error(error_msg)
            return {
                "success": False,
                "return_code": -1,
                "final_step": None,
                "final_energy": None,
                "final_temperature": None,
                "average_ns_per_day": None,
                "stdout": "",
                "stderr": "",
                "error": error_msg,
            }

    # Build command
    cmd = ["pmemd.cuda", "-O"]
    cmd.extend(["-i", str(input_path)])
    cmd.extend(["-o", str(output_file)])
    cmd.extend(["-p", str(topology_path)])
    cmd.extend(["-c", str(coordinate_path)])

    if restart_file:
        cmd.extend(["-r", str(restart_file)])
    if trajectory_file:
        cmd.extend(["-x", str(trajectory_file)])
    if reference_file:
        cmd.extend(["-ref", str(reference_file)])
    if mdinfo_file:
        cmd.extend(["-inf", str(mdinfo_file)])

    logger.debug("Command: %s", " ".join(cmd))

    # Set up environment with GPU selection
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    # Execute pmemd.cuda
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except FileNotFoundError as e:
        error_msg = f"pmemd.cuda not found: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "return_code": -1,
            "final_step": None,
            "final_energy": None,
            "final_temperature": None,
            "average_ns_per_day": None,
            "stdout": "",
            "stderr": "",
            "error": error_msg,
        }
    except Exception as e:
        error_msg = f"Failed to start pmemd.cuda: {type(e).__name__}: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "return_code": -1,
            "final_step": None,
            "final_energy": None,
            "final_temperature": None,
            "average_ns_per_day": None,
            "stdout": "",
            "stderr": "",
            "error": error_msg,
        }

    # Stream output and parse progress
    stdout_lines = []
    stderr_lines = []
    last_step = None
    last_energy = None
    last_temperature = None
    ns_per_day = None

    try:
        # Read stdout
        if proc.stdout:
            for line in proc.stdout:
                stdout_lines.append(line)
                stripped = line.strip()

                # Parse progress
                progress = _parse_progress_line(stripped)
                if progress:
                    if "step" in progress:
                        last_step = progress["step"]
                    if "energy" in progress:
                        last_energy = progress["energy"]
                    if "temperature" in progress:
                        last_temperature = progress["temperature"]

                    # Call progress callback
                    if progress_callback:
                        progress_callback(progress)

                # Parse timing
                timing = _parse_timing_line(stripped)
                if timing is not None:
                    ns_per_day = timing

        # Wait for process to complete
        try:
            if timeout:
                proc.wait(timeout=timeout)
            else:
                proc.wait()
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            error_msg = f"pmemd.cuda timed out after {timeout} seconds"
            logger.error(error_msg)
            return {
                "success": False,
                "return_code": -1,
                "final_step": last_step,
                "final_energy": last_energy,
                "final_temperature": last_temperature,
                "average_ns_per_day": ns_per_day,
                "stdout": "".join(stdout_lines),
                "stderr": "",
                "error": error_msg,
            }

        # Read stderr
        if proc.stderr:
            stderr_lines = list(proc.stderr)

        return_code = proc.returncode

    except Exception as e:
        error_msg = f"Error during execution: {type(e).__name__}: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "return_code": -1,
            "final_step": last_step,
            "final_energy": last_energy,
            "final_temperature": last_temperature,
            "average_ns_per_day": ns_per_day,
            "stdout": "".join(stdout_lines),
            "stderr": "".join(stderr_lines),
            "error": error_msg,
        }

    # Build result
    stdout_text = "".join(stdout_lines)
    stderr_text = "".join(stderr_lines)

    success = return_code == 0

    result = {
        "success": success,
        "return_code": return_code,
        "final_step": last_step,
        "final_energy": last_energy,
        "final_temperature": last_temperature,
        "average_ns_per_day": ns_per_day,
        "stdout": stdout_text,
        "stderr": stderr_text,
    }

    if not success:
        result["error"] = f"pmemd.cuda failed with return code {return_code}"
        logger.error("pmemd.cuda failed: rc=%d", return_code)
    else:
        logger.info(
            "pmemd.cuda completed successfully: step=%s, energy=%s, ns/day=%s",
            last_step,
            last_energy,
            ns_per_day,
        )

    return result
