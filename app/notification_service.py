import asyncio
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import User, Notification
from app.month_utils import get_current_local_now
from app.socketio_server import sio

# Reference to main event loop
_main_loop: Optional[asyncio.AbstractEventLoop] = None

def set_main_loop(loop: asyncio.AbstractEventLoop):
    global _main_loop
    _main_loop = loop

def _get_loop() -> Optional[asyncio.AbstractEventLoop]:
    global _main_loop
    if _main_loop and _main_loop.is_running():
        return _main_loop
    if hasattr(sio, 'eio') and sio.eio and hasattr(sio.eio, 'loop') and sio.eio.loop and sio.eio.loop.is_running():
        return sio.eio.loop
    try:
        loop = asyncio.get_event_loop()
        if loop and loop.is_running():
            return loop
    except Exception:
        pass
    return None

async def _emit_notification_to_user(user_id: int, notif_payload: dict, unread_count: int):
    try:
        await sio.emit("new_notification", notif_payload, room=f"user_{user_id}")
        await sio.emit("unread_count_updated", {"unread_count": unread_count}, room=f"user_{user_id}")
        print(f"[Socket.IO] Emitted notification to room user_{user_id} (unread: {unread_count})")
    except Exception as e:
        print(f"[Socket.IO] Error emitting notification to user {user_id}: {e}")

async def _emit_unread_count_to_user(user_id: int, unread_count: int):
    try:
        await sio.emit("unread_count_updated", {"unread_count": unread_count}, room=f"user_{user_id}")
        print(f"[Socket.IO] Emitted unread_count {unread_count} to room user_{user_id}")
    except Exception as e:
        print(f"[Socket.IO] Error emitting unread_count: {e}")

def create_and_broadcast_notification(
    db: Session,
    title: str,
    message: str,
    notification_type: str = "SYSTEM"
):
    """
    Creates persistent notification DB records for all active users efficiently
    and emits real-time Socket.IO notifications.
    """
    active_users = db.query(User).filter(User.is_active == True).all()
    if not active_users:
        return

    now = get_current_local_now()

    # Optimized 1 single batch query for unread counts instead of N queries in a loop
    unread_counts_raw = db.query(
        Notification.user_id,
        func.count(Notification.id)
    ).filter(
        Notification.is_read == False
    ).group_by(Notification.user_id).all()

    unread_map = {uid: count for uid, count in unread_counts_raw}

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

        new_unread_count = unread_map.get(user.id, 0) + 1

        payload = {
            "id": notif.id,
            "user_id": user.id,
            "title": title,
            "message": message,
            "type": notification_type,
            "is_read": False,
            "created_at": now.isoformat(),
            "unread_count": new_unread_count
        }
        notifications_to_emit.append((user.id, payload, new_unread_count))

    db.commit()

    # Dispatch emits safely using start_background_task with fallback
    for user_id, payload, unread_count in notifications_to_emit:
        try:
            sio.start_background_task(_emit_notification_to_user, user_id, payload, unread_count)
        except Exception:
            loop = _get_loop()
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    _emit_notification_to_user(user_id, payload, unread_count),
                    loop
                )

def create_and_broadcast_per_user_notifications(
    db: Session,
    user_notifications: List[Tuple[int, str, str, str]]
):
    """
    Accepts a list of tuples (user_id, title, message, notification_type)
    and broadcasts tailored notifications to each specific user.
    """
    if not user_notifications:
        return

    now = get_current_local_now()

    unread_counts_raw = db.query(
        Notification.user_id,
        func.count(Notification.id)
    ).filter(
        Notification.is_read == False
    ).group_by(Notification.user_id).all()

    unread_map = {uid: count for uid, count in unread_counts_raw}

    notifications_to_emit = []

    for user_id, title, message, notification_type in user_notifications:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            is_read=False,
            created_at=now
        )
        db.add(notif)
        db.flush()

        new_unread_count = unread_map.get(user_id, 0) + 1
        unread_map[user_id] = new_unread_count

        payload = {
            "id": notif.id,
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": notification_type,
            "is_read": False,
            "created_at": now.isoformat(),
            "unread_count": new_unread_count
        }
        notifications_to_emit.append((user_id, payload, new_unread_count))

    db.commit()

    for user_id, payload, unread_count in notifications_to_emit:
        try:
            sio.start_background_task(_emit_notification_to_user, user_id, payload, unread_count)
        except Exception:
            loop = _get_loop()
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    _emit_notification_to_user(user_id, payload, unread_count),
                    loop
                )

def notify_unread_count_changed(db: Session, user_id: int):
    """
    Recalculates and emits the updated unread count to a specific user room over Socket.IO.
    """
    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).count()

    try:
        sio.start_background_task(_emit_unread_count_to_user, user_id, unread_count)
    except Exception:
        loop = _get_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _emit_unread_count_to_user(user_id, unread_count),
                loop
            )
