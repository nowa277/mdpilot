"""propka integration for pKa prediction and protonation state determination.

propka is a widely-used tool for predicting pKa values of ionizable residues
in proteins. This module provides a wrapper for propka3 and utilities for
parsing its output to determine optimal protonation states.

References:
- Olsson et al. (2011) J. Chem. Theory Comput. 7, 525-537
- Søndergaard et al. (2011) J. Chem. Theory Comput. 7, 2284-2295
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class ResiduePka:
    """pKa prediction for a single residue."""

    residue_name: str  # e.g., "HIS", "ASP", "GLU"
    residue_number: int
    chain_id: str
    pka: float
    model_pka: float  # Standard model pKa for this residue type
    buried: bool  # Whether residue is buried (affects pKa)
    metal_interaction: bool = False  # Whether residue interacts with metal ion

    def protonation_state(self, ph: float = 7.0) -> Literal["protonated", "deprotonated"]:
        """Determine protonation state at given pH.

        Args:
            ph: Target pH (default: 7.0)

        Returns:
            "protonated" if pKa > pH, "deprotonated" if pKa < pH
        """
        # Henderson-Hasselbalch: if pKa > pH, residue is protonated
        return "protonated" if self.pka > ph else "deprotonated"


@dataclass
class PropkaResult:
    """Complete propka analysis result."""

    pka_values: dict[tuple[str, int, str], ResiduePka]  # (resname, resnum, chain) -> ResiduePka
    summary: str  # Full propka output

    def get_residue(self, resname: str, resnum: int, chain: str = "A") -> ResiduePka | None:
        """Get pKa prediction for specific residue."""
        return self.pka_values.get((resname, resnum, chain))

    def get_his_residues(self) -> list[ResiduePka]:
        """Get all HIS residues."""
        return [pka for (resname, _, _), pka in self.pka_values.items() if resname == "HIS"]

    def get_asp_residues(self) -> list[ResiduePka]:
        """Get all ASP residues."""
        return [pka for (resname, _, _), pka in self.pka_values.items() if resname == "ASP"]

    def get_glu_residues(self) -> list[ResiduePka]:
        """Get all GLU residues."""
        return [pka for (resname, _, _), pka in self.pka_values.items() if resname == "GLU"]

    def get_lys_residues(self) -> list[ResiduePka]:
        """Get all LYS residues."""
        return [pka for (resname, _, _), pka in self.pka_values.items() if resname == "LYS"]


class PropkaWrapper:
    """Wrapper for propka3 command-line tool."""

    def __init__(self):
        """Initialize propka wrapper."""
        self.propka_path = shutil.which("propka3")
        if not self.propka_path:
            logger.warning("propka3 not found in PATH. Install with: pip install propka")

    def is_available(self) -> bool:
        """Check if propka3 is available."""
        return self.propka_path is not None

    def run(
        self,
        pdb_file: Path | str,
        ph: float = 7.0,
        output_dir: Path | str | None = None
    ) -> PropkaResult:
        """Run propka3 on PDB file.

        Note on propka pH parameter:
        The --pH flag affects how propka INTERPRETS protonation states in its output,
        but does NOT change the calculated pKa values themselves. pKa values are
        intrinsic properties of the residue environment and remain constant regardless
        of the pH parameter. The pH only affects the protonation_state() method output.

        Args:
            pdb_file: Path to PDB file
            ph: Target pH for protonation state calculation (default: 7.0)
            output_dir: Directory for output files (default: same as input)

        Returns:
            PropkaResult with pKa predictions

        Raises:
            RuntimeError: If propka3 is not available or execution fails
            FileNotFoundError: If PDB file does not exist
        """
        if not self.is_available():
            raise RuntimeError(
                "propka3 not found. Install with: pip install propka"
            )

        # Validate input
        pdb_file = Path(pdb_file).resolve()
        if not pdb_file.exists():
            raise FileNotFoundError(f"PDB file not found: {pdb_file}")
        if not pdb_file.is_file():
            raise ValueError(f"Path is not a file: {pdb_file}")

        # Set output directory
        if output_dir is None:
            output_dir = pdb_file.parent
        else:
            output_dir = Path(output_dir).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)

        # Run propka3
        logger.info(f"Running propka3 on {pdb_file.name}")
        cmd = [
            self.propka_path,
            str(pdb_file),
            f"--pH={ph:.2f}",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=output_dir,
                timeout=60
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("propka3 timed out after 60 seconds")

        if result.returncode != 0:
            error_msg = f"propka3 failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f"\nStderr: {result.stderr}"
            if result.stdout:
                error_msg += f"\nStdout: {result.stdout}"
            raise RuntimeError(error_msg)

        # Parse output
        pka_file = output_dir / f"{pdb_file.stem}.pka"
        if not pka_file.exists():
            raise RuntimeError(f"propka3 did not generate output file: {pka_file}")

        logger.info(f"propka3 completed: {pka_file.name}")
        return self._parse_output(pka_file, result.stdout)

    def _parse_output(self, pka_file: Path, stdout: str) -> PropkaResult:
        """Parse propka output file.

        Args:
            pka_file: Path to .pka output file
            stdout: Standard output from propka3

        Returns:
            PropkaResult with parsed pKa values
        """
        pka_values = {}
        metal_interactions = set()  # Track which residues interact with metals

        with pka_file.open() as f:
            content = f.read()

        # Validate file is not empty
        if not content.strip():
            raise RuntimeError(f"propka output file is empty: {pka_file}")

        # Validate file contains expected sections
        if "SUMMARY OF THIS PREDICTION" not in content:
            logger.warning(
                f"propka output missing 'SUMMARY OF THIS PREDICTION' section. "
                f"File may be incomplete or format may have changed."
            )

        # First pass: Parse detailed output for metal interactions
        # Format: "HIS  60 A   3.50    92 %   -2.57  538   0.00    0    0.00 XXX   0 X    0.00 XXX   0 X   -0.36 ZN   ZN A"
        # Metal interaction appears in the rightmost columns
        for line in content.split("\n"):
            if "ZN" in line or "FE" in line or "CU" in line or "MG" in line:
                # Check if this is a residue line with metal interaction
                parts = line.split()
                if len(parts) >= 3 and parts[0] in ("HIS", "ASP", "GLU", "CYS"):
                    try:
                        resname = parts[0]
                        resnum = int(parts[1])
                        chain = parts[2]
                        # Check if metal ion appears in interaction columns (rightmost part)
                        if any(metal in line for metal in ["ZN   ZN", "FE   FE", "CU   CU", "MG   MG"]):
                            metal_interactions.add((resname, resnum, chain))
                            logger.debug(f"Detected metal interaction: {resname} {resnum} {chain}")
                    except (ValueError, IndexError):
                        continue

        # Second pass: Parse pKa values from summary section
        # Format: "ASP  10 A    3.80     3.80    0.00  XXX   0   0    0"
        pattern = r"^([A-Z]{3})\s+(\d+)\s+([A-Z])\s+(-?\d+\.\d+)\s+(\d+\.\d+)"

        in_summary = False
        for line in content.split("\n"):
            # Find summary section
            if "SUMMARY OF THIS PREDICTION" in line:
                in_summary = True
                continue

            if not in_summary:
                continue

            # Stop at end of summary
            if line.strip().startswith("---") or line.strip() == "":
                if in_summary and pka_values:  # Only stop if we've collected data
                    break

            # Parse pKa line
            match = re.match(pattern, line.strip())
            if match:
                resname = match.group(1)
                resnum = int(match.group(2))
                chain = match.group(3)
                pka = float(match.group(4))
                model_pka = float(match.group(5))

                # Determine if buried (simplified: if pKa shift > 1.0)
                buried = abs(pka - model_pka) > 1.0

                # Check if this residue has metal interaction
                has_metal = (resname, resnum, chain) in metal_interactions

                residue_pka = ResiduePka(
                    residue_name=resname,
                    residue_number=resnum,
                    chain_id=chain,
                    pka=pka,
                    model_pka=model_pka,
                    buried=buried,
                    metal_interaction=has_metal
                )

                pka_values[(resname, resnum, chain)] = residue_pka

        # Validate parsing succeeded
        if not pka_values:
            logger.warning(
                "propka output parsing found zero pKa values. "
                "This may indicate a format change or empty input. "
                "Check the .pka file for unexpected format."
            )
        else:
            logger.info(
                f"Parsed {len(pka_values)} pKa predictions "
                f"({len(metal_interactions)} with metal interactions)"
            )

        return PropkaResult(
            pka_values=pka_values,
            summary=content
        )


# ------------------------------------------------------------------ #
# Convenience functions
# ------------------------------------------------------------------ #

def predict_pka(
    pdb_file: Path | str,
    ph: float = 7.0,
    output_dir: Path | str | None = None
) -> PropkaResult:
    """Predict pKa values for all ionizable residues in PDB file.

    Args:
        pdb_file: Path to PDB file
        ph: Target pH (default: 7.0)
        output_dir: Output directory (default: same as input)

    Returns:
        PropkaResult with pKa predictions

    Example:
        result = predict_pka("protein.pdb", ph=7.0)
        for his in result.get_his_residues():
            print(f"HIS {his.residue_number}: pKa = {his.pka:.2f}")
    """
    wrapper = PropkaWrapper()
    return wrapper.run(pdb_file, ph=ph, output_dir=output_dir)


def is_propka_available() -> bool:
    """Check if propka3 is installed and available.

    Returns:
        True if propka3 is available, False otherwise
    """
    wrapper = PropkaWrapper()
    return wrapper.is_available()
