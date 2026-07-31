from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.models import User, MessMonth
from app.security import get_password_hash
from app.routers import auth, users, months, meals, expenses, deposits, summary

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mess Meal Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_db_seed():
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

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(months.router)
app.include_router(meals.router)
app.include_router(expenses.router)
app.include_router(deposits.router)
app.include_router(summary.router)

@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    return {"message": "Mess Meal Management API is running", "docs": "/docs"}

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok"}

