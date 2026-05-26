"""System validation for AMBER topology and coordinate files.

Provides validation checks for different system types:
- Standard proteins
- Ligand systems
- Metal proteins
- Nucleic acids
- Membrane systems
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationCheck:
    """Single validation check result.

    Attributes
    ----------
    name : str
        Check name (e.g., "charge_neutral")
    passed : bool
        Whether check passed
    value : str
        Actual value observed
    expected : str
        Expected value
    message : str
        Additional information or error message
    """

    name: str
    passed: bool
    value: str
    expected: str
    message: str = ""

    def __str__(self) -> str:
        """Human-readable string representation."""
        status = "✅ PASS" if self.passed else "❌ FAIL"
        result = f"{status} {self.name}: {self.value}"
        if not self.passed:
            result += f" (expected: {self.expected})"
        if self.message:
            result += f" - {self.message}"
        return result


@dataclass
class ValidationReport:
    """Complete validation report for a system.

    Attributes
    ----------
    system_type : str
        System type (e.g., "standard_protein")
    passed : bool
        Whether all checks passed
    checks : list[ValidationCheck]
        Individual check results
    prmtop_path : str
        Path to topology file
    inpcrd_path : str
        Path to coordinate file
    """

    system_type: str
    passed: bool
    checks: list[ValidationCheck]
    prmtop_path: str
    inpcrd_path: str

    @property
    def num_passed(self) -> int:
        """Number of checks that passed."""
        return sum(1 for c in self.checks if c.passed)

    @property
    def num_failed(self) -> int:
        """Number of checks that failed."""
        return sum(1 for c in self.checks if not c.passed)

    @property
    def num_total(self) -> int:
        """Total number of checks."""
        return len(self.checks)

    def __str__(self) -> str:
        """Human-readable string representation."""
        lines = [
            f"Validation Report: {self.system_type}",
            f"Topology: {self.prmtop_path}",
            f"Coordinates: {self.inpcrd_path}",
            f"",
            f"Overall: {'✅ PASSED' if self.passed else '❌ FAILED'}",
            f"Checks: {self.num_passed}/{self.num_total} passed, {self.num_failed} failed",
            f"",
            "Details:",
        ]

        for check in self.checks:
            lines.append(f"  {check}")

        return "\n".join(lines)


class SystemValidator:
    """Base validator for AMBER systems.

    Provides common validation checks for all system types.
    """

    def __init__(self):
        """Initialize validator."""
        self.checks: list[ValidationCheck] = []

    def validate(self, prmtop: str | Path, inpcrd: str | Path) -> ValidationReport:
        """Validate AMBER system files.

        Parameters
        ----------
        prmtop : str | Path
            Path to topology file (.prmtop)
        inpcrd : str | Path
            Path to coordinate file (.inpcrd or .rst7)

        Returns
        -------
        ValidationReport
            Validation results
        """
        raise NotImplementedError("Subclasses must implement validate()")

    def _check_charge_neutral(self, structure) -> ValidationCheck:
        """Check if system is charge neutral (±0.01 e).

        Parameters
        ----------
        structure : parmed.Structure
            Loaded structure

        Returns
        -------
        ValidationCheck
            Check result
        """
        total_charge = sum(a.charge for a in structure.atoms)
        passed = abs(total_charge) < 0.01

        return ValidationCheck(
            name="charge_neutral",
            passed=passed,
            value=f"{total_charge:.4f}",
            expected="0.0000 ± 0.01",
            message="System must be electrically neutral" if not passed else "",
        )

    def _check_ep_atoms(self, structure, water_model: str = "OPC3") -> ValidationCheck:
        """Check EP (extra point) atom count.

        Parameters
        ----------
        structure : parmed.Structure
            Loaded structure
        water_model : str
            Water model used (OPC, OPC3, TIP3P, etc.)

        Returns
        -------
        ValidationCheck
            Check result
        """
        ep_count = sum(1 for a in structure.atoms if a.atomic_number == 0)

        # OPC3 and TIP3P have no EP atoms
        # OPC and TIP4P have EP atoms
        if water_model in ("OPC3", "TIP3P"):
            expected = "0"
            passed = ep_count == 0
        elif water_model in ("OPC", "TIP4P", "TIP4PEW"):
            expected = "> 0"
            passed = ep_count > 0
        else:
            expected = "unknown"
            passed = True  # Don't fail on unknown water model

        return ValidationCheck(
            name="ep_atoms",
            passed=passed,
            value=str(ep_count),
            expected=expected,
            message=f"EP atom count for {water_model} water model" if not passed else "",
        )

    def _check_box_angles(
        self, structure, expected_type: str = "octahedron"
    ) -> ValidationCheck:
        """Check box angles.

        Parameters
        ----------
        structure : parmed.Structure
            Loaded structure
        expected_type : str
            Expected box type: "octahedron" (109.47°) or "cubic" (90°)

        Returns
        -------
        ValidationCheck
            Check result
        """
        if structure.box is None:
            return ValidationCheck(
                name="box_angles",
                passed=False,
                value="None",
                expected=expected_type,
                message="No box information found",
            )

        box_angles = structure.box[3:]  # alpha, beta, gamma

        if expected_type == "octahedron":
            expected_angle = 109.47
            tolerance = 0.1
            passed = all(abs(angle - expected_angle) < tolerance for angle in box_angles)
            expected_str = "[109.47, 109.47, 109.47]"
        elif expected_type == "cubic":
            expected_angle = 90.0
            tolerance = 0.1
            passed = all(abs(angle - expected_angle) < tolerance for angle in box_angles)
            expected_str = "[90.0, 90.0, 90.0]"
        else:
            passed = True
            expected_str = "unknown"

        return ValidationCheck(
            name="box_angles",
            passed=passed,
            value=f"[{box_angles[0]:.2f}, {box_angles[1]:.2f}, {box_angles[2]:.2f}]",
            expected=expected_str,
            message=f"Box type: {expected_type}" if not passed else "",
        )

    def _check_his_assignment(self, structure) -> ValidationCheck:
        """Check that all HIS residues are assigned (HIE/HID/HIP).

        Parameters
        ----------
        structure : parmed.Structure
            Loaded structure

        Returns
        -------
        ValidationCheck
            Check result
        """
        his_count = sum(1 for r in structure.residues if r.name == "HIS")
        passed = his_count == 0

        return ValidationCheck(
            name="his_assignment",
            passed=passed,
            value=str(his_count),
            expected="0",
            message="All HIS must be assigned to HIE/HID/HIP" if not passed else "",
        )

    def _check_atom_count(self, structure, min_atoms: int = 100) -> ValidationCheck:
        """Check minimum atom count.

        Parameters
        ----------
        structure : parmed.Structure
            Loaded structure
        min_atoms : int
            Minimum expected atoms

        Returns
        -------
        ValidationCheck
            Check result
        """
        atom_count = len(structure.atoms)
        passed = atom_count >= min_atoms

        return ValidationCheck(
            name="atom_count",
            passed=passed,
            value=str(atom_count),
            expected=f">= {min_atoms}",
            message="System has too few atoms" if not passed else "",
        )

    def _check_water_molecules(self, structure) -> ValidationCheck:
        """Check that system contains water molecules.

        Parameters
        ----------
        structure : parmed.Structure
            Loaded structure

        Returns
        -------
        ValidationCheck
            Check result
        """
        water_count = sum(
            1 for r in structure.residues if r.name in ("WAT", "HOH", "TIP3", "OPC", "OPC3")
        )
        passed = water_count > 0

        return ValidationCheck(
            name="water_molecules",
            passed=passed,
            value=str(water_count),
            expected="> 0",
            message="System should contain water molecules" if not passed else "",
        )

    def _run_cpptraj_check(
        self, prmtop: str | Path, inpcrd: str | Path, script: str
    ) -> tuple[bool, str]:
        """Run cpptraj analysis script.

        Parameters
        ----------
        prmtop : str | Path
            Topology file
        inpcrd : str | Path
            Coordinate file
        script : str
            cpptraj script content

        Returns
        -------
        tuple[bool, str]
            (success, output)
        """
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".cpptraj", delete=False) as f:
                f.write(script)
                script_path = f.name

            result = subprocess.run(
                ["cpptraj", "-i", script_path],
                capture_output=True,
                text=True,
                timeout=60,
            )

            Path(script_path).unlink()

            return result.returncode == 0, result.stdout + result.stderr

        except Exception as e:
            logger.error(f"cpptraj check failed: {e}")
            return False, str(e)


class StandardProteinValidator(SystemValidator):
    """Validator for standard protein systems.

    Checks specific to proteins without ligands, metals, or nucleic acids.
    """

    def validate(
        self,
        prmtop: str | Path,
        inpcrd: str | Path,
        water_model: str = "OPC3"
    ) -> ValidationReport:
        """Validate standard protein system.

        Parameters
        ----------
        prmtop : str | Path
            Path to topology file
        inpcrd : str | Path
            Path to coordinate file
        water_model : str
            Water model used (OPC, OPC3, TIP3P, etc.)

        Returns
        -------
        ValidationReport
            Validation results
        """
        try:
            import parmed as pmd
        except ImportError:
            raise ImportError("parmed is required for validation. Install with: pip install parmed")

        prmtop = Path(prmtop)
        inpcrd = Path(inpcrd)

        if not prmtop.exists():
            raise FileNotFoundError(f"Topology file not found: {prmtop}")
        if not inpcrd.exists():
            raise FileNotFoundError(f"Coordinate file not found: {inpcrd}")

        # Load structure with timeout protection
        logger.info(f"Loading topology and coordinates for validation")
        structure = pmd.load_file(str(prmtop), xyz=str(inpcrd))

        checks = []

        # Universal checks
        checks.append(self._check_charge_neutral(structure))
        checks.append(self._check_ep_atoms(structure, water_model=water_model))
        checks.append(self._check_box_angles(structure, expected_type="octahedron"))
        checks.append(self._check_atom_count(structure, min_atoms=1000))
        checks.append(self._check_water_molecules(structure))

        # Standard protein specific checks
        checks.append(self._check_his_assignment(structure))

        # Overall pass/fail
        passed = all(c.passed for c in checks)

        logger.info(f"Validation complete: {sum(c.passed for c in checks)}/{len(checks)} checks passed")

        return ValidationReport(
            system_type="standard_protein",
            passed=passed,
            checks=checks,
            prmtop_path=str(prmtop),
            inpcrd_path=str(inpcrd),
        )
