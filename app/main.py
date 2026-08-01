from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.models import User, MessMonth
from app.security import get_password_hash
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

@app.on_event("startup")
async def capture_main_loop():
    set_main_loop(asyncio.get_running_loop())

@app.on_event("startup")
def startup_db_seed():
    try:
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.email == "admin@mess.com").first()
            if not admin:
                admin = User(
                    name="Super Admin",
                    email="admin@mess.com",
                    hashed_password=get_password_hash("admin123"),
                    role="SUPER_ADMIN",
                    is_active=True
                )
                db.add(admin)
                db.commit()
                db.refresh(admin)
                print("Default Super Admin created: admin@mess.com / admin123")
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
