"""Task management router."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.api.models.tasks import Task, TaskCreate, TaskList
from mdpilot.api.services.task_service import TaskService
from mdpilot.api.services.background_executor import BackgroundExecutor
from mdpilot.api.services.agent_service import AgentService
from mdpilot.api.auth import verify_token
from mdpilot.database import get_session_dependency

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    dependencies=[Depends(verify_token)]
)


class AgentTaskRequest(BaseModel):
    """Request model for creating agent background task."""
    session_id: str
    prompt: str
    user_id: Optional[str] = None


@router.post("", response_model=Task)
async def create_task(
    task_data: TaskCreate,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> Task:
    """Create a new task."""
    service = TaskService(db_session)
    task = await service.create_task(
        task_type=task_data.task_type,
        parameters=task_data.parameters,
        user_id=task_data.user_id,
        metadata=task_data.metadata,
    )
    await db_session.commit()
    return task


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> Task:
    """Get task status by ID."""
    service = TaskService(db_session)
    task = await service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("", response_model=TaskList)
async def list_tasks(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> TaskList:
    """List tasks with optional filters and pagination."""
    service = TaskService(db_session)
    tasks, total = await service.list_tasks(
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return TaskList(
        tasks=tasks,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{task_id}/cancel", response_model=Task)
async def cancel_task(
    task_id: str,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> Task:
    """Cancel a task."""
    service = TaskService(db_session)
    task = await service.cancel_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await db_session.commit()
    return task


@router.post("/agent/execute", response_model=Task)
async def execute_agent_background(
    request: AgentTaskRequest,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> Task:
    """Execute agent task in background."""
    task_service = TaskService(db_session)
    agent_service = AgentService()
    
    executor = BackgroundExecutor(task_service, agent_service)
    task_id = await executor.submit_agent_task(
        session_id=request.session_id,
        prompt=request.prompt,
        user_id=request.user_id or "default"
    )
    
    task = await task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=500, detail="Failed to create task")
    
    return task
