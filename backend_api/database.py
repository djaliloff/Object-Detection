from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
from dotenv import load_dotenv

from pathlib import Path

# Get project root (parent of backend_api)
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "backend_api" / "surveillance.db"

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or "sqlite" in DATABASE_URL:
    # Force absolute path for SQLite to avoid confusion between microservices
    DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

logger_str = f"Connecting to database: {DATABASE_URL}"
print(logger_str)

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
