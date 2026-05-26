"""Background task executor for long-running agent tasks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mdpilot.api.services.agent_service import AgentService
from mdpilot.api.services.task_service import TaskService

logger = logging.getLogger(__name__)


class BackgroundExecutor:
    """Executes agent tasks in the background without blocking WebSocket."""
    
    def __init__(self, task_service: TaskService, agent_service: AgentService) -> None:
        self._task_service = task_service
        self._agent_service = agent_service
        self._running_tasks: dict[str, asyncio.Task] = {}
    
    async def submit_agent_task(
        self,
        session_id: str,
        prompt: str,
        user_id: str = "default"
    ) -> str:
        """Submit an agent execution task to run in background.
        
        Args:
            session_id: Agent session identifier
            prompt: User prompt to execute
            user_id: User identifier
            
        Returns:
            Task ID for tracking
        """
        task_id = await self._task_service.create_agent_task(
            session_id=session_id,
            prompt=prompt,
            user_id=user_id
        )
        
        asyncio_task = asyncio.create_task(
            self._execute_agent_task(task_id, session_id, prompt)
        )
        self._running_tasks[task_id] = asyncio_task
        
        asyncio_task.add_done_callback(
            lambda t: self._running_tasks.pop(task_id, None)
        )
        
        return task_id

    async def _execute_agent_task(
        self,
        task_id: str,
        session_id: str,
        prompt: str
    ) -> None:
        """Execute agent task with progress tracking."""
        try:
            await self._task_service.update_task_progress(
                task_id, 10.0, "initializing"
            )
            
            await self._task_service.update_task_status(
                task_id=task_id,
                status="running"
            )
            
            await self._task_service.update_task_progress(
                task_id, 30.0, "processing"
            )
            
            result_text = ""
            async for event in self._agent_service.execute_with_stream(session_id, prompt):
                event_type = event.get("type")
                
                if event_type == "progress_update":
                    progress = event.get("data", {}).get("percentage", 50.0)
                    await self._task_service.update_task_progress(
                        task_id, min(30.0 + progress * 0.6, 90.0), "processing"
                    )
                elif event_type == "complete":
                    result_text = event.get("data", {}).get("result", "")
            
            await self._task_service.update_task_progress(
                task_id, 95.0, "finalizing"
            )
            
            await self._task_service.update_task_status(
                task_id=task_id,
                status="completed",
                result={"response": result_text}
            )
            
            await self._task_service.update_task_progress(
                task_id, 100.0, "completed"
            )
            
            await self._agent_service.save_agent_state(session_id)
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            await self._task_service.update_task_status(
                task_id=task_id,
                status="failed",
                error=str(e)
            )

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get current task status.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status dict or None if not found
        """
        task = await self._task_service.get_task(task_id)
        if not task:
            return None
        
        return {
            "task_id": task.task_id,
            "status": task.status,
            "progress_percentage": task.metadata.get("progress_percentage", 0.0) if task.metadata else 0.0,
            "current_stage": task.metadata.get("current_stage", "unknown") if task.metadata else "unknown",
            "result": task.result,
            "error": task.error,
        }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if cancelled, False if not found
        """
        asyncio_task = self._running_tasks.get(task_id)
        if asyncio_task and not asyncio_task.done():
            asyncio_task.cancel()
        
        task = await self._task_service.cancel_task(task_id)
        return task is not None
