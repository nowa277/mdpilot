"""
WebSocket client for MDPilot TUI.

Handles real-time communication with backend.
"""
import asyncio
import json
from typing import AsyncGenerator, Optional, Dict, Any
import websockets
from websockets.client import WebSocketClientProtocol


class WebSocketClient:
    """
    Async WebSocket client for LLM streaming.
    
    Features:
    - Connect to backend WebSocket endpoint
    - Send user messages
    - Receive streaming responses
    - Auto-reconnect on disconnect
    """
    
    def __init__(self, url: str = "ws://localhost:8000/ws"):
        """
        Initialize WebSocket client.
        
        Args:
            url: WebSocket endpoint URL
        """
        self.url = url
        self.ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """
        Connect to WebSocket endpoint.
        
        Returns:
            True if connected successfully
        """
        try:
            self.ws = await websockets.connect(self.url)
            self._connected = True
            return True
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self._connected = False
            return False
    
    async def send(self, message: str, session_id: Optional[str] = None) -> None:
        """
        Send message to backend.
        
        Args:
            message: User message content
            session_id: Optional session ID for context
        """
        if not self.ws or not self._connected:
            raise RuntimeError("WebSocket not connected")
        
        payload = {
            "type": "message",
            "content": message,
            "session_id": session_id,
        }
        
        await self.ws.send(json.dumps(payload))
    
    async def receive(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Receive streaming responses.
        
        Yields:
            Message chunks as dicts
        """
        if not self.ws or not self._connected:
            raise RuntimeError("WebSocket not connected")
        
        try:
            async for message in self.ws:
                data = json.loads(message)
                yield data
        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            raise
    
    async def close(self) -> None:
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self._connected = False
    
    @property
    def connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected
