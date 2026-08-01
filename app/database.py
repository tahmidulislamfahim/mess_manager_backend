import os
import re
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if TURSO_DATABASE_URL:
    url = TURSO_DATABASE_URL
    clean_url = url
    for prefix in ["sqlite+libsql://", "sqlite+https://", "libsql://", "https://", "http://"]:
        if clean_url.startswith(prefix):
            clean_url = clean_url[len(prefix):]
            break
    
    if "?" in clean_url:
        clean_url = clean_url.split("?")[0]

    # Strip AWS region subdomain (e.g. .aws-ap-south-1) to avoid 308 redirects from Turso edge proxy
    clean_url = re.sub(r'\.aws-[a-z0-9-]+\.turso\.io', '.turso.io', clean_url)
        
    token = TURSO_AUTH_TOKEN or ""
    turso_engine_url = f"sqlite+libsql://{clean_url}?authToken={token}"
    
    print(f"[Database] Connecting to Turso Cloud Database: {clean_url}...")
    engine = create_engine(turso_engine_url, connect_args={"check_same_thread": False})
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
