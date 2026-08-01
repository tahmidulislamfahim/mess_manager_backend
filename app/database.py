import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if TURSO_DATABASE_URL:
    try:
        import libsql_experimental
    except ImportError:
        import sqlite3 as libsql_experimental

    url = TURSO_DATABASE_URL
    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://")

    print(f"[Database] Connecting to Turso Cloud Database...")
    
    def connect_turso():
        return libsql_experimental.connect(database=url, auth_token=TURSO_AUTH_TOKEN)

    engine = create_engine("sqlite://", creator=connect_turso, connect_args={"check_same_thread": False})
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'mess.db')}"
    print(f"[Database] Connecting to local SQLite file...")
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
