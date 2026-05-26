"""antechamber tool — small molecule parameterization.

Wraps antechamber for generating AMBER force field parameters for small molecules:
charge calculation (AM1-BCC, Gasteiger, etc.), atom type assignment, and
generating prepc/frcmod/mol2 files. Also wraps parmchk2 for missing parameters.
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
    name="antechamber",
    description=(
        "Run antechamber for small molecule parameterization: charge calculation, "
        "atom type assignment, format conversion. Generates prepc/mol2 files for "
        "use in tLEaP. Also supports parmchk2 for missing parameter generation."
    ),
)
def antechamber_run(
    input_file: str,
    input_format: str = "mol2",
    output_file: str = "output.mol2",
    output_format: str = "mol2",
    charge_method: str = "bcc",
    net_charge: int = 0,
    atom_type: str = "gaff2",
    run_parmchk: bool = True,
    workdir: str | None = None,
    timeout: int = 300,
) -> str:
    """Run antechamber to parameterize a small molecule.

    Args:
        input_file: Path to input molecule file (mol2, sdf, pdb, etc.).
        input_format: Input file format (mol2, sdf, pdb, smi, ac, etc.).
        output_file: Output file name.
        output_format: Output file format (mol2, prepc, frcmod, etc.).
        charge_method: Charge method: bcc (AM1-BCC), gas (Gasteiger), resp, cm1, cm2, mul.
        net_charge: Net molecular charge.
        atom_type: Atom type set: gaff2, gaff, amber.
        run_parmchk: Whether to also run parmchk2 to generate frcmod file.
        workdir: Working directory. Defaults to temp directory.
        timeout: Maximum execution time in seconds.

    Returns:
        antechamber stdout + parmchk2 output if run, or error message.
    """
    ante_exe = shutil.which("antechamber")
    parmchk_exe = shutil.which("parmchk2") if run_parmchk else None

    if not ante_exe:
        amber_home = os.environ.get("AMBERHOME", "")
        if amber_home:
            ante_candidate = Path(amber_home) / "bin" / "antechamber"
            if ante_candidate.exists():
                ante_exe = str(ante_candidate)
            if run_parmchk:
                pc_candidate = Path(amber_home) / "bin" / "parmchk2"
                if pc_candidate.exists():
                    parmchk_exe = str(pc_candidate)
        if not ante_exe:
            return "Error: antechamber not found. Set AMBERHOME or add to PATH."

    use_temp = workdir is None
    if use_temp:
        workdir_path = Path(tempfile.mkdtemp(prefix="antechamber_"))
    else:
        workdir_path = Path(workdir)
        workdir_path.mkdir(parents=True, exist_ok=True)

    # Resolve input file path
    input_path = Path(input_file)
    if not input_path.is_absolute():
        input_path = workdir_path / input_file
    if not input_path.exists():
        return f"Error: input file not found: {input_path}"

    output_path = workdir_path / output_file

    # Build antechamber command
    cmd = [
        ante_exe,
        "-i", str(input_path),
        "-fi", input_format,
        "-o", str(output_path),
        "-fo", output_format,
        "-c", charge_method,
        "-nc", str(net_charge),
        "-at", atom_type,
    ]

    env = os.environ.copy()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workdir_path),
            env=env,
        )

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")

        # Check output file
        if output_path.exists():
            output_parts.append(f"\n[output: {output_path}]")
        else:
            output_parts.append("\n[warning: output file not created]")

        # Run parmchk2 if requested
        if run_parmchk and parmchk_exe:
            frcmod_path = workdir_path / "output.frcmod"
            pc_cmd = [
                parmchk_exe,
                "-i", str(output_path),
                "-f", output_format,
                "-o", str(frcmod_path),
            ]
            try:
                pc_result = subprocess.run(
                    pc_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(workdir_path),
                    env=env,
                )
                output_parts.append("\n[parmchk2]")
                if pc_result.stdout:
                    output_parts.append(pc_result.stdout)
                if pc_result.stderr:
                    output_parts.append(pc_result.stderr)
                if frcmod_path.exists():
                    output_parts.append(f"[frcmod: {frcmod_path}]")
            except subprocess.TimeoutExpired:
                output_parts.append("\n[parmchk2 timed out]")
            except Exception as exc:
                output_parts.append(f"\n[parmchk2 error: {exc}]")

        if use_temp:
            output_parts.append(f"\n[workdir: {workdir_path}]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: antechamber timed out after {timeout}s"
    except Exception as exc:
        return f"Error running antechamber: {type(exc).__name__}: {exc}"
