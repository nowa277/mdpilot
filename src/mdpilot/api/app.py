"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Query, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware

import mdpilot.database.models  # noqa: F401
from mdpilot.api.config import Settings
from mdpilot.api.middleware.logging import LoggingMiddleware
from mdpilot.api.routers import agent, alphafold2, bioreason, chat, frontend, health, tasks
from mdpilot.api.websockets.chat import chat_websocket_endpoint
from mdpilot.api.websockets.logs import logs_websocket_endpoint
from mdpilot.config.logging import configure_logging
from mdpilot.config.schema import DatabaseConfig
from mdpilot.config.settings import get_settings
from mdpilot.database import Base, dispose_engine, get_engine, get_session_factory, init_db
from mdpilot.database.repositories.task import TaskRepository

configure_logging()


async def _ensure_database_schema() -> None:
    """Create missing database tables without dropping existing data."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    settings = get_settings()
    db_config = DatabaseConfig(
        url=settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
    )
    init_db(db_config)
    await _ensure_database_schema()

    yield

    await dispose_engine()


def create_app():
    """Create and configure FastAPI application."""
    settings = Settings()

    fastapi_app = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    fastapi_app.add_middleware(LoggingMiddleware)

    fastapi_app.include_router(chat.router)
    fastapi_app.include_router(tasks.router)
    fastapi_app.include_router(health.router)
    fastapi_app.include_router(bioreason.router)
    fastapi_app.include_router(alphafold2.router)
    fastapi_app.include_router(agent.router)
    fastapi_app.include_router(frontend.router)

    @fastapi_app.websocket("/ws/chat/{session_id}")
    async def websocket_chat(websocket: WebSocket, session_id: str, token: str = Query(None)):
        """WebSocket endpoint for chat."""
        settings = get_settings()
        if settings.api_token is not None:
            expected_token = settings.api_token.get_secret_value()
            if token != expected_token:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        await chat_websocket_endpoint(websocket, session_id)

    @fastapi_app.websocket("/ws/logs/{task_id}")
    async def websocket_logs(websocket: WebSocket, task_id: str, token: str = Query(None)):
        """WebSocket endpoint for task logs."""
        settings = get_settings()
        if settings.api_token is not None:
            expected_token = settings.api_token.get_secret_value()
            if token != expected_token:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        await logs_websocket_endpoint(websocket, task_id)

    @fastapi_app.websocket("/ws/task/{task_id}")
    async def websocket_task_progress(websocket: WebSocket, task_id: str, token: str = Query(None)):
        """Frontend-compatible task progress stream."""
        settings = get_settings()
        if settings.api_token is not None:
            expected_token = settings.api_token.get_secret_value()
            if token != expected_token:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        await websocket.accept()
        last_status = None
        last_percent = None
        last_stage = None
        try:
            while True:
                session_factory = get_session_factory()
                async with session_factory() as session:
                    repo = TaskRepository(session)
                    task = await repo.get_by_id(UUID(task_id))
                if task is None:
                    await websocket.send_json({"type": "status", "status": "failed"})
                    await websocket.send_json(
                        {"type": "log_line", "level": "error", "line": "task not found", "ts": ""}
                    )
                    return
                frontend_status = {
                    "completed": "succeeded",
                    "success": "succeeded",
                }.get(task.status, task.status)
                percent = int(task.progress_percentage or 0)
                stage = task.current_stage or task.task_type
                if frontend_status != last_status:
                    await websocket.send_json({"type": "status", "status": frontend_status})
                    last_status = frontend_status
                if percent != last_percent or stage != last_stage:
                    await websocket.send_json(
                        {"type": "progress", "percent": percent, "stage": stage}
                    )
                    last_percent = percent
                    last_stage = stage
                if task.error:
                    await websocket.send_json(
                        {
                            "type": "log_line",
                            "level": "error",
                            "line": task.error,
                            "ts": str(task.updated_at),
                        }
                    )
                if task.status in {"completed", "failed", "cancelled"}:
                    return
                await asyncio.sleep(1)
        finally:
            await websocket.close()

    @fastapi_app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    @fastapi_app.get("/api/v1/version")
    async def version():
        """Get API version information."""
        return {
            "version": "1.0.0",
            "api_version": settings.api_version,
        }

    return CORSMiddleware(
        fastapi_app,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app = create_app()
