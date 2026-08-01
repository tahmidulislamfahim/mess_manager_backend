import asyncio
from typing import Optional
from sqlalchemy.orm import Session
from app.models import User, Notification
from app.month_utils import get_current_local_now
from app.socketio_server import sio

# Reference to main event loop
_main_loop: Optional[asyncio.AbstractEventLoop] = None

def set_main_loop(loop: asyncio.AbstractEventLoop):
    global _main_loop
    _main_loop = loop

async def _emit_notification_to_user(user_id: int, notif_payload: dict, unread_count: int):
    # Emit new notification event to specific user room
    await sio.emit("new_notification", notif_payload, room=f"user_{user_id}")
    # Emit updated unread count event to specific user room
    await sio.emit("unread_count_updated", {"unread_count": unread_count}, room=f"user_{user_id}")

async def _emit_unread_count_to_user(user_id: int, unread_count: int):
    await sio.emit("unread_count_updated", {"unread_count": unread_count}, room=f"user_{user_id}")

def create_and_broadcast_notification(
    db: Session,
    title: str,
    message: str,
    notification_type: str = "SYSTEM"
):
    """
    Creates persistent notification DB records for all active users
    and emits real-time 'new_notification' and 'unread_count_updated' events over Socket.IO.
    """
    active_users = db.query(User).filter(User.is_active == True).all()
    now = get_current_local_now()

    notifications_to_emit = []

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
        db.flush()  # Generates notif.id

        # Calculate exact unread count for this user
        unread_count = db.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.is_read == False
        ).count()

        payload = {
            "id": notif.id,
            "user_id": user.id,
            "title": title,
            "message": message,
            "type": notification_type,
            "is_read": False,
            "created_at": now.isoformat(),
            "unread_count": unread_count
        }
        notifications_to_emit.append((user.id, payload, unread_count))

    db.commit()

    # Safely dispatch async Socket.IO emits onto main event loop
    global _main_loop
    for user_id, payload, unread_count in notifications_to_emit:
        if _main_loop and _main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _emit_notification_to_user(user_id, payload, unread_count),
                _main_loop
            )
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_emit_notification_to_user(user_id, payload, unread_count))
            except RuntimeError:
                pass

def notify_unread_count_changed(db: Session, user_id: int):
    """
    Recalculates and emits the updated unread count to a specific user room over Socket.IO.
    """
    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).count()

    global _main_loop
    if _main_loop and _main_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            _emit_unread_count_to_user(user_id, unread_count),
            _main_loop
        )
    else:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_emit_unread_count_to_user(user_id, unread_count))
        except RuntimeError:
            pass
