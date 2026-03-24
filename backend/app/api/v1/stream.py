"""
Aegis Backend — WebSocket Stream

Provides real-time event streaming for the React Dashboard.
Clients can connect to this endpoint to receive live updates of metrics,
logs, and incidents.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger(__name__)

stream_router = APIRouter()

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        await logger.ainfo("websocket_client_connected", clients=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            # Cannot use await logger here synchronously easily, so use structlog sync bound
            logger.info("websocket_client_disconnected", clients=len(self.active_connections))

    async def broadcast(self, message_type: str, data: dict[str, Any]) -> None:
        if not self.active_connections:
            return
            
        payload = {"type": message_type, "data": data}
        for connection in list(self.active_connections):
            try:
                await connection.send_json(payload)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()


@stream_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Main WebSocket endpoint for the React frontend.
    The frontend simply connects and listens to broadcasts.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect the client to send much, but we keep the connection open
            # and respond to pings or commands if necessary.
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await logger.aerror("websocket_error", error=str(e))
        manager.disconnect(websocket)
