"""PDB file information extractor."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PDBInfo:
    """PDB file metadata and structure information.

    Attributes
    ----------
    pdb_id : str
        PDB identifier (e.g., "2CAB")
    title : str
        Structure title
    organism : str
        Source organism
    resolution : float | None
        Resolution in Angstroms (None for NMR structures)
    chains : list[str]
        Chain identifiers
    num_atoms : int
        Total number of atoms
    num_residues : int
        Total number of residues
    has_metals : bool
        Whether structure contains metal ions
    has_ligands : bool
        Whether structure contains ligands
    metal_ions : list[str]
        List of metal ion residue names
    ligands : list[str]
        List of ligand residue names
    """

    pdb_id: str
    title: str
    organism: str
    resolution: Optional[float]
    chains: list[str]
    num_atoms: int
    num_residues: int
    has_metals: bool
    has_ligands: bool
    metal_ions: list[str]
    ligands: list[str]

    @classmethod
    def from_pdb(cls, pdb_content: str) -> PDBInfo:
        """Extract information from PDB file content.

        Parameters
        ----------
        pdb_content : str
            PDB file content

        Returns
        -------
        PDBInfo
            Extracted PDB information
        """
        lines = pdb_content.split("\n")

        # Extract header information
        pdb_id = ""
        title = ""
        organism = ""
        resolution = None

        for line in lines:
            record_type = line[:6].strip()

            if record_type == "HEADER":
                pdb_id = line[62:66].strip()

            elif record_type == "TITLE":
                title += " " + line[10:].strip()

            elif record_type == "SOURCE":
                if "ORGANISM_SCIENTIFIC:" in line:
                    organism = line.split("ORGANISM_SCIENTIFIC:")[1].strip().rstrip(";")

            elif record_type == "REMARK" and line[7:10].strip() == "2":
                # REMARK   2 RESOLUTION
                if "RESOLUTION" in line:
                    match = re.search(r"(\d+\.\d+)\s+ANGSTROM", line)
                    if match:
                        resolution = float(match.group(1))

        title = title.strip()

        # Extract structure information
        chains = set()
        num_atoms = 0
        num_residues = 0
        residues_seen = set()
        metal_ions = set()
        ligands = set()

        # Common metal ions
        METAL_IONS = {
            "ZN", "FE", "CA", "MG", "MN", "CU", "CO", "NI",
            "K", "NA", "CL", "FE2", "SF4", "F3S", "FES"
        }

        # Standard amino acids
        AMINO_ACIDS = {
            "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY",
            "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER",
            "THR", "TRP", "TYR", "VAL", "HIE", "HID", "HIP", "CYX"
        }

        # Standard nucleotides
        NUCLEOTIDES = {
            "A", "C", "G", "T", "U",
            "DA", "DC", "DG", "DT",
            "RA", "RC", "RG", "RU"
        }

        for line in lines:
            record_type = line[:6].strip()

            if record_type in ("ATOM", "HETATM"):
                num_atoms += 1

                # Extract chain
                chain = line[21:22].strip()
                if chain:
                    chains.add(chain)

                # Extract residue
                residue_name = line[17:20].strip()
                residue_num = line[22:26].strip()
                residue_key = f"{chain}:{residue_name}:{residue_num}"

                if residue_key not in residues_seen:
                    residues_seen.add(residue_key)
                    num_residues += 1

                # Check for metals and ligands
                if record_type == "HETATM":
                    if residue_name in METAL_IONS:
                        metal_ions.add(residue_name)
                    elif residue_name not in ("HOH", "WAT", "H2O", "TIP", "TIP3", "SOL"):
                        if residue_name not in AMINO_ACIDS and residue_name not in NUCLEOTIDES:
                            ligands.add(residue_name)

        return cls(
            pdb_id=pdb_id,
            title=title,
            organism=organism,
            resolution=resolution,
            chains=sorted(chains),
            num_atoms=num_atoms,
            num_residues=num_residues,
            has_metals=len(metal_ions) > 0,
            has_ligands=len(ligands) > 0,
            metal_ions=sorted(metal_ions),
            ligands=sorted(ligands),
        )

    @classmethod
    def from_file(cls, pdb_path: str | Path) -> PDBInfo:
        """Extract information from PDB file.

        Parameters
        ----------
        pdb_path : str | Path
            Path to PDB file

        Returns
        -------
        PDBInfo
            Extracted PDB information
        """
        with open(pdb_path, "r") as f:
            content = f.read()
        return cls.from_pdb(content)

    def __str__(self) -> str:
        """Human-readable string representation."""
        lines = [
            f"PDB ID: {self.pdb_id}",
            f"Title: {self.title[:60]}..." if len(self.title) > 60 else f"Title: {self.title}",
            f"Organism: {self.organism}",
            f"Resolution: {self.resolution:.2f} Å" if self.resolution else "Resolution: N/A",
            f"Chains: {', '.join(self.chains)}",
            f"Atoms: {self.num_atoms}",
            f"Residues: {self.num_residues}",
        ]

        if self.has_metals:
            lines.append(f"Metal ions: {', '.join(self.metal_ions)}")

        if self.has_ligands:
            lines.append(f"Ligands: {', '.join(self.ligands)}")

        return "\n".join(lines)
