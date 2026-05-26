"""Frontend contract compatibility routes."""
import asyncio
import socket
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import httpx
import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.api.auth import verify_token
from mdpilot.config.defaults import DEFAULT_ALPHAFOLD2_REMOTE, DEFAULT_BIOREASON_REMOTE, DEFAULT_LAB03_REMOTE
from mdpilot.config.loader import load_config
from mdpilot.database import get_session_dependency, get_session_factory
from mdpilot.database.models.chat import Chat as DBChat
from mdpilot.database.models.task import Task as DBTask
from mdpilot.database.repositories.chat import ChatRepository
from mdpilot.database.repositories.message import MessageRepository
from mdpilot.database.repositories.task import TaskRepository
from mdpilot.integrations.alphafold2 import AlphaFold2CeleryClient
from mdpilot.integrations.bioreason_client import BioreasonClient

router = APIRouter(prefix="/api", tags=["frontend"], dependencies=[Depends(verify_token)])


class FrontendChatCreate(BaseModel):
    title: str


class FrontendChatPatch(BaseModel):
    title: str


class FrontendChat(BaseModel):
    id: str
    title: str
    createdAt: datetime
    updatedAt: datetime


class FrontendMessagePage(BaseModel):
    items: list[dict[str, Any]]
    nextCursor: Optional[str] = None


class FrontendTask(BaseModel):
    id: str
    chatId: str
    kind: str
    status: str
    progress: int
    startedAt: Optional[datetime] = None
    finishedAt: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None


class LlmSettings(BaseModel):
    endpoint: str
    apiToken: Optional[str] = None
    model: str
    temperature: float
    maxTokens: int


class FrontendSettings(BaseModel):
    llm: LlmSettings


class FrontendSettingsPatch(BaseModel):
    llm: Optional[LlmSettings] = None


class BioReasonSubmit(BaseModel):
    sequence: str
    organism: str = "Homo sapiens"


class AlphaFold2Submit(BaseModel):
    sequence: str
    jobName: str = "prediction"
    dbPreset: str = "reduced_dbs"


@router.get("/chats", response_model=list[FrontendChat])
async def list_chats(db_session: AsyncSession = Depends(get_session_dependency)) -> list[FrontendChat]:
    result = await db_session.execute(select(DBChat).order_by(desc(DBChat.updated_at)))
    return [_map_chat(chat) for chat in result.scalars().all()]


@router.post("/chats", response_model=FrontendChat, status_code=201)
async def create_chat(
    body: FrontendChatCreate,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> FrontendChat:
    repo = ChatRepository(db_session)
    chat = await repo.create({"title": body.title, "extra_data": {}})
    await db_session.commit()
    return _map_chat(chat)


@router.patch("/chats/{chat_id}", response_model=FrontendChat)
async def update_chat(
    chat_id: str,
    body: FrontendChatPatch,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> FrontendChat:
    repo = ChatRepository(db_session)
    chat = await repo.update(UUID(chat_id), {"title": body.title})
    if chat is None:
        raise HTTPException(status_code=404, detail="chat not found")
    await db_session.commit()
    return _map_chat(chat)


@router.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> None:
    repo = ChatRepository(db_session)
    deleted = await repo.delete(UUID(chat_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="chat not found")
    await db_session.commit()


@router.get("/chats/{chat_id}/messages", response_model=FrontendMessagePage)
async def list_messages(
    chat_id: str,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> FrontendMessagePage:
    chat_repo = ChatRepository(db_session)
    chat = await chat_repo.get_by_id(UUID(chat_id))
    if chat is None:
        raise HTTPException(status_code=404, detail="chat not found")

    message_repo = MessageRepository(db_session)
    messages = await message_repo.get_by_chat_id(UUID(chat_id))
    return FrontendMessagePage(
        items=[
            {
                "id": str(message.id),
                "chatId": str(message.chat_id),
                "role": message.role,
                "content": message.content,
                "createdAt": message.created_at.isoformat(),
                **({
                    k: message.extra_data[k]
                    for k in ("agentBlocks", "interrupted", "reasoning")
                    if k in message.extra_data
                } if message.extra_data else {}),
            }
            for message in messages
        ],
        nextCursor=None,
    )


@router.get("/settings", response_model=FrontendSettings)
async def get_frontend_settings() -> FrontendSettings:
    return _settings_from_config()


@router.patch("/settings", response_model=FrontendSettings)
async def update_frontend_settings(body: FrontendSettingsPatch) -> FrontendSettings:
    if body.llm is not None:
        _write_user_llm_settings(body.llm)
    return _settings_from_config()


@router.post("/llm/chat/completions")
async def proxy_llm_chat_completions(body: dict[str, Any]) -> Response:
    settings = _settings_from_config().llm
    if not settings.endpoint or not settings.model:
        raise HTTPException(status_code=400, detail="LLM endpoint and model are required")

    headers = {"Content-Type": "application/json"}
    if settings.apiToken:
        headers["Authorization"] = f"Bearer {settings.apiToken}"

    payload = {**body, "model": settings.model}
    url = _llm_chat_completions_url(settings.endpoint)

    if not payload.get("stream"):
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(url, headers=headers, json=payload)
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type", "application/json"),
        )

    client = httpx.AsyncClient(timeout=None)
    request = client.build_request("POST", url, headers=headers, json=payload)
    response = await client.send(request, stream=True)
    if response.status_code >= 400:
        content = await response.aread()
        await response.aclose()
        await client.aclose()
        return Response(
            content=content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type", "application/json"),
        )

    async def stream_response():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(stream_response(), media_type=response.headers.get("content-type", "text/event-stream"))


@router.get("/tasks", response_model=list[FrontendTask])
async def list_frontend_tasks(
    status: Optional[str] = None,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> list[FrontendTask]:
    query = select(DBTask).order_by(desc(DBTask.updated_at))
    if status:
        query = query.where(DBTask.status == status)
    result = await db_session.execute(query)
    return [_map_task(task) for task in result.scalars().all()]


@router.get("/tasks/{task_id}", response_model=FrontendTask)
async def get_frontend_task(
    task_id: str,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> FrontendTask:
    repo = TaskRepository(db_session)
    task = await repo.get_by_id(UUID(task_id))
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return _map_task(task)


@router.post("/tools/bioreason", response_model=FrontendTask, status_code=201)
async def submit_bioreason(
    body: BioReasonSubmit,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> FrontendTask:
    if not body.sequence.strip():
        raise HTTPException(status_code=400, detail="sequence must not be empty")

    repo = TaskRepository(db_session)
    task = await repo.create({
        "task_type": "bioreason",
        "parameters": body.model_dump(),
        "user_id": "frontend",
        "status": "pending",
        "progress_percentage": 0.0,
        "current_stage": "queued",
    })
    await db_session.commit()
    asyncio.create_task(_run_bioreason_task(str(task.id), body))
    return _map_task(task)


@router.post("/tools/alphafold2", response_model=FrontendTask, status_code=201)
async def submit_alphafold2(
    body: AlphaFold2Submit,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> FrontendTask:
    if not body.sequence.strip():
        raise HTTPException(status_code=400, detail="sequence must not be empty")

    repo = TaskRepository(db_session)
    task = await repo.create({
        "task_type": "alphafold2",
        "parameters": body.model_dump(),
        "user_id": "frontend",
        "status": "pending",
        "progress_percentage": 0.0,
        "current_stage": "queued",
    })
    await db_session.commit()
    asyncio.create_task(_run_alphafold2_task(str(task.id), body))
    return _map_task(task)


@router.get("/nodes")
async def list_nodes() -> list[dict[str, Any]]:
    now = datetime.utcnow().isoformat() + "Z"
    lab03_config = _lab03_remote_config()
    nodes = [
        {"id": "lab02", "host": DEFAULT_ALPHAFOLD2_REMOTE["ssh"]["host"]},
        {"id": "lab06", "host": DEFAULT_BIOREASON_REMOTE["ssh"]["host"]},
        {"id": "lab03", "host": lab03_config["ssh"]["host"]},
    ]

    results = await asyncio.gather(
        *(_collect_node_gpus(node["id"], node["host"]) for node in nodes),
        return_exceptions=True,
    )

    response = []
    for node, result in zip(nodes, results):
        node_status: dict[str, Any] = {"id": node["id"], "online": False, "queueDepth": 0, "lastSeen": now}
        if not isinstance(result, Exception):
            node_status["online"] = True
            if result:
                node_status["gpu"] = result[0]
                node_status["gpus"] = result
        response.append(node_status)

    return response


async def _collect_node_gpus(node_id: str, host: str) -> list[dict[str, Any]]:
    command = "timeout 5 nvidia-smi --query-gpu=index,name,memory.used,memory.total,temperature.gpu,utilization.gpu,power.draw,power.limit --format=csv,noheader,nounits"
    if _should_collect_locally(node_id, host):
        process = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=index,name,memory.used,memory.total,temperature.gpu,utilization.gpu,power.draw,power.limit",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        process = await asyncio.create_subprocess_exec(
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            host,
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
    except asyncio.TimeoutError:
        # Kill the process if it times out to prevent zombie processes
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
        raise RuntimeError(f"{node_id} GPU telemetry timed out after 10s")
    if process.returncode != 0:
        detail = stderr.decode(errors="replace").strip()
        raise RuntimeError(f"{node_id} GPU telemetry failed: {detail or process.returncode}")
    return _parse_nvidia_smi_output(stdout.decode())


def _should_collect_locally(node_id: str, host: str) -> bool:
    lab03_hosts = {"lab03", "lab-03"}
    return node_id == "lab03" and host.lower() in lab03_hosts and socket.gethostname().lower() in lab03_hosts


def _parse_nvidia_smi_output(output: str) -> list[dict[str, Any]]:
    """Parse nvidia-smi CSV output into GPU info dicts.

    Expected fields: index, name, memory.used, memory.total,
                     temperature.gpu, utilization.gpu, power.draw, power.limit
    """
    gpus = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 8:
            continue
        try:
            gpus.append({
                "id": parts[0],
                "model": parts[1],
                "usedMB": int(parts[2]),
                "totalMB": int(parts[3]),
                "tempC": int(parts[4]),
                "utilization": int(parts[5]),
                "powerDraw": float(parts[6]),
                "powerLimit": float(parts[7]),
            })
        except (ValueError, IndexError):
            continue
    return gpus


@router.get("/health")
async def frontend_health() -> dict[str, Any]:
    return {"status": "ok", "commit": "local", "uptimeSec": 0}


async def _update_task(task_id: str, **data: Any) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = TaskRepository(session)
        await repo.update(UUID(task_id), data)
        await session.commit()


async def _run_bioreason_task(task_id: str, body: BioReasonSubmit) -> None:
    await _update_task(task_id, status="running", progress_percentage=10.0, current_stage="connecting lab06")
    try:
        client = BioreasonClient(config=_bioreason_remote_config(), use_remote=True)
        result = await client.annotate(body.sequence, body.organism)
        await _update_task(
            task_id,
            status="completed",
            progress_percentage=100.0,
            current_stage="completed",
            result=result,
        )
    except Exception as e:
        await _update_task(task_id, status="failed", progress_percentage=10.0, current_stage="failed", error=str(e))


async def _run_alphafold2_task(task_id: str, body: AlphaFold2Submit) -> None:
    await _update_task(task_id, status="running", progress_percentage=10.0, current_stage="connecting lab02")
    try:
        async with AlphaFold2CeleryClient(**_alphafold2_remote_config()) as client:
            result = await client.predict(body.sequence, body.jobName, db_preset=body.dbPreset)
        await _update_task(
            task_id,
            status="completed",
            progress_percentage=100.0,
            current_stage="completed",
            result=result,
        )
    except Exception as e:
        await _update_task(task_id, status="failed", progress_percentage=10.0, current_stage="failed", error=str(e))


def _llm_chat_completions_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return f"{base}/v1/chat/completions"


def _settings_from_config() -> FrontendSettings:
    config = load_config()
    provider = config.provider
    user_provider = _read_user_config().get("provider", {})
    api_token = user_provider.get("api_key") or (provider.api_key.get_secret_value() if provider.api_key else None)
    return FrontendSettings(
        llm=LlmSettings(
            endpoint=user_provider.get("base_url") or provider.base_url or "",
            apiToken=api_token,
            model=user_provider.get("model") or provider.model,
            temperature=user_provider.get("temperature", provider.temperature),
            maxTokens=user_provider.get("max_tokens", provider.max_tokens),
        )
    )


def _read_user_config() -> dict[str, Any]:
    config_path = Path.home() / ".mdpilot" / "config.yaml"
    if not config_path.exists():
        return {}
    loaded = yaml.safe_load(config_path.read_text())
    return loaded if isinstance(loaded, dict) else {}


def _write_user_llm_settings(settings: LlmSettings) -> None:
    config_path = Path.home() / ".mdpilot" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_user_config()

    provider = data.setdefault("provider", {})
    provider.update(
        {
            "base_url": settings.endpoint,
            "model": settings.model,
            "temperature": settings.temperature,
            "max_tokens": settings.maxTokens,
        }
    )
    if settings.apiToken is not None:
        provider["api_key"] = settings.apiToken

    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _bioreason_remote_config() -> dict[str, Any]:
    config = load_config()
    if config.bioreason_remote is None:
        return DEFAULT_BIOREASON_REMOTE
    return config.bioreason_remote.model_dump()


def _alphafold2_remote_config() -> dict[str, Any]:
    config = load_config()
    if config.alphafold2_remote is None:
        return DEFAULT_ALPHAFOLD2_REMOTE
    return config.alphafold2_remote.model_dump()


def _lab03_remote_config() -> dict[str, Any]:
    config = load_config()
    if config.lab03_remote is None:
        return DEFAULT_LAB03_REMOTE
    return config.lab03_remote.model_dump()


def _map_chat(chat: DBChat) -> FrontendChat:
    return FrontendChat(
        id=str(chat.id),
        title=chat.title,
        createdAt=chat.created_at,
        updatedAt=chat.updated_at,
    )


def _map_task(task: DBTask) -> FrontendTask:
    metadata = task.extra_data or {}
    progress = task.progress_percentage
    if progress is None:
        progress = metadata.get("progress_percentage", 100 if task.status == "succeeded" else 0)
    return FrontendTask(
        id=str(task.id),
        chatId=str(task.chat_id) if task.chat_id else str(metadata.get("agent_session_id", "workspace")),
        kind=_map_task_kind(task.task_type),
        status=_map_task_status(task.status),
        progress=int(progress or 0),
        startedAt=task.created_at,
        finishedAt=task.updated_at if task.status in {"succeeded", "failed", "cancelled"} else None,
        error=task.error,
        result=task.result,
    )


def _map_task_kind(task_type: str) -> str:
    if task_type in {"alphafold2", "amber_md", "mmpbsa", "bioreason", "report"}:
        return task_type
    if task_type == "agent_execution":
        return "report"
    return "report"


def _map_task_status(status: str) -> str:
    return {
        "completed": "succeeded",
        "success": "succeeded",
        "running": "running",
        "pending": "pending",
        "failed": "failed",
        "cancelled": "cancelled",
    }.get(status, status)
