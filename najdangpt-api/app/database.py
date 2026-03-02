"""
NajdanGPT Database Configuration
SQLAlchemy engine, session management, and Base class
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import INSTANCE_CONNECTION_NAME, DB_USER, DB_PASS, DB_NAME

Base = declarative_base()


def get_db_engine():
    """Create database engine - PostgreSQL on Cloud SQL or SQLite locally"""
    if INSTANCE_CONNECTION_NAME:
        connection_string = (
            f"postgresql+pg8000://{DB_USER}:{DB_PASS}@/{DB_NAME}"
            f"?unix_sock=/cloudsql/{INSTANCE_CONNECTION_NAME}/.s.PGSQL.5432"
        )
    else:
        connection_string = "sqlite:///./najdangpt.db"
    
    return create_engine(connection_string, pool_pre_ping=True)


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
