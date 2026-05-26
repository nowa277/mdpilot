"""Professional PDB cleaning tool with format validation.

Ensures cleaned PDB files meet professional standards:
- Only ATOM/HETATM/TER/END lines
- No CONECT, REMARK, CRYST1, or other header lines
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from mdpilot.tools.decorator import tool


def validate_and_fix_pdb(pdb_path: Path) -> dict[str, int]:
    """Validate PDB format and fix if needed.

    Args:
        pdb_path: Path to PDB file to validate/fix

    Returns:
        Dictionary with line counts before and after fixing
    """
    content = pdb_path.read_text()
    lines = content.splitlines()

    # Count problematic lines
    conect_count = sum(1 for line in lines if line.startswith("CONECT"))
    remark_count = sum(1 for line in lines if line.startswith("REMARK"))
    cryst1_count = sum(1 for line in lines if line.startswith("CRYST1"))
    other_count = sum(
        1 for line in lines
        if line.strip() and not line.startswith(("ATOM", "HETATM", "TER", "END", "CONECT", "REMARK", "CRYST1"))
    )

    total_problematic = conect_count + remark_count + cryst1_count + other_count

    if total_problematic > 0:
        # Fix: keep only ATOM, HETATM, TER, and END lines
        filtered_lines = [
            line for line in lines
            if line.startswith(("ATOM", "HETATM", "TER", "END"))
        ]
        pdb_path.write_text("\n".join(filtered_lines) + "\n")

        return {
            "removed_conect": conect_count,
            "removed_remark": remark_count,
            "removed_cryst1": cryst1_count,
            "removed_other": other_count,
            "total_removed": total_problematic,
            "fixed": True,
        }

    return {
        "removed_conect": 0,
        "removed_remark": 0,
        "removed_cryst1": 0,
        "removed_other": 0,
        "total_removed": 0,
        "fixed": False,
    }


@tool(
    category="amber",
    name="clean_pdb_professional",
    description=(
        "Clean PDB file to professional standards using pdb4amber, "
        "then validate and ensure only ATOM/HETATM lines remain. "
        "Automatically removes CONECT, REMARK, CRYST1, and other header lines."
    ),
)
def clean_pdb_professional(
    input_pdb: str,
    output: str | None = None,
    remove_hydrogens: bool = False,
    remove_water: bool = False,
    protein_only: bool = False,
    workdir: str | None = None,
) -> str:
    """Clean PDB file to professional standards.

    This tool:
    1. Runs pdb4amber with --no-conect and --noter flags
    2. Validates the output format
    3. If validation fails, uses sed to remove problematic lines
    4. Reports what was cleaned

    Args:
        input_pdb: Path to input PDB file.
        output: Output PDB file name. Defaults to input_name_clean.pdb.
        remove_hydrogens: Remove all hydrogen atoms.
        remove_water: Remove all water molecules.
        protein_only: Keep only protein residues.
        workdir: Working directory. Defaults to input file directory.

    Returns:
        Cleaning report with statistics.
    """
    import os
    import shutil

    # Find pdb4amber
    pdb4amber_exe = shutil.which("pdb4amber")
    if not pdb4amber_exe:
        amber_home = os.environ.get("AMBERHOME", "")
        if amber_home:
            candidate = Path(amber_home) / "bin" / "pdb4amber"
            if candidate.exists():
                pdb4amber_exe = str(candidate)
        if not pdb4amber_exe:
            return "Error: pdb4amber not found. Set AMBERHOME or add to PATH."

    # Resolve paths
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

    # Build pdb4amber command
    cmd = [
        pdb4amber_exe,
        "-i", str(input_path),
        "-o", str(output_path),
        "--no-conect",  # Remove CONECT records
        "--noter",      # Remove REMARK records
    ]

    if remove_hydrogens:
        cmd.append("-y")
    if remove_water:
        cmd.append("-d")
    if protein_only:
        cmd.append("-p")

    # Run pdb4amber
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(workdir_path),
        )

        output_parts = []

        # Check if output was created
        if not output_path.exists():
            return f"Error: pdb4amber failed to create output file\n{result.stderr}"

        # Validate and fix format
        validation = validate_and_fix_pdb(output_path)

        # Count final lines
        content = output_path.read_text()
        lines = content.splitlines()
        atom_count = sum(1 for line in lines if line.startswith("ATOM"))
        hetatm_count = sum(1 for line in lines if line.startswith("HETATM"))
        ter_count = sum(1 for line in lines if line.startswith("TER"))

        # Build report
        output_parts.append("✅ PDB cleaning completed successfully")
        output_parts.append(f"\nInput: {input_path}")
        output_parts.append(f"Output: {output_path}")
        output_parts.append(f"\nFinal structure:")
        output_parts.append(f"  - ATOM lines: {atom_count}")
        output_parts.append(f"  - HETATM lines: {hetatm_count}")
        output_parts.append(f"  - TER lines: {ter_count}")

        if validation["fixed"]:
            output_parts.append(f"\n⚠️  Format validation and cleanup:")
            output_parts.append(f"  - Removed CONECT: {validation['removed_conect']}")
            output_parts.append(f"  - Removed REMARK: {validation['removed_remark']}")
            output_parts.append(f"  - Removed CRYST1: {validation['removed_cryst1']}")
            output_parts.append(f"  - Removed other headers: {validation['removed_other']}")
            output_parts.append(f"  - Total lines removed: {validation['total_removed']}")
        else:
            output_parts.append("\n✅ Format validation: PASSED (no cleanup needed)")

        output_parts.append(f"\n📄 File size: {output_path.stat().st_size / 1024:.1f} KB")
        output_parts.append("\n✨ Output file contains ONLY ATOM/HETATM/TER/END lines")

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return "Error: pdb4amber timed out after 120s"
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"
