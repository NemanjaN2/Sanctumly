"""
Sanctumly Database Configuration
SQLAlchemy engine, session management, and Base class
"""
import os
from sqlalchemy import create_engine, inspect, text
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

def migrate_ai_routing_event_columns(target_engine=engine):
    """Add nullable token/cache telemetry columns to existing routing-event tables."""
    additive_columns = {
        "prompt_tokens": "INTEGER",
        "cached_prompt_tokens": "INTEGER",
        "completion_tokens": "INTEGER",
        "reasoning_tokens": "INTEGER",
        "estimated_cost_usd": "FLOAT",
        "cache_savings_usd": "FLOAT",
        "reasoning_effort": "VARCHAR(16)",
    }
    inspector = inspect(target_engine)
    if "ai_routing_events" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("ai_routing_events")}
    with target_engine.begin() as connection:
        for column_name, sql_type in additive_columns.items():
            if column_name in existing:
                continue
            if target_engine.dialect.name == "postgresql":
                # IF NOT EXISTS makes concurrent Railway instance startup safe.
                statement = (
                    "ALTER TABLE ai_routing_events ADD COLUMN IF NOT EXISTS "
                    f"{column_name} {sql_type}"
                )
            else:
                statement = (
                    "ALTER TABLE ai_routing_events ADD COLUMN "
                    f"{column_name} {sql_type}"
                )
            connection.execute(text(statement))


def init_db():
    """Create missing tables and apply safe additive schema updates."""
    Base.metadata.create_all(engine)
    for table in Base.metadata.sorted_tables:
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            index.create(bind=engine, checkfirst=True)
    migrate_ai_routing_event_columns(engine)
