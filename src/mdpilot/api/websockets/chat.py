"""WebSocket chat handler with LLM integration"""
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from mdpilot.api.services.agent_service import AgentService


class ConnectionManager:
    """Manage WebSocket connections for chat sessions"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.agent_service = AgentService()

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                self.agent_service.cleanup_agent(session_id)

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict[str, Any], session_id: str):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                await connection.send_json(message)


manager = ConnectionManager()


async def chat_websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for chat sessions with LLM integration"""
    await manager.connect(websocket, session_id)
    try:
        await manager.send_personal_message(
            {
                "type": "connection",
                "message": f"Connected to chat session: {session_id}",
            },
            websocket,
        )

        while True:
            data = await websocket.receive_json()

            if "type" not in data or data["type"] != "message":
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": "Invalid message format. Expected 'type': 'message'",
                    },
                    websocket,
                )
                continue

            if "content" not in data or "role" not in data:
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": "Missing 'content' or 'role' in message",
                    },
                    websocket,
                )
                continue

            if data["role"] == "user":
                await manager.broadcast(
                    {
                        "type": "message",
                        "content": data["content"],
                        "role": "user",
                        "session_id": session_id,
                    },
                    session_id,
                )
                
                async for event in manager.agent_service.execute_with_stream(
                    session_id=session_id,
                    prompt=data["content"]
                ):
                    await manager.broadcast(event, session_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    finally:
        await manager.agent_service.save_agent_state(session_id)
