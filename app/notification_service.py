import asyncio
from typing import Dict, List, Optional
from fastapi import WebSocket
from sqlalchemy.orm import Session
from app.models import User, Notification
from app.month_utils import get_current_local_now

class ConnectionManager:
    def __init__(self):
        # Maps user_id -> List[WebSocket]
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_json(self, data: dict, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(data)
                except Exception:
                    pass

    async def broadcast_json(self, data: dict):
        for user_id, connections in list(self.active_connections.items()):
            for connection in list(connections):
                try:
                    await connection.send_json(data)
                except Exception:
                    pass

manager = ConnectionManager()

def create_and_broadcast_notification(
    db: Session,
    title: str,
    message: str,
    notification_type: str = "SYSTEM"
):
    """
    Creates persistent notification DB records for all active users
    and broadcasts the notification in real-time over WebSockets.
    """
    active_users = db.query(User).filter(User.is_active == True).all()
    now = get_current_local_now()

    for user in active_users:
        notif = Notification(
            user_id=user.id,
            title=title,
            message=message,
            type=notification_type,
            is_read=False,
            created_at=now
        )
        db.add(notif)

    db.commit()

    payload = {
        "event": "NOTIFICATION",
        "title": title,
        "message": message,
        "type": notification_type,
        "created_at": now.isoformat()
    }

    # Schedule WebSocket broadcast in current event loop if running
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast_json(payload))
    except RuntimeError:
        # Fallback if outside running async loop
        asyncio.run(manager.broadcast_json(payload))
