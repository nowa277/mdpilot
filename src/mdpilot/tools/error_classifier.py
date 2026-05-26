"""AMBER error classifier — pattern-matches sander/tleap/cpptraj errors.

Maps common AMBER failure messages to structured error categories with
actionable suggestions, so the LLM can self-correct without blind retries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ClassifiedError:
    """A structured error with category, code, and fix suggestion."""

    code: str
    category: str
    message: str
    suggestion: str


# ------------------------------------------------------------------ #
# Pattern tables: (regex_pattern, code, category, suggestion)
# ------------------------------------------------------------------ #

_AMBER_PATTERNS: list[tuple[str, str, str, str]] = [
    # --- Missing files / force field ---
    (
        r"(?:could not open|cannot open|No such file).*leaprc",
        "MISSING_FF",
        "amber_config",
        "The force field leaprc file is missing. Check AMBERHOME or install the missing force field package.",
    ),
    (
        r"(?:could not open|cannot open|No such file|not found).*\.dat",
        "MISSING_PARAM",
        "amber_config",
        "A parameter data file (.dat) is missing. Ensure the AMBER force field is fully installed.",
    ),
    (
        r"(?:could not open|cannot open|file does not exist)",
        "MISSING_FILE",
        "missing_file",
        "A required input file was not found. Verify the file path and that the previous step produced it.",
    ),
    (
        r"Could not find ff.*parameters",
        "MISSING_FF_PARAMS",
        "amber_config",
        "Force field parameters not found. The residue name may not match any known force field. Consider using antechamber for custom residues.",
    ),

    # --- PDB format issues ---
    (
        r"(?:duplicate atom|Duplicate atom|atoms with the same name)",
        "PDB_DUPLICATE",
        "pdb_format",
        "Duplicate atom names detected. Use pdb4amber to clean the PDB file, or manually deduplicate atoms.",
    ),
    (
        r"(?:Atom names|duplicate atom|Unknown residue|FATAL).*residue",
        "PDB_RESIDUE",
        "pdb_format",
        "PDB has unknown or duplicate residue names. Run pdb4amber --dry --reduce first, or check for non-standard residues.",
    ),
    (
        r"(?:unknown residue|Unknown residue|FATAL: Residue)",
        "PDB_UNKNOWN_RES",
        "pdb_format",
        "Unknown residue in PDB. Either add the residue parameters (loadamberparams/frcmod) or use antechamber for non-standard molecules.",
    ),
    (
        r"(?:SEGINIT|segid|chain ID)",
        "PDB_CHAIN",
        "pdb_format",
        "PDB chain/segment issue. Use pdb4amber to normalize chain IDs before tLEaP.",
    ),
    (
        r"(?:altLoc|alternate location)",
        "PDB_ALTLOC",
        "pdb_format",
        "Alternate location atoms found. pdb4amber or PDBFixer can resolve this.",
    ),

    # --- Memory issues ---
    (
        r"(?:out of memory|Cannot allocate|MemoryError|Allocation would exceed)",
        "OOM",
        "memory",
        "System ran out of memory. Reduce system size, use a smaller water box, or increase swap space.",
    ),
    (
        r"(?:Segmentation fault|segfault)",
        "SEGFAULT",
        "memory",
        "Segmentation fault — likely memory corruption or incompatible binary. Try with sander instead of pmemd, or check CUDA compatibility.",
    ),

    # --- GPU / CUDA ---
    (
        r"(?:CUDA|cuda|gpu|GPU).*error",
        "CUDA_ERROR",
        "gpu",
        "CUDA error detected. Try running with sander (CPU) instead of pmemd.cuda, or check GPU driver compatibility.",
    ),
    (
        r"(?:could not initialize|init).*CUDA",
        "CUDA_INIT",
        "gpu",
        "Failed to initialize CUDA. Verify nvidia driver is installed and compatible with your CUDA version.",
    ),

    # --- sander numerical ---
    (
        r"(?:NAN|NaN|nan).*Etot",
        "NAN_ENERGY",
        "numerical",
        "Energy is NaN — the system likely has severe clashes or bad initial coordinates. Run more minimization steps or use a smaller timestep.",
    ),
    (
        r"(?:vlimit exceeded|VLIMIT)",
        "VLIMIT",
        "numerical",
        "Velocity limit exceeded — atoms moving too fast. Reduce timestep to 0.001 or re-minimize the structure.",
    ),
    (
        r"(?:shake|SHAKE).*(?:error|fail|converge)",
        "SHAKE_FAIL",
        "numerical",
        "SHAKE constraint failed. Reduce timestep (0.001), use ntc=1 instead of ntc=2, or re-minimize.",
    ),

    # --- Timeout ---
    (
        r"(?:timed out|timeout|TIMEOUT)",
        "TIMEOUT",
        "timeout",
        "Simulation timed out. Either increase the timeout setting or reduce nstlim for a shorter run.",
    ),

    # --- Topology / coordinate mismatch ---
    (
        r"(?:mismatch|different number).*atom",
        "TOPO_MISMATCH",
        "amber_config",
        "Topology and coordinate file have different numbers of atoms. Ensure prmtop and inpcrd were generated from the same tLEaP run.",
    ),

    # --- Generic AMBER fatal ---
    (
        r"FATAL",
        "AMBER_FATAL",
        "unknown",
        "AMBER reported a FATAL error. Check the output file above the FATAL line for specific details.",
    ),
]


def classify_amber_error(error_text: str) -> ClassifiedError | None:
    """Classify an AMBER tool error into a structured error.

    Scans the error text against known AMBER error patterns and returns
    a ``ClassifiedError`` with category, code, and fix suggestion.
    Returns ``None`` if no pattern matches.
    """
    if not error_text:
        return None

    for pattern, code, category, suggestion in _AMBER_PATTERNS:
        if re.search(pattern, error_text, re.IGNORECASE):
            return ClassifiedError(
                code=code,
                category=category,
                message=error_text[:500],  # truncate to avoid context bloat
                suggestion=suggestion,
            )

    return None


def format_classified_error(error_text: str) -> tuple[str | None, str | None, str | None]:
    """Convenience: classify and return (error_code, error_category, suggestion).

    Returns (None, None, None) if no classification matched.
    """
    result = classify_amber_error(error_text)
    if result is None:
        return None, None, None
    return result.code, result.category, result.suggestion
