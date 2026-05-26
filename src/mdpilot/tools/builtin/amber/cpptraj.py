"""cpptraj tool — trajectory analysis and processing.

Wraps the cpptraj executable for RMSD calculation, distance/angle measurements,
clustering, PCA, hydrogen bond analysis, and more.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from mdpilot.tools.decorator import tool


@tool(
    category="amber",
    name="cpptraj",
    description=(
        "Run cpptraj for trajectory analysis: RMSD, RMSF, distances, angles, "
        "dihedrals, hydrogen bonds, clustering, PCA, and more. "
        "Accepts a cpptraj input script as a multiline string."
    ),
)
def cpptraj_run(
    input_script: str,
    workdir: str | None = None,
    timeout: int = 600,
) -> str:
    """Execute a cpptraj input script.

    Args:
        input_script: Multiline cpptraj commands (e.g. 'trajin md.nc\\nrms first\\n...').
        workdir: Working directory for input/output files. Defaults to current directory.
        timeout: Maximum execution time in seconds.

    Returns:
        cpptraj stdout + stderr, or error message.
    """
    cpptraj_exe = shutil.which("cpptraj")
    if not cpptraj_exe:
        amber_home = os.environ.get("AMBERHOME", "")
        if amber_home:
            candidate = Path(amber_home) / "bin" / "cpptraj"
            if candidate.exists():
                cpptraj_exe = str(candidate)
        if not cpptraj_exe:
            return "Error: cpptraj not found. Set AMBERHOME or add cpptraj to PATH."

    use_temp = workdir is None
    if use_temp:
        workdir_path = Path(tempfile.mkdtemp(prefix="cpptraj_"))
    else:
        workdir_path = Path(workdir)
        workdir_path.mkdir(parents=True, exist_ok=True)

    input_file = workdir_path / "cpptraj.in"
    input_file.write_text(input_script)

    try:
        result = subprocess.run(
            [cpptraj_exe, str(input_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workdir_path),
            env=os.environ.copy(),
        )

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")

        # Check for errors
        combined = result.stdout + result.stderr
        error_lines = [
            line.strip() for line in combined.splitlines()
            if "error" in line.lower() and "warning" not in line.lower()
        ]
        if error_lines:
            output_parts.append(f"\n[cpptraj errors]\n" + "\n".join(error_lines[:10]))

        if use_temp:
            output_parts.append(f"\n[workdir: {workdir_path}]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: cpptraj timed out after {timeout}s"
    except Exception as exc:
        return f"Error running cpptraj: {type(exc).__name__}: {exc}"
