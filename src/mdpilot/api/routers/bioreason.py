import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from mdpilot.api.auth import verify_token
from ...integrations.bioreason_client import BioreasonClient
from ...types import TaskProgress

router = APIRouter(
    prefix="/api/v1/bioreason",
    tags=["bioreason"],
    dependencies=[Depends(verify_token)]
)

_client = BioreasonClient(use_remote=True)

@router.post("/annotate")
async def annotate_protein(
    sequence: str,
    organism: str = "Homo sapiens"
) -> dict:
    try:
        _ = asyncio.create_task(
            _client.annotate(sequence, organism)
        )
        
        return {
            "task_id": "temp-task-id",
            "status": "submitted",
            "message": "任务已提交，请通过 WebSocket 监听进度"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    
    try:
        async def progress_callback(progress: TaskProgress):
            await websocket.send_text(json.dumps(progress.to_dict()))
        
        result = await _client.annotate(
            sequence="MVLSPADKTN",
            organism="Homo sapiens",
            progress_callback=progress_callback
        )
        
        await websocket.send_text(json.dumps({
            "task_id": task_id,
            "stage": "completed",
            "percent": 100,
            "result": result
        }))
        
    except WebSocketDisconnect:
        print(f"WebSocket 断开: {task_id}")
    except Exception as e:
        await websocket.send_text(json.dumps({
            "task_id": task_id,
            "stage": "failed",
            "error": str(e)
        }))
    finally:
        await websocket.close()
