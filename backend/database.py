"""
SatQuery AI — Database Engine and Session Management
"""
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings

# Configure SQLAlchemy 2.0 Engine using psycopg3
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    echo=settings.DB_ECHO,
)

# Session factory for DB interactions
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.x declarative models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to yield a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    """Utility function to verify connectivity and PostGIS extension status."""
    with engine.connect() as conn:
        db_version = conn.execute(text("SELECT version();")).scalar()
        postgis_version = conn.execute(text("SELECT PostGIS_Full_Version();")).scalar()
        return {
            "status": "connected",
            "database_version": db_version,
            "postgis_version": postgis_version,
        }
