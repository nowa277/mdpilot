"""BioReason client with SSH + Celery integration for remote execution"""

from typing import Any, Dict, Optional, Callable
from mdpilot.integrations.base_client import ModelClient
from mdpilot.integrations.bioreason.celery_client import BioreasonCeleryClient
from mdpilot.config.defaults import DEFAULT_BIOREASON_REMOTE
from mdpilot.types import TaskProgress


class BioreasonClient(ModelClient):
    """BioReason client using SSH + Celery for remote execution
    
    Connects to lab06 (六号机) to execute BioReason-Pro GO term prediction
    via Celery task queue with real-time progress tracking.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, use_remote: bool = True):
        """Initialize BioReason client
        
        Args:
            config: Remote configuration (uses DEFAULT_BIOREASON_REMOTE if None)
            use_remote: Whether to use remote Celery mode (True) or mock mode (False)
        """
        self.use_remote = use_remote
        self.config = config or {}
        
        if use_remote:
            remote_config = config if config else DEFAULT_BIOREASON_REMOTE
            self._celery_client = BioreasonCeleryClient(**remote_config)
        else:
            self._celery_client = None
    
    def _validate_config(self) -> None:
        """Validate configuration (no-op for BioReason)"""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if BioReason service is available
        
        Returns:
            Dictionary with status and connection info
        """
        if not self.use_remote:
            return {"status": "mock", "mode": "mock"}
        
        try:
            async with self._celery_client as client:
                # Try to connect
                return {
                    "status": "healthy",
                    "mode": "remote",
                    "host": client.ssh_config["host"],
                    "work_dir": client.work_dir,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "mode": "remote",
                "error": str(e),
            }
    
    async def annotate(
        self,
        sequence: str,
        organism: str = "Homo sapiens",
        progress_callback: Optional[Callable[[TaskProgress], None]] = None,
        **options
    ) -> Dict[str, Any]:
        """Annotate protein sequence with GO terms
        
        Args:
            sequence: Protein amino acid sequence
            organism: Organism name (default: Homo sapiens)
            progress_callback: Optional callback for progress updates
            **options: Additional options (reserved for future use)
            
        Returns:
            Dictionary containing:
                - success: Whether annotation succeeded
                - go_terms: GO annotations by category (MF, BP, CC)
                - metadata: Additional metadata
                
        Raises:
            ValueError: If sequence is invalid
            RuntimeError: If annotation fails
        """
        if not sequence or not sequence.strip():
            raise ValueError("Sequence cannot be empty")
        
        if self.use_remote:
            # Use real SSH + Celery integration
            result = await self._celery_client.annotate(
                sequence=sequence,
                organism=organism,
                progress_callback=progress_callback,
            )
            return result
        else:
            # Mock mode for testing
            return self._mock_annotate(sequence, organism)
    
    def _mock_annotate(self, sequence: str, organism: str) -> Dict[str, Any]:
        """Mock annotation for testing
        
        Args:
            sequence: Protein sequence
            organism: Organism name
            
        Returns:
            Mock annotation result
        """
        return {
            "success": True,
            "go_terms": {
                "MF": [
                    {"id": "GO:0003824", "name": "catalytic activity", "score": 0.95}
                ],
                "BP": [
                    {"id": "GO:0008152", "name": "metabolic process", "score": 0.92}
                ],
                "CC": [
                    {"id": "GO:0005737", "name": "cytoplasm", "score": 0.85}
                ],
            },
            "metadata": {
                "mode": "mock",
                "organism": organism,
                "sequence_length": len(sequence),
            },
        }
