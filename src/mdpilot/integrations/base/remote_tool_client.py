"""Base class for remote tool clients using SSH + Celery"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import asyncssh

logger = logging.getLogger(__name__)


class BaseRemoteToolClient:
    """Base class for remote tool clients using SSH + Celery
    
    This class provides common functionality for tools that run on remote
    servers via SSH and use Celery for task management.
    """
    
    def __init__(
        self,
        ssh: Dict[str, Any],
        celery: Dict[str, Any],
        work_dir: str,
        conda_env: str,
    ):
        """Initialize base remote tool client
        
        Args:
            ssh: SSH configuration (host, port, username, key_path)
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
            logger.debug("Already connected")
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
    
    async def _run_command(self, cmd: str, check: bool = True) -> asyncssh.SSHCompletedProcess:
        """Execute command on remote server
        
        Args:
            cmd: Command to execute
            check: Raise exception if command fails
            
        Returns:
            SSH completed process result
            
        Raises:
            RuntimeError: If not connected
            asyncssh.ProcessError: If command fails and check=True
        """
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        
        logger.debug(f"Executing command: {cmd[:100]}...")
        return await self._conn.run(cmd, check=check)
    
    async def _submit_celery_task(self, task_name: str, *args, **kwargs) -> str:
        """Submit task to Celery and return task ID
        
        Args:
            task_name: Name of the Celery task
            *args: Positional arguments for the task
            **kwargs: Keyword arguments for the task
            
        Returns:
            Task ID
        """
        # Build Python command to submit task
        args_str = ", ".join(repr(arg) for arg in args)
        kwargs_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())
        params = ", ".join(filter(None, [args_str, kwargs_str]))
        
        cmd = f"""
cd {self.work_dir} && \
source ~/miniconda3/etc/profile.d/conda.sh && \
conda activate {self.conda_env} && \
python -c "
from celery_tasks_alphafold2 import {task_name}
result = {task_name}.delay({params})
print(result.id)
"
"""
        
        result = await self._run_command(cmd)
        task_id = result.stdout.strip()
        
        logger.info(f"Task submitted: {task_id}")
        return task_id
    
    async def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Query task status from Celery backend
        
        Args:
            task_id: Task ID to query
            
        Returns:
            Task status dictionary
        """
        cmd = f"""
cd {self.work_dir} && \
source ~/miniconda3/etc/profile.d/conda.sh && \
conda activate {self.conda_env} && \
python -c "
from celery.result import AsyncResult
from celery_tasks_alphafold2 import app
result = AsyncResult('{task_id}', app=app)
import json
print(json.dumps({{
    'state': result.state,
    'info': result.info if result.info else {{}},
    'ready': result.ready(),
    'successful': result.successful() if result.ready() else False
}}))
"
"""
        
        result = await self._run_command(cmd)
        import json
        return json.loads(result.stdout)
    
    async def _wait_for_task(
        self,
        task_id: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Wait for task to complete with optional progress updates
        
        Args:
            task_id: Task ID to wait for
            progress_callback: Optional callback for progress updates
            
        Returns:
            Task result
        """
        poll_interval = self.celery_config.get("poll_interval", 5)
        timeout = self.celery_config.get("task_timeout", 14400)
        elapsed = 0
        
        while elapsed < timeout:
            status = await self._get_task_status(task_id)
            
            # Call progress callback if provided
            if progress_callback and status["state"] == "PROGRESS":
                await progress_callback(status["info"])
            
            # Check if task is complete
            if status["ready"]:
                if status["successful"]:
                    return status["info"]
                else:
                    raise RuntimeError(f"Task failed: {status['info']}")
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds")
