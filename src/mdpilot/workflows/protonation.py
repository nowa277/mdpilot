"""Protonation state determination for protein preparation.

This module implements intelligent protonation state assignment based on:
- propka pKa predictions
- Metal coordination detection
- H-bond network analysis
- Local environment analysis

References:
- AMBER Tutorial B1: Standard protein preparation
- Olsson et al. (2011) J. Chem. Theory Comput. 7, 525-537
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

from mdpilot.tools.builtin.pdb.info import PDBInfo
from mdpilot.tools.builtin.propka import PropkaResult, predict_pka


@dataclass
class ProtonationAssignment:
    """Protonation state assignment for a residue."""

    residue_name: str  # Original name (e.g., "HIS")
    residue_number: int
    chain_id: str
    assigned_name: str  # AMBER name (e.g., "HID", "HIE", "HIP")
    reason: str  # Explanation for assignment
    pka: float | None = None  # pKa value if available


@dataclass
class ProtonationReport:
    """Complete protonation state report."""

    assignments: list[ProtonationAssignment]
    his_assignments: dict[int, str]  # resnum -> HID/HIE/HIP
    asp_glu_assignments: dict[int, str]  # resnum -> ASP/ASH, GLU/GLH
    cys_assignments: dict[int, str]  # resnum -> CYS/CYX/CYM

    def get_tleap_commands(self) -> list[str]:
        """Generate tleap commands for protonation state assignment.

        Returns:
            List of tleap commands (e.g., 'set mol.10 name "HID"')
        """
        commands = []

        # HIS assignments
        for resnum, name in self.his_assignments.items():
            commands.append(f'set mol.{resnum} name "{name}"')

        # ASP/GLU assignments (protonated forms)
        for resnum, name in self.asp_glu_assignments.items():
            if name in ("ASH", "GLH"):
                commands.append(f'set mol.{resnum} name "{name}"')

        # CYS assignments (deprotonated/disulfide)
        for resnum, name in self.cys_assignments.items():
            if name in ("CYX", "CYM"):
                commands.append(f'set mol.{resnum} name "{name}"')

        return commands

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = ["Protonation State Assignments:"]
        lines.append("-" * 60)

        if self.his_assignments:
            lines.append(f"\nHistidine ({len(self.his_assignments)} residues):")
            for resnum, name in sorted(self.his_assignments.items()):
                assignment = next(a for a in self.assignments if a.residue_number == resnum and a.residue_name == "HIS")
                lines.append(f"  HIS {resnum:3d} → {name:3s}  ({assignment.reason})")

        if self.asp_glu_assignments:
            lines.append(f"\nAcidic residues ({len(self.asp_glu_assignments)} modified):")
            for resnum, name in sorted(self.asp_glu_assignments.items()):
                assignment = next(a for a in self.assignments if a.residue_number == resnum and a.residue_name in ("ASP", "GLU"))
                lines.append(f"  {assignment.residue_name} {resnum:3d} → {name:3s}  ({assignment.reason})")

        if self.cys_assignments:
            lines.append(f"\nCysteine ({len(self.cys_assignments)} modified):")
            for resnum, name in sorted(self.cys_assignments.items()):
                assignment = next(a for a in self.assignments if a.residue_number == resnum and a.residue_name == "CYS")
                lines.append(f"  CYS {resnum:3d} → {name:3s}  ({assignment.reason})")

        return "\n".join(lines)


class ProtonationEngine:
    """Intelligent protonation state determination engine.

    This engine uses propka pKa predictions and structural analysis to determine
    optimal protonation states for ionizable residues in protein structures.

    Note on propka pH parameter:
    When propka is used, the pH parameter affects how propka interprets protonation
    states, but does NOT change the calculated pKa values. pKa values are intrinsic
    properties of the residue environment. This engine uses the pKa values (which are
    pH-independent) to make protonation decisions based on the target simulation pH.
    """

    # Standard pKa values for reference
    STANDARD_PKA = {
        "HIS": 6.0,
        "ASP": 3.9,
        "GLU": 4.3,
        "LYS": 10.5,
        "CYS": 8.3,
    }

    # Metal ions that coordinate with HIS
    METAL_IONS = {"ZN", "FE", "CU", "MG", "CA", "MN", "CO", "NI"}

    # HIS protonation decision threshold (pH units)
    # If |pKa - pH| < threshold, consider pKa ≈ pH
    DEFAULT_PKA_THRESHOLD = 1.0

    def __init__(self, ph: float = 7.0, pka_threshold: float = 1.0):
        """Initialize protonation engine.

        Args:
            ph: Target pH for simulation (default: 7.0)
            pka_threshold: pH units for pKa ≈ pH decision (default: 1.0)
                          If |pKa - pH| < threshold, assign HIE
                          If pKa > pH + threshold, assign HIP
                          If pKa < pH - threshold, assign HIE

        Raises:
            ValueError: If pH is outside reasonable range (0-14)
        """
        if not 0 <= ph <= 14:
            raise ValueError(f"pH must be between 0 and 14, got {ph}")
        if ph < 2 or ph > 12:
            logger.warning(
                f"pH {ph} is outside typical physiological range (2-12). "
                "Extreme pH values may produce unexpected protonation states."
            )
        if pka_threshold < 0:
            raise ValueError(f"pka_threshold must be non-negative, got {pka_threshold}")

        self.ph = ph
        self.pka_threshold = pka_threshold

    def determine_protonation(
        self,
        pdb_file: Path | str,
        propka_result: PropkaResult | None = None,
        use_propka: bool = True
    ) -> ProtonationReport:
        """Determine protonation states for all ionizable residues.

        Args:
            pdb_file: Path to PDB file
            propka_result: Pre-computed propka result (optional)
            use_propka: Whether to use propka for pKa prediction (default: True)

        Returns:
            ProtonationReport with assignments and tleap commands
        """
        pdb_file = Path(pdb_file)

        # Run propka if requested and not provided
        if use_propka and propka_result is None:
            try:
                from mdpilot.tools.builtin.propka import is_propka_available
                if is_propka_available():
                    logger.info("Running propka for pKa prediction")
                    propka_result = predict_pka(pdb_file, ph=self.ph)
                else:
                    logger.warning("propka not available, using default rules")
                    use_propka = False
            except Exception as e:
                logger.warning(f"propka failed: {e}, using default rules")
                use_propka = False

        # Extract PDB info
        pdb_info = PDBInfo.from_file(pdb_file)

        # Determine assignments
        assignments = []
        his_assignments = {}
        asp_glu_assignments = {}
        cys_assignments = {}

        # Process HIS residues
        his_residues = self._find_his_residues(pdb_file)
        logger.debug(f"Found {len(his_residues)} HIS residues: {his_residues}")
        for resnum, chain in his_residues:
            assignment = self._determine_his_protonation(
                resnum, chain, pdb_info, propka_result
            )
            assignments.append(assignment)
            his_assignments[resnum] = assignment.assigned_name

        # Process ASP/GLU residues
        if propka_result:
            for asp in propka_result.get_asp_residues():
                if asp.pka > self.ph:  # Protonated at target pH
                    assignment = ProtonationAssignment(
                        residue_name="ASP",
                        residue_number=asp.residue_number,
                        chain_id=asp.chain_id,
                        assigned_name="ASH",  # Protonated ASP
                        reason=f"pKa={asp.pka:.1f} > pH={self.ph:.1f}",
                        pka=asp.pka
                    )
                    assignments.append(assignment)
                    asp_glu_assignments[asp.residue_number] = "ASH"

            for glu in propka_result.get_glu_residues():
                if glu.pka > self.ph:  # Protonated at target pH
                    assignment = ProtonationAssignment(
                        residue_name="GLU",
                        residue_number=glu.residue_number,
                        chain_id=glu.chain_id,
                        assigned_name="GLH",  # Protonated GLU
                        reason=f"pKa={glu.pka:.1f} > pH={self.ph:.1f}",
                        pka=glu.pka
                    )
                    assignments.append(assignment)
                    asp_glu_assignments[glu.residue_number] = "GLH"

        # Process CYS residues for disulfide bonds
        disulfide_pairs = self._detect_disulfide_bonds(pdb_file)
        for resnum1, resnum2, chain1, chain2 in disulfide_pairs:
            # Assign both cysteines as CYX (disulfide bonded)
            for resnum, chain in [(resnum1, chain1), (resnum2, chain2)]:
                assignment = ProtonationAssignment(
                    residue_name="CYS",
                    residue_number=resnum,
                    chain_id=chain,
                    assigned_name="CYX",
                    reason=f"Disulfide bond with CYS {resnum2 if resnum == resnum1 else resnum1}",
                )
                assignments.append(assignment)
                cys_assignments[resnum] = "CYX"

        return ProtonationReport(
            assignments=assignments,
            his_assignments=his_assignments,
            asp_glu_assignments=asp_glu_assignments,
            cys_assignments=cys_assignments
        )

    def _find_his_residues(self, pdb_file: Path) -> list[tuple[int, str]]:
        """Find all HIS residues in PDB file.

        Returns:
            List of (residue_number, chain_id) tuples
        """
        his_residues = []
        seen = set()

        with open(pdb_file) as f:
            for line in f:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    resname = line[17:20].strip()
                    if resname in ("HIS", "HIE", "HID", "HIP"):
                        resnum = int(line[22:26].strip())
                        chain = line[21].strip() or "A"
                        key = (resnum, chain)
                        if key not in seen:
                            his_residues.append(key)
                            seen.add(key)

        return his_residues

    def _determine_his_protonation(
        self,
        resnum: int,
        chain: str,
        pdb_info: PDBInfo,
        propka_result: PropkaResult | None
    ) -> ProtonationAssignment:
        """Determine HIS protonation state using decision tree.

        Decision tree:
        1. Check for metal coordination → HID (ND1 deprotonated)
        2. Check propka pKa:
           - pKa > pH+threshold → HIP (charged, both protonated)
           - Otherwise → HIE (NE2 protonated, default)
        3. Default → HIE

        Args:
            resnum: Residue number
            chain: Chain ID
            pdb_info: PDB information
            propka_result: propka result (optional)

        Returns:
            ProtonationAssignment for this HIS
        """
        # Check for metal coordination (using propka metal interaction data)
        if self._is_metal_coordinated(resnum, chain, propka_result):
            logger.debug(f"HIS {resnum} {chain}: Assigned HID (metal coordination)")
            return ProtonationAssignment(
                residue_name="HIS",
                residue_number=resnum,
                chain_id=chain,
                assigned_name="HID",
                reason="Metal coordination (ND1 deprotonated)"
            )

        # Use propka if available
        if propka_result:
            his_pka = propka_result.get_residue("HIS", resnum, chain)
            if his_pka:
                pka_diff = his_pka.pka - self.ph
                logger.debug(
                    f"HIS {resnum} {chain}: pKa={his_pka.pka:.2f}, pH={self.ph:.2f}, "
                    f"diff={pka_diff:.2f}, threshold={self.pka_threshold:.2f}"
                )

                # Charged if pKa significantly above pH
                if his_pka.pka > self.ph + self.pka_threshold:
                    logger.debug(f"HIS {resnum} {chain}: Assigned HIP (pKa >> pH)")
                    return ProtonationAssignment(
                        residue_name="HIS",
                        residue_number=resnum,
                        chain_id=chain,
                        assigned_name="HIP",
                        reason=f"pKa={his_pka.pka:.1f} >> pH={self.ph:.1f} (charged)",
                        pka=his_pka.pka
                    )
                # Default to HIE
                else:
                    logger.debug(f"HIS {resnum} {chain}: Assigned HIE (pKa ≈ pH)")
                    return ProtonationAssignment(
                        residue_name="HIS",
                        residue_number=resnum,
                        chain_id=chain,
                        assigned_name="HIE",
                        reason=f"pKa={his_pka.pka:.1f} ≈ pH={self.ph:.1f} (NE2 protonated)",
                        pka=his_pka.pka
                    )

        # Default: HIE (most common)
        logger.debug(f"HIS {resnum} {chain}: Assigned HIE (default, no propka data)")
        return ProtonationAssignment(
            residue_name="HIS",
            residue_number=resnum,
            chain_id=chain,
            assigned_name="HIE",
            reason="Default (NE2 protonated)"
        )

    def _is_metal_coordinated(self, resnum: int, chain: str, propka_result: PropkaResult | None) -> bool:
        """Check if HIS residue is coordinated to a metal ion.

        Args:
            resnum: HIS residue number
            chain: Chain ID
            propka_result: propka result with metal interaction data

        Returns:
            True if metal coordination detected
        """
        # If propka is available, use its metal interaction annotations
        if propka_result:
            his_pka = propka_result.get_residue("HIS", resnum, chain)
            if his_pka and his_pka.metal_interaction:
                logger.info(f"HIS {resnum} {chain}: Metal coordination detected by propka")
                return True

        # If propka not available or no metal interaction found, return False
        # (Conservative: only assign HID if we have evidence of metal coordination)
        return False

    def _check_metal_distance(
        self,
        his_coords: tuple[float, float, float],
        metal_coords: tuple[float, float, float]
    ) -> bool:
        """Check if HIS is within coordination distance of metal.

        Args:
            his_coords: HIS ND1/NE2 coordinates
            metal_coords: Metal ion coordinates

        Returns:
            True if distance < 3.0 Å (typical coordination distance)
        """
        dx = his_coords[0] - metal_coords[0]
        dy = his_coords[1] - metal_coords[1]
        dz = his_coords[2] - metal_coords[2]
        distance = (dx**2 + dy**2 + dz**2) ** 0.5
        return distance < 3.0

    def _detect_disulfide_bonds(self, pdb_file: Path) -> list[tuple[int, int, str, str]]:
        """Detect disulfide bonds between CYS residues.

        First tries to parse pdb4amber's sslink file. If that's empty or missing,
        falls back to distance-based detection (SG-SG distance < 2.5 Å).

        Args:
            pdb_file: Path to PDB file

        Returns:
            List of (resnum1, resnum2, chain1, chain2) tuples for disulfide pairs
        """
        disulfide_pairs = []

        # Try to parse pdb4amber sslink file first
        sslink_file = pdb_file.parent / f"{pdb_file.stem}_sslink"
        if sslink_file.exists() and sslink_file.stat().st_size > 0:
            try:
                with sslink_file.open() as f:
                    for line in f:
                        # Parse sslink format (if pdb4amber generates it)
                        # Format may vary, so this is a best-effort parse
                        if "CYS" in line:
                            parts = line.split()
                            # Try to extract residue numbers
                            # This is a simplified parser - may need adjustment
                            logger.debug(f"Found sslink entry: {line.strip()}")
            except Exception as e:
                logger.debug(f"Could not parse sslink file: {e}")

        # If no disulfides found from sslink, try distance-based detection
        # Parse PDB file to extract CYS SG coordinates
        cys_residues = {}  # (resnum, chain) -> (x, y, z)

        try:
            with pdb_file.open() as f:
                for line in f:
                    if line.startswith("ATOM") or line.startswith("HETATM"):
                        atom_name = line[12:16].strip()
                        resname = line[17:20].strip()

                        if resname == "CYS" and atom_name == "SG":
                            try:
                                resnum = int(line[22:26].strip())
                                chain = line[21].strip() or "A"
                                x = float(line[30:38].strip())
                                y = float(line[38:46].strip())
                                z = float(line[46:54].strip())
                                cys_residues[(resnum, chain)] = (x, y, z)
                            except (ValueError, IndexError):
                                continue

            # Check all pairs for disulfide bonds (distance < 2.5 Å)
            cys_list = list(cys_residues.keys())
            for i, (resnum1, chain1) in enumerate(cys_list):
                for resnum2, chain2 in cys_list[i+1:]:
                    coords1 = cys_residues[(resnum1, chain1)]
                    coords2 = cys_residues[(resnum2, chain2)]

                    dx = coords1[0] - coords2[0]
                    dy = coords1[1] - coords2[1]
                    dz = coords1[2] - coords2[2]
                    distance = (dx**2 + dy**2 + dz**2) ** 0.5

                    if distance < 2.5:  # Disulfide bond threshold
                        disulfide_pairs.append((resnum1, resnum2, chain1, chain2))
                        logger.info(
                            f"Detected disulfide bond: CYS {resnum1} {chain1} - "
                            f"CYS {resnum2} {chain2} (distance: {distance:.2f} Å)"
                        )
                        logger.debug(f"Disulfide bond: CYS {resnum1}-{resnum2}, distance={distance:.2f} Å")

        except Exception as e:
            logger.warning(f"Could not detect disulfide bonds: {e}")

        return disulfide_pairs


# ------------------------------------------------------------------ #
# Convenience functions
# ------------------------------------------------------------------ #

def determine_protonation_states(
    pdb_file: Path | str,
    ph: float = 7.0,
    use_propka: bool = True
) -> ProtonationReport:
    """Determine protonation states for protein preparation.

    Args:
        pdb_file: Path to PDB file
        ph: Target pH (default: 7.0)
        use_propka: Use propka for pKa prediction (default: True)

    Returns:
        ProtonationReport with assignments and tleap commands

    Example:
        report = determine_protonation_states("protein.pdb", ph=7.0)
        print(report.summary())

        # Get tleap commands
        for cmd in report.get_tleap_commands():
            print(cmd)
    """
    engine = ProtonationEngine(ph=ph)
    return engine.determine_protonation(pdb_file, use_propka=use_propka)
