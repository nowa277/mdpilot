"""PDB file fetcher for downloading structures from RCSB PDB."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class PDBFetcher:
    """Download PDB files from RCSB PDB database.

    Examples
    --------
    >>> fetcher = PDBFetcher()
    >>> pdb_content = await fetcher.download("2CAB")
    >>> fetcher.save(pdb_content, "2CAB.pdb")
    """

    BASE_URL = "https://files.rcsb.org/download"

    def __init__(self, timeout: int = 30):
        """Initialize PDB fetcher.

        Parameters
        ----------
        timeout : int
            HTTP request timeout in seconds (default: 30)
        """
        self.timeout = timeout

    async def download(self, pdb_id: str) -> str:
        """Download PDB file from RCSB.

        Parameters
        ----------
        pdb_id : str
            PDB ID (e.g., "2CAB", "1AKI")

        Returns
        -------
        str
            PDB file content as string

        Raises
        ------
        ValueError
            If PDB ID is invalid
        httpx.HTTPError
            If download fails
        """
        # Validate PDB ID
        pdb_id = pdb_id.strip().upper()
        if len(pdb_id) != 4:
            raise ValueError(f"Invalid PDB ID: {pdb_id} (must be 4 characters)")

        # Construct URL
        url = f"{self.BASE_URL}/{pdb_id}.pdb"

        logger.info(f"Downloading PDB {pdb_id} from {url}")

        # Download with httpx
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

        content = response.text

        # Verify content is valid PDB
        if not content.startswith(("HEADER", "TITLE", "COMPND", "ATOM", "HETATM")):
            raise ValueError(f"Downloaded content does not appear to be a valid PDB file")

        # Basic format validation
        lines = content.split("\n")
        if len(lines) < 10:
            raise ValueError(f"PDB file too short ({len(lines)} lines)")

        # Check for at least one ATOM or HETATM record
        has_atoms = any(line.startswith(("ATOM", "HETATM")) for line in lines[:1000])
        if not has_atoms:
            raise ValueError("PDB file contains no ATOM or HETATM records")

        logger.info(f"Successfully downloaded PDB {pdb_id} ({len(content)} bytes)")

        return content

    def download_sync(self, pdb_id: str) -> str:
        """Synchronous version of download().

        Parameters
        ----------
        pdb_id : str
            PDB ID (e.g., "2CAB", "1AKI")

        Returns
        -------
        str
            PDB file content as string
        """
        import httpx

        pdb_id = pdb_id.strip().upper()
        if len(pdb_id) != 4:
            raise ValueError(f"Invalid PDB ID: {pdb_id} (must be 4 characters)")

        url = f"{self.BASE_URL}/{pdb_id}.pdb"

        logger.info(f"Downloading PDB {pdb_id} from {url}")

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url)
            response.raise_for_status()

        content = response.text

        if not content.startswith(("HEADER", "TITLE", "COMPND", "ATOM", "HETATM")):
            raise ValueError(f"Downloaded content does not appear to be a valid PDB file")

        logger.info(f"Successfully downloaded PDB {pdb_id} ({len(content)} bytes)")

        return content

    def save(self, content: str, output_path: str | Path) -> None:
        """Save PDB content to file.

        Parameters
        ----------
        content : str
            PDB file content
        output_path : str | Path
            Output file path
        """
        output_path = Path(output_path).resolve()

        # Validate output path is not attempting path traversal
        try:
            # Check if path is within a reasonable directory
            output_path.relative_to(Path.cwd())
        except ValueError:
            # Path is outside cwd, check if it's in home or temp
            try:
                output_path.relative_to(Path.home())
            except ValueError:
                raise ValueError(
                    f"Output path is outside allowed directories: {output_path}"
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        logger.info(f"Saved PDB to {output_path}")

    async def download_and_save(self, pdb_id: str, output_path: str | Path) -> Path:
        """Download PDB and save to file in one step.

        Parameters
        ----------
        pdb_id : str
            PDB ID (e.g., "2CAB")
        output_path : str | Path
            Output file path

        Returns
        -------
        Path
            Path to saved file
        """
        content = await self.download(pdb_id)
        output_path = Path(output_path)
        self.save(content, output_path)
        return output_path

    def download_and_save_sync(self, pdb_id: str, output_path: str | Path) -> Path:
        """Synchronous version of download_and_save().

        Parameters
        ----------
        pdb_id : str
            PDB ID (e.g., "2CAB")
        output_path : str | Path
            Output file path

        Returns
        -------
        Path
            Path to saved file
        """
        content = self.download_sync(pdb_id)
        output_path = Path(output_path)
        self.save(content, output_path)
        return output_path
