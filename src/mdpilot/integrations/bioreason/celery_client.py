"""BioReason-Pro Celery client with SSH connection management"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import asyncssh

from mdpilot.types import TaskProgress, ProgressStage

logger = logging.getLogger(__name__)
# Global semaphore to limit concurrent GPU queries across all instances
_GPU_QUERY_SEMAPHORE = asyncio.Semaphore(2)


class BioreasonCeleryClient:
    """Client for BioReason-Pro via SSH + Celery"""
    
    def __init__(
        self,
        ssh: Dict[str, Any],
        celery: Dict[str, Any],
        work_dir: str,
        conda_env: str,
    ):
        """
        Initialize BioReason Celery client
        
        Args:
            ssh: SSH configuration (host, port, username, key_path, timeout)
            celery: Celery configuration (broker_url, backend_url, task_timeout, poll_interval)
            work_dir: Remote working directory
            conda_env: Conda environment name
        """
        self.ssh_config = ssh
        self.celery_config = celery
        self.work_dir = work_dir
        self.conda_env = conda_env
        self._conn: Optional[asyncssh.SSHClientConnection] = None
    
    async def connect(self) -> None:
        """Establish SSH connection to remote server"""
        if self._conn is not None:
            return
        
        logger.info(f"Connecting to {self.ssh_config['host']}...")
        
        key_path = str(Path(self.ssh_config["key_path"]).expanduser())
        connect_kwargs: Dict[str, Any] = {
            "host": self.ssh_config["host"],
            "username": self.ssh_config["username"],
            "client_keys": [key_path],
            "known_hosts": None,
        }
        if self.ssh_config.get("port") not in (None, 22):
            connect_kwargs["port"] = self.ssh_config["port"]
        self._conn = await asyncssh.connect(**connect_kwargs)
        
        logger.info("SSH connection established")
    
    async def disconnect(self) -> None:
        """Close SSH connection"""
        if self._conn is not None:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None
            logger.info("SSH connection closed")
    
    async def _submit_task(self, sequence: str, organism: str, output_dir: Optional[str] = None) -> str:
        """
        Submit BioReason task to Celery
        
        Args:
            sequence: Protein sequence
            organism: Organism name
            output_dir: Optional output directory for results
            
        Returns:
            Task ID
        """
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        
        output_arg = f", '{output_dir}'" if output_dir else ""
        cmd = f"""
cd {self.work_dir} && \
source /home/6-FF/luo/miniconda/etc/profile.d/conda.sh && \
conda activate {self.conda_env} && \
python -c "
from celery_tasks import run_bioreason_task
result = run_bioreason_task.delay('{sequence}', '{organism}'{output_arg})
print(result.id)
"
"""
        
        result = await self._conn.run(cmd, check=False)
        if result.exit_status != 0:
            raise RuntimeError(
                f"Remote command failed (exit {result.exit_status}): {result.stderr.strip()}"
            )
        task_id = result.stdout.strip()

        logger.info(f"Task submitted: {task_id}")
        return task_id
    
    async def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Query task status from Celery backend with GPU query rate limiting

        Args:
         task_id: Celery task ID

        Returns:
            Task status dict with 'state' and optional 'result'
        """
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")

        # Rate limit GPU queries to prevent driver overload
        async with _GPU_QUERY_SEMAPHORE:
            cmd = f"""
cd {self.work_dir} && \
source /home/6-FF/luo/miniconda/etc/profile.d/conda.sh && \
conda activate {self.conda_env} && \
python -c "
from celery_tasks import app
result = app.AsyncResult('{task_id}')
import json
print(json.dumps({{'state': result.state, 'result': result.result if result.ready() else None}}))
"
"""

            result = await self._conn.run(cmd, check=False)
            if result.exit_status != 0:
                raise RuntimeError(
                    f"Status query failed (exit {result.exit_status}): {result.stderr.strip()}"
                )
            status = json.loads(result.stdout.strip())

            return status
    
    async def _poll_task(
        self,
        task_id: str,
        progress_callback: Optional[Callable[[TaskProgress], None]] = None,
    ) -> Dict[str, Any]:
        """
        Poll task until completion
        
        Args:
            task_id: Celery task ID
            progress_callback: Optional callback for progress updates
            
        Returns:
            Final task result
        """
        poll_interval = self.celery_config.get("poll_interval", 2)
        timeout = self.celery_config.get("task_timeout", 300)
        elapsed = 0
        
        while elapsed < timeout:
            status = await self._get_task_status(task_id)
            state = status["state"]
            
            # Map Celery state to progress stage
            if state == "PENDING":
                stage = ProgressStage.PREPARING
                percent = 25
            elif state == "STARTED":
                stage = ProgressStage.EXECUTING
                percent = 50
            elif state == "SUCCESS":
                stage = ProgressStage.COMPLETED
                percent = 100
            elif state == "FAILURE":
                stage = ProgressStage.FAILED
                percent = 0
            else:
                stage = ProgressStage.PARSING
                percent = 75
            
            if progress_callback:
                progress = TaskProgress(
                    task_id=task_id,
                    stage=stage,
                    current_step=1,
                    total_steps=4,
                    percent=percent,
                    message=f"Task {state.lower()}",
                    timestamp=datetime.now(),
                )
                await progress_callback(progress)
            
            if state in ("SUCCESS", "FAILURE"):
                return status["result"]
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")
    
    async def annotate(
        self,
        sequence: str,
        organism: str,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[TaskProgress], None]] = None,
    ) -> Dict[str, Any]:
        """
        Annotate protein sequence with GO terms
        
        Args:
            sequence: Protein sequence
            organism: Organism name
            output_dir: Optional output directory for results
            progress_callback: Optional callback for progress updates
            
        Returns:
            Annotation result with GO terms
        """
        if not sequence or not sequence.strip():
            raise ValueError("sequence must not be empty")

        await self.connect()
        
        try:
            # Submit task
            if progress_callback:
                await progress_callback(TaskProgress(
                    task_id="pending",
                    stage=ProgressStage.PREPARING,
                    current_step=1,
                    total_steps=4,
                    percent=25,
                    message="Submitting task to Celery",
                    timestamp=datetime.now(),
                ))
            
            task_id = await self._submit_task(sequence, organism, output_dir)
            
            # Poll for completion
            result = await self._poll_task(task_id, progress_callback)
            
            return result
        
        finally:
            await self.disconnect()
    
    async def get_queue_length(self) -> int:
        """Query the number of pending tasks in the Celery queue via Redis."""
        await self.connect()
        broker_url = self.celery_config.get("broker_url", "redis://localhost:6379/0")
        result = await self._conn.run(
            f"redis-cli -u {broker_url} LLEN celery",
            check=False,
        )
        try:
            return int(result.stdout.strip())
        except (ValueError, AttributeError):
            return 0

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
