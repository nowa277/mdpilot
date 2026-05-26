"""sander tool — run MD simulations with sander.

Wraps the sander (and optionally pmemd) executable for energy minimization,
heating, equilibration, and production MD runs.

Supports real-time progress feedback via optional callback.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from mdpilot.tools.decorator import tool


# Regex patterns for sander output parsing
_NSTEP_RE = re.compile(r"^\s*NSTEP\s*=")
_ENERGY_RE = re.compile(r"Etot\s*=")


def _parse_energy_line(line: str) -> dict[str, str] | None:
    """Extract key-value pairs from a sander energy output line."""
    if "Etot" not in line:
        return None
    # Typical format: "   NSTEP =    100   TIME(PS) =      20.000  Temp  =   300.12 ..."
    # or: "Etot   =    -12345.6789  EPtot      =    -23456.7890 ..."
    parts = {}
    for m in re.finditer(r"(\w+)\s*=\s*([-\d.eE+]+)", line):
        parts[m.group(1)] = m.group(2)
    return parts if parts else None


@tool(
    category="amber",
    name="sander",
    exclude=["progress_callback"],
    description=(
        "Run sander/pmemd for MD simulation: energy minimization, heating, "
        "equilibration, or production dynamics. Accepts a sander input configuration "
        "as a multiline string. Automatically selects pmemd if available. "
        "Supports optional progress_callback for real-time NSTEP/Etot updates."
    ),
)
def sander_run(
    input_config: str,
    prmtop: str,
    inpcrd: str,
    output: str = "md.out",
    trajectory: str | None = None,
    use_pmemd: bool = False,
    nproc: int = 1,
    workdir: str | None = None,
    timeout: int = 3600,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    """Run sander or pmemd for molecular dynamics simulation.

    Args:
        input_config: Multiline sander input configuration (control variables).
        prmtop: Path to topology file (prmtop).
        inpcrd: Path to coordinate file (inpcrd/restart).
        output: Output file name.
        trajectory: Trajectory output file name (mdcrd). None skips traj output.
        use_pmemd: Try to use pmemd instead of sander.
        nproc: Number of MPI processes (only for pmemd.MPI).
        workdir: Working directory. Defaults to current directory.
        timeout: Maximum execution time in seconds (default 1 hour).
        progress_callback: Optional callable receiving dicts with keys:
            - "nstep": current step number
            - "energy": dict of energy components
            - "raw_line": the raw output line
            Called in real-time as sander produces output.

    Returns:
        sander/pmemd output summary, or error message.
    """
    # Select executable
    exe = None
    if use_pmemd:
        for candidate_name in ("pmemd.cuda.MPI", "pmemd.cuda", "pmemd.MPI", "pmemd"):
            found = shutil.which(candidate_name)
            if found:
                exe = found
                break

    if exe is None:
        exe = shutil.which("sander")
        if not exe:
            amber_home = os.environ.get("AMBERHOME", "")
            if amber_home:
                candidate = Path(amber_home) / "bin" / "sander"
                if candidate.exists():
                    exe = str(candidate)
            if not exe:
                return "Error: sander/pmemd not found. Set AMBERHOME or add to PATH."

    use_temp = workdir is None
    if use_temp:
        workdir_path = Path(tempfile.mkdtemp(prefix="sander_"))
    else:
        workdir_path = Path(workdir)
        workdir_path.mkdir(parents=True, exist_ok=True)

    # Resolve paths
    prmtop_path = Path(prmtop)
    if not prmtop_path.is_absolute():
        prmtop_path = workdir_path / prmtop
    inpcrd_path = Path(inpcrd)
    if not inpcrd_path.is_absolute():
        inpcrd_path = workdir_path / inpcrd

    if not prmtop_path.exists():
        return f"Error: prmtop not found: {prmtop_path}"
    if not inpcrd_path.exists():
        return f"Error: inpcrd not found: {inpcrd_path}"

    # Write input file
    input_file = workdir_path / "sander.in"
    input_file.write_text(input_config)

    output_path = workdir_path / output
    traj_path = workdir_path / trajectory if trajectory else None

    # Build command
    is_mpi = nproc > 1 and "MPI" in (exe or "")
    cmd = []
    if is_mpi:
        cmd.extend(["mpirun", "-np", str(nproc)])
    cmd.append(exe)

    cmd.extend(["-O"])  # overwrite output
    cmd.extend(["-i", str(input_file)])
    cmd.extend(["-o", str(output_path)])
    cmd.extend(["-p", str(prmtop_path)])
    cmd.extend(["-c", str(inpcrd_path)])
    if traj_path:
        cmd.extend(["-x", str(traj_path)])
    restart_path = workdir_path / "md.rst"
    cmd.extend(["-r", str(restart_path)])
    info_path = workdir_path / "md.info"
    cmd.extend(["-inf", str(info_path)])

    env = os.environ.copy()

    # ---- Run with Popen for streaming output ----
    timed_out = False

    def _timeout_kill(proc: subprocess.Popen) -> None:
        nonlocal timed_out
        timed_out = True
        proc.kill()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(workdir_path),
            env=env,
        )
    except Exception as exc:
        return f"Error starting sander: {type(exc).__name__}: {exc}"

    # Set up timeout timer
    timer = threading.Timer(timeout, _timeout_kill, args=[proc])
    timer.daemon = True
    timer.start()

    # Stream stdout line-by-line
    last_nstep = 0
    last_energy: dict[str, str] = {}

    if proc.stdout is not None:
        try:
            for line in proc.stdout:
                stripped = line.strip()

                # Parse NSTEP progress lines
                if _NSTEP_RE.match(stripped):
                    nstep_match = re.search(r"NSTEP\s*=\s*(\d+)", stripped)
                    if nstep_match:
                        last_nstep = int(nstep_match.group(1))

                    energy_parts = _parse_energy_line(stripped)
                    if energy_parts:
                        last_energy = energy_parts

                    if progress_callback:
                        progress_callback({
                            "nstep": last_nstep,
                            "energy": last_energy,
                            "raw_line": stripped,
                        })

                # Also catch standalone energy lines
                elif _ENERGY_RE.search(stripped):
                    energy_parts = _parse_energy_line(stripped)
                    if energy_parts:
                        last_energy.update(energy_parts)
                        if progress_callback:
                            progress_callback({
                                "nstep": last_nstep,
                                "energy": last_energy,
                                "raw_line": stripped,
                            })
        except Exception:
            pass
        finally:
            proc.stdout.close()

    # Wait for process to finish
    returncode = proc.wait()
    timer.cancel()

    if timed_out:
        return f"Error: sander/pmemd timed out after {timeout}s"

    # ---- Parse output ----
    output_parts = []

    if output_path.exists():
        content = output_path.read_text()
        lines = content.splitlines()

        # Extract key info: last energy line
        energy_lines = [l for l in lines if "Etot" in l or "EPtot" in l]
        if energy_lines:
            output_parts.append("[final energy]")
            output_parts.append(energy_lines[-1].strip())

        # Check for completion
        completed = any("STOP" in l for l in lines[-10:])
        if completed:
            output_parts.append("\n[status: completed]")
        else:
            output_parts.append(f"\n[status: may be incomplete (rc={returncode})]")

        # NSTEP info
        nstep_lines = [l for l in lines if l.strip().startswith("NSTEP")]
        if nstep_lines:
            output_parts.append(f"[{nstep_lines[-1].strip()}]")
    else:
        stderr_output = ""
        if proc.stderr:
            try:
                stderr_output = proc.stderr.read()
            except Exception:
                pass
        if stderr_output:
            output_parts.append(f"[stderr]\n{stderr_output[-2000:]}")

    if last_nstep:
        output_parts.append(f"\n[last nstep: {last_nstep}]")
    if last_energy:
        key_energies = {k: v for k, v in last_energy.items()
                        if k in ("Etot", "EPtot", "Temp", "Press")}
        if key_energies:
            output_parts.append(f"[final energies: {key_energies}]")

    if traj_path and traj_path.exists():
        size_mb = traj_path.stat().st_size / (1024 * 1024)
        output_parts.append(f"\n[trajectory: {traj_path} ({size_mb:.1f} MB)]")

    if restart_path.exists():
        output_parts.append(f"[restart: {restart_path}]")

    if use_temp:
        output_parts.append(f"\n[workdir: {workdir_path}]")

    return "\n".join(output_parts) if output_parts else "(no output)"
