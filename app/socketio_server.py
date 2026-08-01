import urllib.parse
import jwt
import socketio
from app.security import SECRET_KEY, ALGORITHM
from app.database import SessionLocal
from app.models import User

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)

@sio.event
async def connect(sid, environ, auth=None):
    token = None
    if auth and isinstance(auth, dict) and 'token' in auth:
        token = auth['token']
    if not token and 'QUERY_STRING' in environ:
        qs = urllib.parse.parse_qs(environ['QUERY_STRING'])
        if 'token' in qs and len(qs['token']) > 0:
            token = qs['token'][0]
    if not token and 'HTTP_AUTHORIZATION' in environ:
        auth_header = environ['HTTP_AUTHORIZATION']
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        print(f"[Socket.IO] Connection rejected: No token provided (sid: {sid})")
        raise ConnectionRefusedError('Authentication token required')

    db = SessionLocal()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user = db.query(User).filter(User.email == email).first() if email else None

        if not user:
            print(f"[Socket.IO] Connection rejected: Invalid user (sid: {sid})")
            raise ConnectionRefusedError('Invalid user token')

        await sio.save_session(sid, {'user_id': user.id})
        await sio.enter_room(sid, f"user_{user.id}")
        await sio.enter_room(sid, "all_users")
        print(f"[Socket.IO] User '{user.name}' (ID: {user.id}) connected & joined room 'user_{user.id}' (sid: {sid})")

    except Exception as e:
        print(f"[Socket.IO] Connection failed: {e}")
        raise ConnectionRefusedError('Authentication failed')
    finally:
        db.close()

@sio.event
async def disconnect(sid):
    try:
        session = await sio.get_session(sid)
        user_id = session.get('user_id') if session else None
        print(f"[Socket.IO] User ID {user_id} disconnected (sid: {sid})")
    except Exception:
        pass
