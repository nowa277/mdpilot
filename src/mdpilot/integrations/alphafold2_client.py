"""AlphaFold2 client for protein structure prediction."""

import asyncio
import os
import re
import subprocess
from typing import Any, Dict, Optional

import aiohttp

from mdpilot.integrations.base_client import ClientMode, ModelClient


class AlphaFold2Client(ModelClient):
    """Client for AlphaFold2 structure prediction.

    Supports both local installation and API-based prediction.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize AlphaFold2 client.

        Args:
            config: Configuration dictionary with keys:
                - mode: "local" or "api"
                - local_path: Path to AlphaFold installation (local mode)
                - api_endpoint: API endpoint URL (api mode)
                - api_key: API authentication key (api mode, optional)
                - model_preset: Model preset (default: "monomer")
        """
        super().__init__(config)

        if self.mode == ClientMode.LOCAL:
            self.local_path = config["local_path"]
            self.model_preset = config.get("model_preset", "monomer")
        else:
            self.api_endpoint = config["api_endpoint"]
            self.api_key = config.get("api_key")

    def _validate_config(self) -> None:
        """Validate configuration based on mode."""
        mode = self.config.get("mode", "").lower()

        if mode == "local":
            if "local_path" not in self.config:
                raise ValueError("local_path is required for local mode")
        elif mode == "api":
            if "api_endpoint" not in self.config:
                raise ValueError("api_endpoint is required for API mode")

    async def health_check(self) -> Dict[str, Any]:
        """Check if AlphaFold2 is available and healthy.

        Returns:
            Dictionary with status, mode, and additional info
        """
        try:
            if self.mode == ClientMode.LOCAL:
                return await self._health_check_local()
            else:
                return await self._health_check_api()
        except Exception as e:
            return {
                "status": "unhealthy",
                "mode": self.mode.value,
                "error": str(e),
            }

    async def _health_check_local(self) -> Dict[str, Any]:
        """Health check for local mode."""
        if not os.path.exists(self.local_path):
            return {
                "status": "unhealthy",
                "mode": "local",
                "error": f"AlphaFold path not found: {self.local_path}",
            }

        return {
            "status": "healthy",
            "mode": "local",
            "local_path": self.local_path,
            "model_preset": self.model_preset,
        }

    async def _health_check_api(self) -> Dict[str, Any]:
        """Health check for API mode."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_endpoint}/health", headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return {
                        "status": "healthy",
                        "mode": "api",
                        "api_endpoint": self.api_endpoint,
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "mode": "api",
                        "error": f"API returned status {response.status}",
                    }

    async def predict(self, sequence: str, **options) -> Dict[str, Any]:
        """Predict protein structure from sequence.

        Args:
            sequence: Amino acid sequence
            **options: Additional prediction options (model_preset, num_recycles, etc.)

        Returns:
            Dictionary containing:
                - pdb_string: PDB format structure
                - plddt: Per-residue confidence scores
                - mean_plddt: Mean pLDDT score
                - ptm: Predicted TM-score (if available)

        Raises:
            ValueError: If sequence is invalid
            RuntimeError: If prediction fails
        """
        if not self._validate_sequence(sequence):
            raise ValueError("Invalid sequence: must be non-empty and contain only valid amino acids")

        if self.mode == ClientMode.LOCAL:
            return await self._run_local_prediction(sequence, **options)
        else:
            return await self._run_api_prediction(sequence, **options)

    def _validate_sequence(self, sequence: str) -> bool:
        """Validate amino acid sequence.

        Args:
            sequence: Amino acid sequence to validate

        Returns:
            True if valid, False otherwise
        """
        if not sequence:
            return False

        # Valid amino acid codes (20 standard + X for unknown)
        valid_pattern = re.compile(r"^[ACDEFGHIKLMNPQRSTVWYX]+$", re.IGNORECASE)
        return bool(valid_pattern.match(sequence))

    async def _run_local_prediction(self, sequence: str, **options) -> Dict[str, Any]:
        """Run prediction using local AlphaFold installation.

        Args:
            sequence: Amino acid sequence
            **options: Prediction options

        Returns:
            Prediction results dictionary
        """
        # This is a simplified implementation
        # In production, this would call the actual AlphaFold binary
        model_preset = options.get("model_preset", self.model_preset)
        num_recycles = options.get("num_recycles", 3)

        # Simulate running AlphaFold locally
        # In reality, this would involve:
        # 1. Writing sequence to FASTA file
        # 2. Running AlphaFold binary
        # 3. Parsing output files
        await asyncio.sleep(0.1)  # Simulate processing time

        # Mock result structure
        return {
            "pdb_string": f"ATOM    1  N   MET A   1...\n# Predicted with {model_preset}",
            "plddt": [95.0] * len(sequence),
            "mean_plddt": 95.0,
            "ptm": 0.9,
            "model_preset": model_preset,
            "num_recycles": num_recycles,
        }

    async def _run_api_prediction(self, sequence: str, **options) -> Dict[str, Any]:
        """Run prediction using API endpoint.

        Args:
            sequence: Amino acid sequence
            **options: Prediction options

        Returns:
            Prediction results dictionary
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "sequence": sequence,
            **options,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_endpoint}/predict",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=300),  # 5 minutes for prediction
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"API prediction failed: {error_text}")

                result = await response.json()
                return result
