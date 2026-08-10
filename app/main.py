import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.models import User, MessMonth
from app.security import get_password_hash
from app.month_utils import get_or_create_mess_month, get_current_local_now
from app.routers import auth, users, months, meals, expenses, deposits, summary, notifications

import asyncio
from app.notification_service import set_main_loop

try:
    print("[Startup] Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    print("[Startup] Database tables initialized successfully!")
except Exception as e:
    print(f"[Startup Exception] Table creation error: {e}")
    import traceback
    traceback.print_exc()

app = FastAPI(title="Mess Meal Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def midnight_month_checker():
    """
    Dedicated background worker task that checks once per hour
    for month transitions and triggers automated month-end notifications.
    """
    while True:
        try:
            await asyncio.sleep(3600)  # Sleep for 1 hour
            now = get_current_local_now()
            db = SessionLocal()
            try:
                get_or_create_mess_month(db, now.year, now.month)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Background Month Checker Warning] {e}")

@app.on_event("startup")
async def start_background_schedulers():
    set_main_loop(asyncio.get_running_loop())
    asyncio.create_task(midnight_month_checker())

@app.on_event("startup")
def startup_db_seed():
    try:
        admin_email = (os.getenv("SUPER_ADMIN_EMAIL") or "").strip()
        admin_password = (os.getenv("SUPER_ADMIN_PASSWORD") or "").strip()

        if not admin_email or not admin_password:
            raise RuntimeError(
                "SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD environment variables are required and must be set."
            )

        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.email == admin_email).first()
            if not admin:
                # Also check if any super admin exists before creating
                any_super_admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
                if not any_super_admin:
                    admin = User(
                        name="Super Admin",
                        email=admin_email,
                        hashed_password=get_password_hash(admin_password),
                        role="SUPER_ADMIN",
                        is_active=True
                    )
                    db.add(admin)
                    db.commit()
                    db.refresh(admin)
                    print(f"Default Super Admin created: {admin_email}")
        finally:
            db.close()
    except Exception as e:
        print(f"[DB Seed Warning] Startup db seed deferred: {e}")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(months.router)
app.include_router(meals.router)
app.include_router(expenses.router)
app.include_router(deposits.router)
app.include_router(summary.router)
app.include_router(notifications.router)

@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    return {"message": "Mess Meal Management API is running", "docs": "/docs"}

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok"}

import socketio
from app.socketio_server import sio

app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")
