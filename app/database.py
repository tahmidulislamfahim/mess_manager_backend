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

    url = TURSO_DATABASE_URL.strip()
    token = (TURSO_AUTH_TOKEN or "").strip()

    clean_url = url
    for prefix in ["sqlite+libsql://", "sqlite+https://", "libsql://", "https://", "http://"]:
        if clean_url.startswith(prefix):
            clean_url = clean_url[len(prefix):]
            break

    if "?" in clean_url:
        clean_url = clean_url.split("?")[0]

    clean_url = clean_url.rstrip("/")
    https_turso_url = f"https://{clean_url}"

    print(f"[Database] Connecting to Turso Cloud Database over HTTPS: {https_turso_url}...")

    def get_turso_connection():
        return libsql_experimental.connect(https_turso_url, auth_token=token)

    engine = create_engine(
        "sqlite://",
        creator=get_turso_connection,
        connect_args={"check_same_thread": False}
    )
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
