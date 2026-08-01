import os
import re
from urllib.parse import urlparse, parse_qs

try:
    import sqlalchemy_libsql
except ImportError:
    pass

try:
    import libsql_experimental
except ImportError:
    import sqlite3 as libsql_experimental

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if TURSO_DATABASE_URL:
    raw_url = TURSO_DATABASE_URL.strip()

    # Extract token from TURSO_AUTH_TOKEN env var, or fallback to parsing from raw_url query string
    token = (TURSO_AUTH_TOKEN or "").strip()
    if not token and "?" in raw_url:
        parsed = urlparse(raw_url)
        qs = parse_qs(parsed.query)
        token = (qs.get("auth_token") or qs.get("authToken") or [""])[0].strip()

    clean_host = raw_url
    for prefix in ["sqlite+libsql://", "sqlite+https://", "libsql://", "https://", "http://"]:
        if clean_host.startswith(prefix):
            clean_host = clean_host[len(prefix):]
            break

    if "?" in clean_host:
        clean_host = clean_host.split("?")[0]

    clean_host = clean_host.rstrip("/")
    clean_host = re.sub(r'\.aws-[a-z0-9-]+\.turso\.io', '.turso.io', clean_host)
    https_turso_url = f"https://{clean_host}"

    print(f"[Database] Connecting to Turso Cloud Database via libsql_experimental over HTTPS: {https_turso_url} (token len: {len(token)})...")

    def get_turso_connection():
        return libsql_experimental.connect(https_turso_url, auth_token=token)

    engine = create_engine(
        "sqlite+libsql://",
        creator=get_turso_connection,
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300,
        pool_pre_ping=True
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
