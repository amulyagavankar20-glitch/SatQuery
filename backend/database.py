"""
SatQuery AI — Database Engine and Session Management
"""
from collections.abc import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, SessionTransaction

from backend.config import settings
import sys
from src.logger import logging
from src.exception import CustomException

# Primary Engine (Writes)
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    echo=settings.DB_ECHO,
)

# Replica Engine (Reads)
replica_engine = create_engine(
    settings.DATABASE_REPLICA_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    echo=settings.DB_ECHO,
)

class RoutingSession(Session):
    def get_bind(self, mapper=None, clause=None, **kw):
        # Route logic: if it's a read (SELECT), use replica engine
        # But we must be careful: if we are in a transaction, we might want to stick to primary.
        # For simplicity, if we haven't flushed or aren't doing writes, we could use replica.
        if self._flushing or isinstance(clause, (text.__class__,)):
            return engine
            
        # Very basic check for SELECT queries based on clause
        if clause is not None and getattr(clause, "is_select", False):
            return replica_engine
            
        return engine

# Session factory for DB interactions with routing
SessionLocal = sessionmaker(
    class_=RoutingSession,
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
    try:
        with engine.connect() as conn:
            db_version = conn.execute(text("SELECT version();")).scalar()
            postgis_version = conn.execute(text("SELECT PostGIS_Full_Version();")).scalar()
            return {
                "status": "connected",
                "database_version": db_version,
                "postgis_version": postgis_version,
            }
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        raise CustomException(e, sys)
