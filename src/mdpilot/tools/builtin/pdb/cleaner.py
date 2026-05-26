"""PDB file cleaner for preprocessing structures before AMBER tools."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDBCleaner:
    """Clean PDB files for AMBER system preparation.

    Removes unnecessary records and prepares PDB for pdb4amber processing.

    Examples
    --------
    >>> cleaner = PDBCleaner()
    >>> cleaned = cleaner.clean("input.pdb")
    >>> cleaner.save(cleaned, "cleaned.pdb")
    """

    # Records to keep for AMBER processing
    KEEP_RECORDS = {
        "ATOM",
        "HETATM",
        "TER",
        "END",
        "CONECT",  # Important for metal coordination
        "LINK",    # Important for disulfide bonds and metal coordination
    }

    def __init__(self, keep_conect: bool = True, keep_link: bool = True):
        """Initialize PDB cleaner.

        Parameters
        ----------
        keep_conect : bool
            Keep CONECT records (default: True, needed for metal coordination)
        keep_link : bool
            Keep LINK records (default: True, needed for disulfide bonds)
        """
        self.keep_conect = keep_conect
        self.keep_link = keep_link

    def clean(self, pdb_content: str) -> str:
        """Clean PDB content by removing unnecessary records.

        Parameters
        ----------
        pdb_content : str
            Raw PDB file content

        Returns
        -------
        str
            Cleaned PDB content with only essential records
        """
        lines = pdb_content.split("\n")
        cleaned_lines = []

        for line in lines:
            if not line.strip():
                continue

            # Get record type (first 6 characters)
            record_type = line[:6].strip()

            # Keep essential records
            if record_type in ("ATOM", "HETATM", "TER", "END"):
                cleaned_lines.append(line)
            elif record_type == "CONECT" and self.keep_conect:
                cleaned_lines.append(line)
            elif record_type == "LINK" and self.keep_link:
                cleaned_lines.append(line)

        # Ensure END record
        if cleaned_lines and not cleaned_lines[-1].startswith("END"):
            cleaned_lines.append("END")

        result = "\n".join(cleaned_lines)

        logger.info(
            f"Cleaned PDB: {len(lines)} → {len(cleaned_lines)} lines "
            f"({len(cleaned_lines)/len(lines)*100:.1f}% retained)"
        )

        return result

    def clean_file(self, input_path: str | Path, output_path: str | Path) -> None:
        """Clean PDB file and save result.

        Parameters
        ----------
        input_path : str | Path
            Input PDB file path
        output_path : str | Path
            Output cleaned PDB file path
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        # Read input
        with open(input_path, "r") as f:
            content = f.read()

        # Clean
        cleaned = self.clean(content)

        # Atomic write: write to temp file, then rename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory as output
        fd, temp_path = tempfile.mkstemp(
            dir=output_path.parent,
            prefix=".tmp_",
            suffix=".pdb"
        )

        try:
            with os.fdopen(fd, "w") as f:
                f.write(cleaned)

            # Atomic rename
            os.replace(temp_path, output_path)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

        logger.info(f"Cleaned PDB saved to {output_path}")

    def remove_waters(self, pdb_content: str) -> str:
        """Remove water molecules from PDB.

        Parameters
        ----------
        pdb_content : str
            PDB file content

        Returns
        -------
        str
            PDB content without water molecules
        """
        lines = pdb_content.split("\n")
        filtered_lines = []

        for line in lines:
            if not line.strip():
                continue

            record_type = line[:6].strip()

            # Skip water molecules
            if record_type in ("ATOM", "HETATM"):
                residue_name = line[17:20].strip()
                if residue_name in ("HOH", "WAT", "H2O", "TIP", "TIP3", "SOL"):
                    continue

            filtered_lines.append(line)

        result = "\n".join(filtered_lines)

        logger.info(f"Removed water molecules from PDB")

        return result

    def remove_heteroatoms(
        self, pdb_content: str, keep_metals: bool = True
    ) -> str:
        """Remove HETATM records (except metals if specified).

        Parameters
        ----------
        pdb_content : str
            PDB file content
        keep_metals : bool
            Keep metal ions (Zn, Fe, Ca, Mg, etc.) (default: True)

        Returns
        -------
        str
            PDB content without heteroatoms (except metals)
        """
        # Common metal ions to keep
        METAL_IONS = {
            "ZN", "FE", "CA", "MG", "MN", "CU", "CO", "NI",
            "K", "NA", "CL", "FE2", "SF4", "F3S", "FES"
        }

        lines = pdb_content.split("\n")
        filtered_lines = []

        for line in lines:
            if not line.strip():
                continue

            record_type = line[:6].strip()

            # Keep ATOM records
            if record_type == "ATOM":
                filtered_lines.append(line)
                continue

            # Handle HETATM
            if record_type == "HETATM":
                if keep_metals:
                    residue_name = line[17:20].strip()
                    if residue_name in METAL_IONS:
                        filtered_lines.append(line)
                        continue
                # Skip other HETATM
                continue

            # Keep other records (TER, END, CONECT, LINK)
            filtered_lines.append(line)

        result = "\n".join(filtered_lines)

        logger.info(f"Removed heteroatoms from PDB (keep_metals={keep_metals})")

        return result

    def extract_chain(self, pdb_content: str, chain_id: str) -> str:
        """Extract a specific chain from PDB.

        Parameters
        ----------
        pdb_content : str
            PDB file content
        chain_id : str
            Chain identifier (e.g., "A", "B")

        Returns
        -------
        str
            PDB content with only the specified chain
        """
        lines = pdb_content.split("\n")
        filtered_lines = []

        for line in lines:
            if not line.strip():
                continue

            record_type = line[:6].strip()

            # Extract chain from ATOM/HETATM
            if record_type in ("ATOM", "HETATM"):
                line_chain = line[21:22].strip()
                if line_chain == chain_id:
                    filtered_lines.append(line)
            # Keep other records
            elif record_type in ("TER", "END", "CONECT", "LINK"):
                filtered_lines.append(line)

        result = "\n".join(filtered_lines)

        logger.info(f"Extracted chain {chain_id} from PDB")

        return result

    def renumber_residues(self, pdb_content: str, start: int = 1) -> str:
        """Renumber residues sequentially starting from specified number.

        Parameters
        ----------
        pdb_content : str
            PDB file content
        start : int
            Starting residue number (default: 1)

        Returns
        -------
        str
            PDB content with renumbered residues
        """
        lines = pdb_content.split("\n")
        renumbered_lines = []

        current_resnum = None
        new_resnum = start - 1

        for line in lines:
            if not line.strip():
                continue

            record_type = line[:6].strip()

            if record_type in ("ATOM", "HETATM"):
                # Get original residue number
                orig_resnum = line[22:26].strip()

                # Increment counter when residue changes
                if orig_resnum != current_resnum:
                    current_resnum = orig_resnum
                    new_resnum += 1

                # Replace residue number (columns 23-26, right-aligned)
                new_line = line[:22] + f"{new_resnum:4d}" + line[26:]
                renumbered_lines.append(new_line)
            else:
                renumbered_lines.append(line)

        result = "\n".join(renumbered_lines)

        logger.info(f"Renumbered residues starting from {start}")

        return result
