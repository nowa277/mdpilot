"""Standard protein preparation and validation workflow.

Implements the complete pipeline from PDB ID to validated AMBER system:
1. Download PDB file from RCSB
2. Clean PDB (remove non-standard records)
3. Run pdb4amber (fix residue names, add missing atoms)
4. Determine protonation states (propka + intelligent HIS assignment)
5. Run reduce (add hydrogens, optimize H-bond network) - optional
6. Build topology with tleap (ff19SB + OPC3 water + protonation states)
7. Energy minimization (1000 steps)
8. Validate system (charge, box, HIS states, etc.)
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
from mdpilot.tools.builtin.pdb.fetcher import PDBFetcher
from mdpilot.tools.builtin.pdb.info import PDBInfo
from mdpilot.tools.builtin.amber.env_detector import configure_amber_environment
from mdpilot.workflows.protonation import ProtonationEngine, ProtonationReport
from mdpilot.workflows.validator import StandardProteinValidator, ValidationReport


@dataclass
class WorkflowConfig:
    """Configuration for standard protein workflow."""

    # Force field and water model
    force_field: str = "ff19SB"
    water_model: str = "OPC3"
    box_type: Literal["cubic", "octahedron"] = "octahedron"
    box_padding: float = 10.0  # Angstroms

    # Protonation
    use_propka: bool = True  # Use propka for pKa prediction
    target_ph: float = 7.0  # Target pH for protonation states
    pka_threshold: float = 1.0  # pKa threshold for HIS protonation decisions
    use_hplusplus: bool = False  # Use H++ as fallback if propka fails
    hplusplus_timeout: int = 300  # H++ server timeout in seconds
    protonation_report_detail: Literal["summary", "full"] = "summary"  # Report detail level

    # Minimization
    minimize_steps: int = 1000
    minimize_ncyc: int = 500  # steepest descent steps

    # File naming
    output_prefix: str = "system"

    # Paths
    work_dir: Path = field(default_factory=Path.cwd)
    keep_intermediates: bool = True

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.pka_threshold < 0:
            raise ValueError("pka_threshold must be non-negative")
        if self.hplusplus_timeout < 60:
            raise ValueError("hplusplus_timeout must be at least 60 seconds")
        if self.protonation_report_detail not in ("summary", "full"):
            raise ValueError("protonation_report_detail must be 'summary' or 'full'")


@dataclass
class WorkflowResult:
    """Result of workflow execution."""

    success: bool
    prmtop: Path | None = None
    inpcrd: Path | None = None
    validation: ValidationReport | None = None
    protonation: ProtonationReport | None = None
    error: str | None = None
    intermediate_files: dict[str, Path] = field(default_factory=dict)
    _report_detail: Literal["summary", "full"] = "summary"

    def summary(self, detail_override: Literal["summary", "full"] | None = None) -> str:
        """Generate human-readable summary.

        Args:
            detail_override: Override the default report detail level for this call
        """
        if not self.success:
            return f"❌ Workflow failed: {self.error}"

        lines = [
            "✅ Workflow completed successfully",
            f"   Topology: {self.prmtop}",
            f"   Coordinates: {self.inpcrd}",
        ]

        if self.validation:
            lines.append(f"   Validation: {self.validation.summary()}")
            if not self.validation.passed:
                lines.append("   ⚠️  Some validation checks failed:")
                for check in self.validation.checks:
                    if not check.passed:
                        lines.append(f"      - {check.name}: {check.message}")

        # Add protonation report
        if self.protonation:
            detail = detail_override or self._report_detail
            if detail == "summary":
                lines.append(self._format_protonation_summary())
            else:  # full
                lines.append("\n📊 Protonation State Summary:")
                lines.append(self.protonation.summary())

        return "\n".join(lines)

    def _format_protonation_summary(self) -> str:
        """Format protonation statistics in summary mode."""
        if not self.protonation:
            return ""

        lines = ["\n📊 Protonation State Summary:"]

        # HIS statistics
        if self.protonation.his_assignments:
            his_count = len(self.protonation.his_assignments)
            lines.append(f"   HIS residues: {his_count} assigned")

            # Count by type
            hid_count = sum(1 for v in self.protonation.his_assignments.values() if v == "HID")
            hie_count = sum(1 for v in self.protonation.his_assignments.values() if v == "HIE")
            hip_count = sum(1 for v in self.protonation.his_assignments.values() if v == "HIP")

            if hid_count > 0:
                lines.append(f"     HID (metal-coordinating): {hid_count}")
            if hie_count > 0:
                lines.append(f"     HIE (neutral): {hie_count}")
            if hip_count > 0:
                lines.append(f"     HIP (charged): {hip_count}")

        # ASP/GLU statistics
        if self.protonation.asp_glu_assignments:
            protonated_count = len(self.protonation.asp_glu_assignments)
            lines.append(f"   Protonated acidic residues: {protonated_count}")

        # CYS statistics
        if self.protonation.cys_assignments:
            # Count disulfide bonds (CYX pairs)
            cyx_count = sum(1 for v in self.protonation.cys_assignments.values() if v == "CYX")
            if cyx_count > 0:
                disulfide_count = cyx_count // 2
                lines.append(f"   Disulfide bonds: {disulfide_count}")

        return "\n".join(lines)


class StandardProteinWorkflow:
    """Standard protein preparation workflow.

    Usage:
        # Full-auto mode (from PDB ID)
        workflow = StandardProteinWorkflow()
        result = await workflow.run_from_pdb_id("2CAB")

        # Semi-auto mode (from existing PDB file)
        result = await workflow.run_from_pdb_file("2CAB.pdb")
    """

    def __init__(self, config: WorkflowConfig | None = None):
        self.config = config or WorkflowConfig()
        self.fetcher = PDBFetcher()
        self.cleaner = PDBCleaner()
        self.validator = StandardProteinValidator()

        # Configure AmberTools environment
        try:
            self.amber_env = configure_amber_environment()
            logger.info(f"AmberTools configured: {self.amber_env.amberhome}")
        except RuntimeError as e:
            logger.warning(f"AmberTools not detected: {e}")
            self.amber_env = None

    async def run_from_pdb_id(self, pdb_id: str) -> WorkflowResult:
        """Run complete workflow starting from PDB ID.

        Args:
            pdb_id: 4-character PDB ID (e.g., "2CAB")

        Returns:
            WorkflowResult with topology, coordinates, and validation report
        """
        try:
            # Step 1: Download PDB
            pdb_file = await self.fetcher.download_and_save(
                pdb_id,
                output_path=self.config.work_dir / f"{pdb_id}.pdb"
            )

            return await self.run_from_pdb_file(pdb_file)

        except Exception as e:
            return WorkflowResult(success=False, error=str(e))

    async def run_from_pdb_file(self, pdb_file: Path | str) -> WorkflowResult:
        """Run workflow starting from existing PDB file.

        Args:
            pdb_file: Path to PDB file

        Returns:
            WorkflowResult with topology, coordinates, and validation report
        """
        # Check AmberTools environment
        if self.amber_env is None:
            return WorkflowResult(
                success=False,
                error="AmberTools not detected. Please install AmberTools or set AMBERHOME."
            )

        pdb_file = Path(pdb_file)
        intermediate = {}
        protonation_report = None

        try:
            # Step 2: Clean PDB
            logger.info(f"Step 2: Cleaning PDB file")
            cleaned_pdb = self.config.work_dir / f"{pdb_file.stem}_cleaned.pdb"
            self.cleaner.clean_file(pdb_file, cleaned_pdb)
            intermediate["cleaned_pdb"] = cleaned_pdb

            # Step 3: Run pdb4amber
            logger.info(f"Step 3: Running pdb4amber")
            pdb4amber_out = self._run_pdb4amber(cleaned_pdb)
            intermediate["pdb4amber_out"] = pdb4amber_out

            # Step 4: Determine protonation states
            logger.info(f"Step 4: Determining protonation states")
            protonation_engine = ProtonationEngine(
                ph=self.config.target_ph,
                pka_threshold=self.config.pka_threshold
            )
            protonation_report = protonation_engine.determine_protonation(
                pdb4amber_out,
                use_propka=self.config.use_propka
            )
            logger.info(f"Protonation assignments: {len(protonation_report.assignments)} residues")
            intermediate["protonation_report"] = protonation_report

            # Step 5: Run reduce (optional - skip if not available)
            logger.info(f"Step 5: Running reduce (if available)")
            try:
                reduced_pdb = self._run_reduce(pdb4amber_out)
                intermediate["reduced_pdb"] = reduced_pdb
                input_for_tleap = reduced_pdb
            except (FileNotFoundError, RuntimeError) as e:
                logger.warning(f"reduce not available, skipping: {e}")
                logger.info("tleap will add missing hydrogens automatically")
                input_for_tleap = pdb4amber_out

            # Step 6: Build topology with tleap
            logger.info(f"Step 6: Building topology with tleap")
            prmtop, inpcrd = self._run_tleap(input_for_tleap, protonation_report)
            intermediate["prmtop"] = prmtop
            intermediate["inpcrd"] = inpcrd

            # Step 7: Energy minimization
            logger.info(f"Step 7: Running energy minimization")
            min_rst = self._run_minimization(prmtop, inpcrd)
            intermediate["minimized"] = min_rst

            # Step 8: Validate
            logger.info(f"Step 8: Validating system")
            validation = self.validator.validate(
                str(prmtop),
                str(min_rst),
                water_model=self.config.water_model
            )

            return WorkflowResult(
                success=True,
                prmtop=prmtop,
                inpcrd=min_rst,
                validation=validation,
                protonation=protonation_report,
                intermediate_files=intermediate
            )

        except Exception as e:
            return WorkflowResult(
                success=False,
                error=str(e),
                intermediate_files=intermediate
            )

    def _run_pdb4amber(self, input_pdb: Path) -> Path:
        """Run pdb4amber to fix residue names and add missing atoms."""
        logger.info(f"Running pdb4amber on {input_pdb.name}")
        output = self.config.work_dir / f"{input_pdb.stem}_pdb4amber.pdb"

        # Validate input path
        input_pdb = input_pdb.resolve()
        if not input_pdb.exists():
            raise FileNotFoundError(f"Input PDB not found: {input_pdb}")
        if not input_pdb.is_file():
            raise ValueError(f"Input path is not a file: {input_pdb}")

        cmd = [
            "pdb4amber",
            "-i", str(input_pdb),
            "-o", str(output),
            "--dry",  # Remove water
            # Note: Not using --reduce here, we run reduce separately in next step
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.config.work_dir,
            timeout=300
        )

        if result.returncode != 0:
            raise RuntimeError(f"pdb4amber failed: {result.stderr}")

        logger.info(f"pdb4amber completed: {output.name}")
        return output

    def _run_reduce(self, input_pdb: Path) -> Path:
        """Run reduce to add hydrogens."""
        logger.info(f"Running reduce on {input_pdb.name}")
        output = self.config.work_dir / f"{input_pdb.stem}_H.pdb"

        # Validate input path
        input_pdb = input_pdb.resolve()
        if not input_pdb.exists():
            raise FileNotFoundError(f"Input PDB not found: {input_pdb}")
        if not input_pdb.is_file():
            raise ValueError(f"Input path is not a file: {input_pdb}")

        reduce_path = shutil.which("reduce")
        if not reduce_path:
            raise RuntimeError("reduce not found in PATH")

        cmd = [
            reduce_path,
            "-build",
            "-nuclear",
            str(input_pdb)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.config.work_dir,
            timeout=300
        )

        if result.returncode != 0:
            raise RuntimeError(f"reduce failed: {result.stderr}")

        # Write output atomically
        try:
            with output.open('x') as f:
                f.write(result.stdout)
        except FileExistsError:
            output.write_text(result.stdout)

        logger.info(f"reduce completed: {output.name}")
        return output

    def _run_tleap(self, input_pdb: Path, protonation_report: ProtonationReport | None = None) -> tuple[Path, Path]:
        """Build topology with tleap.

        Args:
            input_pdb: Input PDB file
            protonation_report: Protonation state assignments (optional)

        Returns:
            Tuple of (prmtop, inpcrd) paths
        """
        logger.info(f"Running tleap on {input_pdb.name}")

        # Validate input path
        input_pdb = input_pdb.resolve()
        if not input_pdb.exists():
            raise FileNotFoundError(f"Input PDB not found: {input_pdb}")
        if not input_pdb.is_file():
            raise ValueError(f"Input path is not a file: {input_pdb}")

        prmtop = self.config.work_dir / f"{self.config.output_prefix}.prmtop"
        inpcrd = self.config.work_dir / f"{self.config.output_prefix}.inpcrd"

        # Generate tleap script
        script_lines = [
            f"source leaprc.protein.{self.config.force_field}",
            f"source leaprc.water.{self.config.water_model.lower()}",
            f"mol = loadPDB {input_pdb}",
        ]

        # Apply protonation state assignments
        if protonation_report:
            script_lines.append("")
            script_lines.append("# Protonation state assignments")
            for cmd in protonation_report.get_tleap_commands():
                script_lines.append(cmd)
            script_lines.append("")

        # Solvate
        if self.config.box_type == "octahedron":
            box_cmd = f"solvateOct mol {self.config.water_model}BOX {self.config.box_padding}"
        else:
            box_cmd = f"solvateBox mol {self.config.water_model}BOX {self.config.box_padding}"
        script_lines.append(box_cmd)

        # Neutralize (no extra ions for standard protein)
        script_lines.extend([
            "addIons mol Cl- 0",
            "addIons mol Na+ 0",
            f"saveAmberParm mol {prmtop} {inpcrd}",
            "quit"
        ])

        script = "\n".join(script_lines)
        script_file = self.config.work_dir / "tleap.in"
        script_file.write_text(script)

        # Run tleap
        tleap_path = shutil.which("tleap")
        if not tleap_path:
            raise RuntimeError("tleap not found in PATH")

        result = subprocess.run(
            [tleap_path, "-f", str(script_file)],
            capture_output=True,
            text=True,
            cwd=self.config.work_dir,
            timeout=300
        )

        if result.returncode != 0 or not prmtop.exists():
            raise RuntimeError(f"tleap failed: {result.stderr}")

        logger.info(f"tleap completed: {prmtop.name}, {inpcrd.name}")
        return prmtop, inpcrd

    def _run_minimization(self, prmtop: Path, inpcrd: Path) -> Path:
        """Run energy minimization."""
        logger.info(f"Running energy minimization")

        # Validate input paths
        prmtop = prmtop.resolve()
        inpcrd = inpcrd.resolve()
        if not prmtop.exists():
            raise FileNotFoundError(f"Topology file not found: {prmtop}")
        if not inpcrd.exists():
            raise FileNotFoundError(f"Coordinate file not found: {inpcrd}")

        min_out = self.config.work_dir / "min.out"
        min_rst = self.config.work_dir / "min.rst"

        # Generate minimization input
        min_input = f"""Energy minimization
 &cntrl
  imin=1,
  maxcyc={self.config.minimize_steps},
  ncyc={self.config.minimize_ncyc},
  cut=10.0,
  ntb=1,
  ntr=0,
 /
"""
        min_in = self.config.work_dir / "min.in"
        min_in.write_text(min_input)

        # Run sander
        sander_path = shutil.which("sander")
        if not sander_path:
            raise RuntimeError("sander not found in PATH")

        cmd = [
            sander_path,
            "-O",
            "-i", str(min_in),
            "-o", str(min_out),
            "-p", str(prmtop),
            "-c", str(inpcrd),
            "-r", str(min_rst),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.config.work_dir,
            timeout=600
        )

        if result.returncode != 0 or not min_rst.exists():
            raise RuntimeError(f"sander minimization failed: {result.stderr}")

        logger.info(f"Minimization completed: {min_rst.name}")
        return min_rst


# ------------------------------------------------------------------ #
# Convenience functions
# ------------------------------------------------------------------ #

async def prepare_standard_protein(
    pdb_id: str,
    work_dir: Path | None = None,
    config: WorkflowConfig | None = None
) -> WorkflowResult:
    """Prepare a standard protein system from PDB ID.

    Args:
        pdb_id: 4-character PDB ID
        work_dir: Working directory (default: current directory)
        config: Workflow configuration (default: standard settings)

    Returns:
        WorkflowResult with topology, coordinates, and validation

    Example:
        result = await prepare_standard_protein("2CAB")
        if result.success:
            print(f"System ready: {result.prmtop}")
        else:
            print(f"Failed: {result.error}")
    """
    if config is None:
        config = WorkflowConfig()

    if work_dir is not None:
        config.work_dir = work_dir

    workflow = StandardProteinWorkflow(config)
    return await workflow.run_from_pdb_id(pdb_id)
