"""WebSocket logs handler."""
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class LogsConnectionManager:
    """Manage WebSocket connections for task logs."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        """Connect a client to a task's logs."""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str):
        """Disconnect a client from a task's logs."""
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

    async def send_log(self, log: dict[str, Any], websocket: WebSocket):
        """Send a log message to a specific client."""
        await websocket.send_json(log)

    async def broadcast_log(self, log: dict[str, Any], task_id: str):
        """Broadcast a log message to all clients watching a task."""
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                await connection.send_json(log)


logs_manager = LogsConnectionManager()


async def logs_websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for task logs."""
    await logs_manager.connect(websocket, task_id)
    try:
        # Send connection confirmation
        await logs_manager.send_log(
            {
                "type": "connection",
                "message": f"Connected to logs for task: {task_id}",
            },
            websocket,
        )

        # Keep connection alive and wait for logs
        # In a real implementation, logs would be pushed from the task execution
        while True:
            # Wait for any client messages (e.g., ping/pong)
            await websocket.receive_text()

    except WebSocketDisconnect:
        logs_manager.disconnect(websocket, task_id)
