"""Database-backed task service."""
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.api.models.tasks import Task
from mdpilot.database.models.task import Task as DBTask
from mdpilot.database.repositories.task import TaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    """Database-backed task service for managing tasks."""

    def __init__(self, session: AsyncSession):
        """Initialize the task service.

        Args:
            session: The async database session to use for operations.
        """
        self.session = session
        self.task_repo = TaskRepository(session)

    async def create_task(
        self,
        task_type: str,
        parameters: dict,
        user_id: str,
        metadata: Optional[dict] = None,
    ) -> Task:
        """Create a new task.

        Args:
            task_type: The type of task to create.
            parameters: Task parameters.
            user_id: The user ID creating the task.
            metadata: Optional metadata for the task.

        Returns:
            The created task.

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            task_data = {
                "task_type": task_type,
                "parameters": parameters,
                "user_id": user_id,
                "status": "pending",
                "extra_data": metadata,
            }
            db_task = await self.task_repo.create(task_data)

            # Map DB model to API model
            return self._map_to_api_model(db_task)
        except SQLAlchemyError as e:
            logger.error(f"Failed to create task: {e}")
            raise

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.

        Args:
            task_id: The task ID to retrieve.

        Returns:
            The task if found, None otherwise.

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            db_task = await self.task_repo.get_by_id(UUID(task_id))
            if db_task is None:
                return None

            return self._map_to_api_model(db_task)
        except (ValueError, SQLAlchemyError) as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None

    async def list_tasks(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        """List tasks with optional filters and pagination.

        Args:
            user_id: Optional user ID filter.
            status: Optional status filter.
            limit: Maximum number of tasks to return.
            offset: Number of tasks to skip.

        Returns:
            Tuple of (tasks list, total count).

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            # Build query with filters
            query = select(DBTask)
            count_query = select(func.count()).select_from(DBTask)

            filters = []
            if user_id:
                filters.append(DBTask.user_id == user_id)
            if status:
                filters.append(DBTask.status == status)

            if filters:
                filter_condition = and_(*filters)
                query = query.where(filter_condition)
                count_query = count_query.where(filter_condition)

            # Apply ordering and pagination
            query = query.order_by(desc(DBTask.created_at)).offset(offset).limit(limit)

            # Execute queries
            result = await self.session.execute(query)
            db_tasks = list(result.scalars().all())

            count_result = await self.session.execute(count_query)
            total = count_result.scalar_one()

            # Map to API models
            api_tasks = [self._map_to_api_model(task) for task in db_tasks]

            return api_tasks, total
        except SQLAlchemyError as e:
            logger.error(f"Failed to list tasks: {e}")
            raise

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """Cancel a task.

        Args:
            task_id: The task ID to cancel.

        Returns:
            The updated task if found, None otherwise.

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            db_task = await self.task_repo.update_status(UUID(task_id), "cancelled")
            if db_task is None:
                return None

            return self._map_to_api_model(db_task)
        except (ValueError, SQLAlchemyError) as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            if isinstance(e, SQLAlchemyError):
                raise
            return None

    async def create_agent_task(
        self,
        session_id: str,
        prompt: str,
        user_id: str = "default"
    ) -> str:
        """Create a new agent execution task.
        
        Args:
            session_id: Agent session identifier
            prompt: User prompt to execute
            user_id: User identifier
            
        Returns:
            Task ID
        """
        task_data = {
            "task_type": "agent_execution",
            "parameters": {"prompt": prompt},
            "user_id": user_id,
            "status": "pending",
            "agent_session_id": session_id,
            "progress_percentage": 0.0,
            "current_stage": "initializing",
        }
        db_task = await self.task_repo.create(task_data)
        return str(db_task.id)

    async def update_task_progress(
        self,
        task_id: str,
        percentage: float,
        stage: str
    ) -> None:
        """Update task progress.
        
        Args:
            task_id: Task identifier
            percentage: Progress percentage (0-100)
            stage: Current stage description
        """
        try:
            db_task = await self.task_repo.get_by_id(UUID(task_id))
            if db_task:
                db_task.progress_percentage = percentage
                db_task.current_stage = stage
                await self.session.commit()
        except (ValueError, SQLAlchemyError) as e:
            logger.error(f"Failed to update task progress {task_id}: {e}")

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None
    ) -> None:
        """Update task status and optional result/error.
        
        Args:
            task_id: Task identifier
            status: New status
            result: Optional result data
            error: Optional error message
        """
        try:
            db_task = await self.task_repo.get_by_id(UUID(task_id))
            if db_task:
                db_task.status = status
                if result:
                    db_task.result = result
                if error:
                    db_task.error = error
                await self.session.commit()
        except (ValueError, SQLAlchemyError) as e:
            logger.error(f"Failed to update task status {task_id}: {e}")

    def _map_to_api_model(self, db_task: DBTask) -> Task:
        """Map database task model to API task model.

        Args:
            db_task: The database task model.

        Returns:
            The API task model.
        """
        return Task(
            task_id=str(db_task.id),
            task_type=db_task.task_type,
            parameters=db_task.parameters,
            user_id=db_task.user_id,
            status=db_task.status,
            created_at=db_task.created_at,
            updated_at=db_task.updated_at,
            result=db_task.result,
            error=db_task.error,
            metadata={
                **(db_task.extra_data or {}),
                "progress_percentage": db_task.progress_percentage,
                "current_stage": db_task.current_stage,
                "agent_session_id": db_task.agent_session_id,
            },
        )
