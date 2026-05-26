"""AlphaFold2 Celery client with SSH connection management"""

import logging
from datetime import datetime
from typing import Optional, Callable, Dict, Any

from ..base.remote_tool_client import BaseRemoteToolClient
from ...types import TaskProgress, ProgressStage

logger = logging.getLogger(__name__)


class AlphaFold2CeleryClient(BaseRemoteToolClient):
    """Client for AlphaFold2 via SSH + Celery."""
    
    async def predict(
        self,
        sequence: str,
        job_name: str = "prediction",
        output_dir: Optional[str] = None,
        db_preset: str = "reduced_dbs",
        progress_callback: Optional[Callable[[TaskProgress], None]] = None
    ) -> Dict[str, Any]:
        """Predict protein structure using AlphaFold2
        
        Args:
            sequence: Protein amino acid sequence
            job_name: Job name for output files
            output_dir: Output directory path (optional, uses default if not provided)
            db_preset: Database preset ('reduced_dbs', 'full_dbs', 'casp14')
            progress_callback: Optional callback for progress updates
            
        Returns:
            Prediction result dictionary with keys:
                - success: bool
                - job_name: str
                - sequence_length: int
                - best_model: str (path to best PDB file)
                - avg_plddt: float (average confidence score)
                - output_dir: str (output directory path)
                - num_models: int (number of models generated)
                - db_preset: str (database preset used)
                
        Raises:
            RuntimeError: If prediction fails
            TimeoutError: If prediction times out
        """
        if callable(output_dir) and progress_callback is None:
            progress_callback = output_dir
            output_dir = None

        logger.info(f"Starting AlphaFold2 prediction for {job_name} ({len(sequence)} aa) with {db_preset}")

        task_kwargs = {"output_dir": output_dir} if output_dir else {}
        if db_preset != "reduced_dbs":
            task_kwargs["db_preset"] = db_preset

        task_id = await self._submit_celery_task(
            "predict_structure",
            sequence,
            job_name,
            **task_kwargs,
        )

        async def progress_wrapper(info: dict[str, Any]) -> None:
            if not progress_callback:
                return
            progress = TaskProgress(
                task_id=task_id,
                stage=self._map_progress_stage(info.get("stage")),
                current_step=info.get("current", 0),
                total_steps=info.get("total", 5),
                percent=info.get("percent", 0),
                message=info.get("message", ""),
                timestamp=datetime.now(),
            )
            result = progress_callback(progress)
            if hasattr(result, "__await__"):
                await result

        result = await self._wait_for_task(task_id, progress_wrapper if progress_callback else None)
        
        if not result.get("success"):
            error = result.get("error", "Unknown error")
            raise RuntimeError(f"AlphaFold2 prediction failed: {error}")
        
        result["db_preset"] = db_preset
        
        if "best_model" in result:
            logger.info(f"Prediction complete: {result['best_model']}")
        return result

    @staticmethod
    def _map_progress_stage(stage: str | None) -> ProgressStage:
        return {
            "preparing": ProgressStage.QUEUED,
            "running": ProgressStage.RUNNING,
            "processing": ProgressStage.PROCESSING,
            "parsing": ProgressStage.PROCESSING,
            "extracting": ProgressStage.PROCESSING,
            "analyzing": ProgressStage.PROCESSING,
            "completed": ProgressStage.COMPLETED,
        }.get(stage or "", ProgressStage.RUNNING)

    async def get_prediction_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a running prediction task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Task status dictionary
        """
        return await self._get_task_status(task_id)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
