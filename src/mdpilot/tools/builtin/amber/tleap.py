"""tLEaP tool — build AMBER topology and coordinate files.

Wraps the tleap executable to run input scripts for system preparation:
loading force fields, adding ions, solvation, generating prmtop/inpcrd.
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
    name="tleap",
    description=(
        "Run tLEaP to build AMBER topology (prmtop) and coordinate (inpcrd) files. "
        "Accepts a tLEaP input script as a multiline string."
    ),
)
def tleap_run(
    input_script: str,
    workdir: str | None = None,
    timeout: int = 300,
) -> str:
    """Execute a tLEaP input script.

    Args:
        input_script: Multiline tLEaP commands (e.g. 'source leaprc.protein.ff14SB\\n...').
        workdir: Working directory for output files. Defaults to a temp directory.
        timeout: Maximum execution time in seconds.

    Returns:
        tLEaP stdout + stderr, or error message.
    """
    tleap_exe = shutil.which("tleap")
    if not tleap_exe:
        # Try AMBERHOME/bin
        amber_home = os.environ.get("AMBERHOME", "")
        if amber_home:
            candidate = Path(amber_home) / "bin" / "tleap"
            if candidate.exists():
                tleap_exe = str(candidate)
        if not tleap_exe:
            return "Error: tleap not found. Set AMBERHOME or add tleap to PATH."

    use_temp = workdir is None
    if use_temp:
        workdir_path = Path(tempfile.mkdtemp(prefix="tleap_"))
    else:
        workdir_path = Path(workdir)
        workdir_path.mkdir(parents=True, exist_ok=True)

    # Write input script to file
    input_file = workdir_path / "tleap.in"
    input_file.write_text(input_script)

    try:
        result = subprocess.run(
            [tleap_exe, "-f", str(input_file)],
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

        # Check for common tLEaP errors in output
        combined = result.stdout + result.stderr
        errors_found = []
        for line in combined.splitlines():
            lower = line.lower().strip()
            if lower.startswith("error:") or "could not" in lower or "not found" in lower:
                if "adding" not in lower:  # filter false positives
                    errors_found.append(line.strip())

        if errors_found:
            output_parts.append(f"\n[tLEaP warnings/errors]\n" + "\n".join(errors_found))

        if use_temp:
            output_parts.append(f"\n[workdir: {workdir_path}]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: tLEaP timed out after {timeout}s"
    except Exception as exc:
        return f"Error running tLEaP: {type(exc).__name__}: {exc}"
