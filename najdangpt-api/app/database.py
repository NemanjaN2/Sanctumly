"""
Sanctumly Database Configuration
SQLAlchemy engine, session management, and Base class
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

def get_db_engine():
    """Create database engine - uses DATABASE_URL from Railway or falls back to SQLite"""
    database_url = os.environ.get("DATABASE_URL")
    
    if database_url:
        # Railway provides postgresql:// but SQLAlchemy needs postgresql+psycopg2://
        # pg8000 works without psycopg2
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+pg8000://", 1)
        return create_engine(database_url, pool_pre_ping=True)
    else:
        return create_engine("sqlite:///./najdangpt.db", pool_pre_ping=True)

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
    """Create all tables"""
    Base.metadata.create_all(engine)
