"""pdb4amber tool — PDB file preparation for AMBER.

Wraps pdb4amber to clean and prepare PDB files: renumber residues,
add hydrogens, fix missing atoms, convert to AMBER-compatible format.
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
    name="pdb4amber",
    description=(
        "Run pdb4amber to prepare PDB files for AMBER simulations: "
        "renumber residues, identify ter lines, handle disulfide bonds, "
        "and generate cleaned PDB output."
    ),
)
def pdb4amber_run(
    input_pdb: str,
    output: str | None = None,
    reduce: bool = True,
    add_missing_atoms: bool = False,
    no_conect: bool = False,
    no_remarks: bool = False,
    strip_headers: bool = False,
    workdir: str | None = None,
    timeout: int = 120,
) -> str:
    """Run pdb4amber to prepare a PDB file.

    Args:
        input_pdb: Path to input PDB file.
        output: Output PDB file name. Defaults to input_name_clean.pdb.
        reduce: Run reduce to add hydrogens.
        add_missing_atoms: Add missing heavy atoms.
        no_conect: Remove CONECT records from output.
        no_remarks: Remove REMARK records from output.
        strip_headers: Remove all header lines (CRYST1, REMARK, etc), keeping only ATOM/HETATM.
        workdir: Working directory. Defaults to input file directory.
        timeout: Maximum execution time in seconds.

    Returns:
        pdb4amber stdout, or error message.
    """
    pdb4amber_exe = shutil.which("pdb4amber")
    if not pdb4amber_exe:
        amber_home = os.environ.get("AMBERHOME", "")
        if amber_home:
            candidate = Path(amber_home) / "bin" / "pdb4amber"
            if candidate.exists():
                pdb4amber_exe = str(candidate)
        if not pdb4amber_exe:
            return "Error: pdb4amber not found. Set AMBERHOME or add to PATH."

    # Resolve input path
    input_path = Path(input_pdb)
    if not input_path.exists():
        return f"Error: input PDB not found: {input_path}"

    if output is None:
        output = input_path.stem + "_clean.pdb"

    if workdir is None:
        workdir_path = input_path.parent
    else:
        workdir_path = Path(workdir)
        workdir_path.mkdir(parents=True, exist_ok=True)

    output_path = workdir_path / output

    cmd = [
        pdb4amber_exe,
        "-i", str(input_path),
        "-o", str(output_path),
    ]
    if reduce:
        cmd.append("--reduce")
    if add_missing_atoms:
        cmd.append("--add-missing-atoms")
    if no_conect:
        cmd.append("--no-conect")
    if no_remarks:
        cmd.append("--noter")

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

        if output_path.exists():
            # Post-process: strip headers if requested
            if strip_headers:
                content = output_path.read_text()
                lines = content.splitlines()
                # Keep only ATOM, HETATM, TER, and END lines
                filtered_lines = [
                    line for line in lines
                    if line.startswith(("ATOM", "HETATM", "TER", "END"))
                ]
                output_path.write_text("\n".join(filtered_lines) + "\n")
                output_parts.append("[post-processing: removed all header lines]")

            size_kb = output_path.stat().st_size / 1024
            output_parts.append(f"\n[output: {output_path} ({size_kb:.1f} KB)]")

            # Quick summary: count ATOM lines
            content = output_path.read_text()
            atom_count = sum(1 for line in content.splitlines() if line.startswith("ATOM"))
            het_count = sum(1 for line in content.splitlines() if line.startswith("HETATM"))
            ter_count = sum(1 for line in content.splitlines() if line.startswith("TER"))
            output_parts.append(f"[atoms: {atom_count}, hetatm: {het_count}, TER: {ter_count}]")
        else:
            output_parts.append("\n[warning: output file not created]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: pdb4amber timed out after {timeout}s"
    except Exception as exc:
        return f"Error running pdb4amber: {type(exc).__name__}: {exc}"
