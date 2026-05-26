"""reduce tool — Add or remove hydrogens from PDB files.

Wraps reduce to add hydrogens, optimize hydrogen bond networks,
and determine HIS protonation states (HID/HIE/HIP).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from mdpilot.tools.decorator import tool


@tool(
    category="amber",
    name="reduce",
    description=(
        "Run reduce to add or remove hydrogens from PDB files, "
        "optimize hydrogen bond networks, and determine HIS protonation states."
    ),
)
def reduce_run(
    input_pdb: str,
    output: str | None = None,
    mode: str = "build",
    flip: bool = True,
    quiet: bool = False,
    workdir: str | None = None,
    timeout: int = 120,
) -> str:
    """Run reduce to process hydrogens in a PDB file.

    Args:
        input_pdb: Path to input PDB file.
        output: Output PDB file name. Defaults to input_name_H.pdb (build) or input_name_noH.pdb (trim).
        mode: Operation mode: 'build' (add H), 'trim' (remove H).
        flip: Optimize H-bond network by flipping ASN/GLN/HIS.
        quiet: Reduce output verbosity.
        workdir: Working directory. Defaults to input file directory.
        timeout: Maximum execution time in seconds.

    Returns:
        reduce stdout/stderr, or error message.
    """
    reduce_exe = shutil.which("reduce")
    if not reduce_exe:
        amber_home = os.environ.get("AMBERHOME", "")
        if amber_home:
            candidate = Path(amber_home) / "bin" / "reduce"
            if candidate.exists():
                reduce_exe = str(candidate)
        if not reduce_exe:
            return "Error: reduce not found. Set AMBERHOME or add to PATH."

    # Resolve and validate input path (prevent command injection)
    input_path = Path(input_pdb).resolve()
    if not input_path.exists():
        return f"Error: input PDB not found: {input_path}"
    if not input_path.is_file():
        return f"Error: input path is not a file: {input_path}"

    if output is None:
        suffix = "_H.pdb" if mode == "build" else "_noH.pdb"
        output = input_path.stem + suffix

    if workdir is None:
        workdir_path = input_path.parent
    else:
        workdir_path = Path(workdir).resolve()
        workdir_path.mkdir(parents=True, exist_ok=True)

    output_path = (workdir_path / output).resolve()

    # Validate output path (prevent path traversal)
    try:
        output_path.relative_to(workdir_path)
    except ValueError:
        return f"Error: output path escapes working directory: {output_path}"

    # Build command
    cmd = [reduce_exe]

    if mode == "build":
        cmd.append("-build")
    elif mode == "trim":
        cmd.append("-trim")
    else:
        return f"Error: invalid mode '{mode}'. Use 'build' or 'trim'."

    if not flip:
        cmd.append("-noflip")

    if quiet:
        cmd.append("-quiet")

    cmd.append(str(input_path))

    # Build minimal environment (prevent environment pollution)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "AMBERHOME": os.environ.get("AMBERHOME", ""),
    }

    try:
        # reduce writes to stdout, so we redirect to output file
        # Use try-finally to ensure file handle cleanup
        outfile = None
        try:
            outfile = open(output_path, "w")
            result = subprocess.run(
                cmd,
                stdout=outfile,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                cwd=str(workdir_path),
                env=env,
            )
        finally:
            if outfile:
                outfile.close()

        output_parts = []

        # reduce writes informational messages to stderr
        if result.stderr:
            output_parts.append(result.stderr)

        if output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            output_parts.append(f"\n[output: {output_path} ({size_kb:.1f} KB)]")

            # Quick summary: count atoms and hydrogens
            content = output_path.read_text()
            lines = content.splitlines()
            atom_count = sum(1 for line in lines if line.startswith("ATOM"))
            het_count = sum(1 for line in lines if line.startswith("HETATM"))

            # Count hydrogens (element column or atom name starting with H)
            h_count = 0
            for line in lines:
                if line.startswith(("ATOM", "HETATM")):
                    # Element is at columns 76-77 (0-indexed: 76:78)
                    if len(line) >= 78:
                        element = line[76:78].strip()
                        if element == "H":
                            h_count += 1
                    # Fallback: check atom name (columns 12-16)
                    elif len(line) >= 16:
                        atom_name = line[12:16].strip()
                        if atom_name.startswith("H"):
                            h_count += 1

            output_parts.append(f"[atoms: {atom_count}, hetatm: {het_count}, hydrogens: {h_count}]")
        else:
            output_parts.append("\n[warning: output file not created]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: reduce timed out after {timeout}s"
    except Exception as exc:
        return f"Error running reduce: {type(exc).__name__}: {exc}"
