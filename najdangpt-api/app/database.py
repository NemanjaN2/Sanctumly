"""
Sanctumly Database Configuration
SQLAlchemy engine, session management, and Base class
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

def get_db_engine():
    """Create a Railway PostgreSQL or local SQLite SQLAlchemy engine."""
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+pg8000://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+pg8000://", 1)

        # Railway Postgres plans have finite connection limits. Keep the pool
        # intentionally small; pre-ping recovers stale pooled connections.
        return create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=int(os.environ.get("DB_POOL_SIZE", "3")),
            max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "2")),
            pool_timeout=30,
        )

    return create_engine(
        "sqlite:///./najdangpt.db",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

engine = get_db_engine()
SessionLocal = sessionmaker(bind=engine)

def get_db():
    """Dependency for FastAPI routes - yields DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create missing tables and add declared indexes to existing tables.

    SQLAlchemy's create_all skips existing tables as a whole, including newly
    declared indexes on those tables. Creating indexes individually with
    checkfirst=True makes these additive performance updates deploy safely to
    existing Railway PostgreSQL databases without altering stored columns.
    """
    Base.metadata.create_all(engine)
    for table in Base.metadata.sorted_tables:
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            index.create(bind=engine, checkfirst=True)
