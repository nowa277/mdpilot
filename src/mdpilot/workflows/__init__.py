"""AMBER workflow templates — pre-built simulation pipelines.

Common MD simulation workflows as reusable templates. Each template
is a sequence of steps with default parameters that the agent can
customize and execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    """A single step in a workflow template."""

    name: str
    description: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)


@dataclass
class WorkflowTemplate:
    """A pre-built AMBER simulation workflow.

    Attributes:
        name: Template identifier.
        description: What this workflow does.
        category: Workflow category (protein, ligand, membrane, nucleic, etc.).
        steps: Ordered list of steps.
        required_files: Input files needed.
        estimated_time: Rough time estimate.
    """

    name: str
    description: str
    category: str = "general"
    steps: list[WorkflowStep] = field(default_factory=list)
    required_files: list[str] = field(default_factory=list)
    estimated_time: str = "varies"

    def to_plan_dict(self) -> dict[str, Any]:
        """Convert to a plan-compatible dict for the Plan engine."""
        return {
            "goal": self.description,
            "steps": [
                {
                    "id": i + 1,
                    "description": step.description,
                    "tool": step.tool,
                    "arguments": step.arguments,
                    "depends_on": step.depends_on,
                }
                for i, step in enumerate(self.steps)
            ],
            "estimated_time": self.estimated_time,
        }


# ------------------------------------------------------------------ #
# Built-in Templates
# ------------------------------------------------------------------ #

PROTEIN_MD = WorkflowTemplate(
    name="protein_md",
    description="Standard protein MD simulation: prepare PDB → build topology → minimize → heat → equilibrate → production",
    category="protein",
    required_files=["protein.pdb"],
    estimated_time="4-8 hours (depends on system size)",
    steps=[
        WorkflowStep(
            name="prepare_pdb",
            description="Clean PDB file with pdb4amber",
            tool="pdb4amber",
            arguments={"input_pdb": "protein.pdb", "reduce": True},
        ),
        WorkflowStep(
            name="build_system",
            description="Build topology and coordinates with tLEaP",
            tool="tleap",
            arguments={
                "input_script": (
                    "source leaprc.protein.ff19SB\n"
                    "source leaprc.water.opc\n"
                    "mol = loadPDB protein_clean.pdb\n"
                    "solvateBox mol OPCBOX 10.0\n"
                    "addIons mol Cl- 0\n"
                    "addIons mol Na+ 0\n"
                    "saveAmberParm mol system.prmtop system.inpcrd\n"
                    "quit"
                ),
            },
            depends_on=[1],
        ),
        WorkflowStep(
            name="minimize",
            description="Energy minimization (5000 steps steepest descent + 5000 conjugate gradient)",
            tool="sander",
            arguments={
                "input_config": (
                    "Minimization\n"
                    " &cntrl\n"
                    "  imin=1, maxcyc=10000, ncyc=5000,\n"
                    "  cut=10.0, ntb=1,\n"
                    "  ntr=1, restraintmask='@CA,C,O,N',\n"
                    "  restraint_wt=5.0,\n"
                    " /"
                ),
                "prmtop": "system.prmtop",
                "inpcrd": "system.inpcrd",
                "output": "min.out",
            },
            depends_on=[2],
        ),
        WorkflowStep(
            name="heat",
            description="Heat from 0K to 300K over 100ps (NVT)",
            tool="sander",
            arguments={
                "input_config": (
                    "Heating 0-300K over 100ps\n"
                    " &cntrl\n"
                    "  imin=0, irest=0, ntx=1,\n"
                    "  nstlim=50000, dt=0.002,\n"
                    "  ntf=2, ntc=2,\n"
                    "  cut=10.0, ntb=1,\n"
                    "  ntt=3, gamma_ln=2.0,\n"
                    "  temp0=300.0, tempi=0.0,\n"
                    "  ntr=1, restraintmask='@CA,C,O,N',\n"
                    "  restraint_wt=5.0,\n"
                    "  ntpr=500, ntwx=500,\n"
                    " /"
                ),
                "prmtop": "system.prmtop",
                "inpcrd": "md.rst",
                "output": "heat.out",
                "trajectory": "heat.nc",
            },
            depends_on=[3],
        ),
        WorkflowStep(
            name="equilibrate",
            description="NPT equilibration at 300K for 1ns",
            tool="sander",
            arguments={
                "input_config": (
                    "NPT Equilibration 1ns\n"
                    " &cntrl\n"
                    "  imin=0, irest=1, ntx=5,\n"
                    "  nstlim=500000, dt=0.002,\n"
                    "  ntf=2, ntc=2,\n"
                    "  cut=10.0, ntb=2, pres0=1.0, ntp=1,\n"
                    "  ntt=3, gamma_ln=2.0,\n"
                    "  temp0=300.0,\n"
                    "  ntr=0,\n"
                    "  ntpr=1000, ntwx=1000,\n"
                    " /"
                ),
                "prmtop": "system.prmtop",
                "inpcrd": "md.rst",
                "output": "eq.out",
                "trajectory": "eq.nc",
            },
            depends_on=[4],
        ),
        WorkflowStep(
            name="production",
            description="Production MD run (100ns)",
            tool="sander",
            arguments={
                "input_config": (
                    "Production MD 100ns\n"
                    " &cntrl\n"
                    "  imin=0, irest=1, ntx=5,\n"
                    "  nstlim=50000000, dt=0.002,\n"
                    "  ntf=2, ntc=2,\n"
                    "  cut=10.0, ntb=2, pres0=1.0, ntp=1,\n"
                    "  ntt=3, gamma_ln=2.0,\n"
                    "  temp0=300.0,\n"
                    "  ntpr=5000, ntwx=5000,\n"
                    " /"
                ),
                "prmtop": "system.prmtop",
                "inpcrd": "md.rst",
                "output": "md.out",
                "trajectory": "md.nc",
            },
            depends_on=[5],
        ),
    ],
)


LIGAND_PARAMETERIZE = WorkflowTemplate(
    name="ligand_parameterize",
    description="Parameterize a small molecule ligand: mol2 → GAFF2 params + frcmod",
    category="ligand",
    required_files=["ligand.mol2"],
    estimated_time="1-5 minutes",
    steps=[
        WorkflowStep(
            name="antechamber",
            description="Generate GAFF2 atom types and AM1-BCC charges",
            tool="antechamber",
            arguments={
                "input_file": "ligand.mol2",
                "input_format": "mol2",
                "output_file": "ligand_gaff2.mol2",
                "output_format": "mol2",
                "charge_method": "bcc",
                "atom_type": "gaff2",
            },
        ),
        WorkflowStep(
            name="parmchk",
            description="Generate frcmod for missing parameters",
            tool="antechamber",
            arguments={
                "input_file": "ligand_gaff2.mol2",
                "input_format": "mol2",
                "output_file": "ligand_gaff2.mol2",
                "output_format": "mol2",
                "run_parmchk": True,
            },
            depends_on=[1],
        ),
    ],
)


TRAJECTORY_ANALYSIS = WorkflowTemplate(
    name="trajectory_analysis",
    description="Standard trajectory analysis: RMSD, RMSF, H-bonds, distances",
    category="analysis",
    required_files=["md.nc", "system.prmtop"],
    estimated_time="5-30 minutes",
    steps=[
        WorkflowStep(
            name="rmsd_analysis",
            description="Calculate backbone RMSD over time",
            tool="cpptraj",
            arguments={
                "input_script": (
                    "parm system.prmtop\n"
                    "trajin md.nc\n"
                    "rms backbone first @CA,C,O,N out rmsd_backbone.dat\n"
                    "run\n"
                    "quit"
                ),
            },
        ),
        WorkflowStep(
            name="rmsf_analysis",
            description="Calculate per-residue RMSF",
            tool="cpptraj",
            arguments={
                "input_script": (
                    "parm system.prmtop\n"
                    "trajin md.nc\n"
                    "atomicfluct out rmsf.dat @CA byres\n"
                    "run\n"
                    "quit"
                ),
            },
        ),
        WorkflowStep(
            name="hbond_analysis",
            description="Identify hydrogen bonds",
            tool="cpptraj",
            arguments={
                "input_script": (
                    "parm system.prmtop\n"
                    "trajin md.nc\n"
                    "hbond : solventacceptor : solventdonor out hbond.dat\n"
                    "run\n"
                    "quit"
                ),
            },
        ),
    ],
)


# ------------------------------------------------------------------ #
# Registry
# ------------------------------------------------------------------ #

BUILTIN_TEMPLATES: dict[str, WorkflowTemplate] = {
    "protein_md": PROTEIN_MD,
    "ligand_parameterize": LIGAND_PARAMETERIZE,
    "trajectory_analysis": TRAJECTORY_ANALYSIS,
}


def list_templates(category: str | None = None) -> list[dict[str, str]]:
    """List available workflow templates.

    Parameters
    ----------
    category : str or None
        Filter by category. None returns all.

    Returns
    -------
    list of dicts with name, description, category, estimated_time.
    """
    results = []
    for tmpl in BUILTIN_TEMPLATES.values():
        if category and tmpl.category != category:
            continue
        results.append({
            "name": tmpl.name,
            "description": tmpl.description,
            "category": tmpl.category,
            "estimated_time": tmpl.estimated_time,
        })
    return results


def get_template(name: str) -> WorkflowTemplate | None:
    """Look up a template by name."""
    return BUILTIN_TEMPLATES.get(name)


# ------------------------------------------------------------------ #
# Validation
# ------------------------------------------------------------------ #

from mdpilot.workflows.validator import (
    StandardProteinValidator,
    SystemValidator,
    ValidationCheck,
    ValidationReport,
)

# ------------------------------------------------------------------ #
# Standard Protein Workflow
# ------------------------------------------------------------------ #

from mdpilot.workflows.standard_protein import (
    StandardProteinWorkflow,
    WorkflowConfig,
    WorkflowResult,
    prepare_standard_protein,
)

__all__ = [
    "WorkflowStep",
    "WorkflowTemplate",
    "BUILTIN_TEMPLATES",
    "list_templates",
    "get_template",
    "SystemValidator",
    "StandardProteinValidator",
    "ValidationCheck",
    "ValidationReport",
    "StandardProteinWorkflow",
    "WorkflowConfig",
    "WorkflowResult",
    "prepare_standard_protein",
]
