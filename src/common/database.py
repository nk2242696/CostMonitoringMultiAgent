"""
Database module.

Provides database connection, session management, and base models.
"""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from src.common.config import get_config
from src.common.logging_config import get_logger

logger = get_logger(__name__)

# Base class for ORM models
Base = declarative_base()


class Database:
    """Database connection manager."""

    def __init__(self):
        """Initialize database manager."""
        self.config = get_config()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._async_engine = None
        self._async_session_factory = None

    def get_engine(self) -> Engine:
        """
        Get database engine.

        Returns:
            SQLAlchemy Engine instance
        """
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    def _create_engine(self) -> Engine:
        """
        Create database engine.

        Returns:
            SQLAlchemy Engine instance
        """
        db_config = self.config.database
        url = db_config.url
        is_sqlite = url.startswith("sqlite")

        if is_sqlite:
            engine = create_engine(
                url,
                echo=db_config.echo_sql,
                connect_args={"check_same_thread": False},
                poolclass=NullPool,
            )
            logger.info(f"SQLite engine created: {db_config.database}")
        else:
            engine = create_engine(
                url,
                pool_size=db_config.pool_size,
                max_overflow=db_config.max_overflow,
                pool_pre_ping=True,
                echo=db_config.echo_sql,
                poolclass=QueuePool,
            )

            @event.listens_for(engine, "connect")
            def setup_timescaledb(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                try:
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                    dbapi_conn.commit()
                except Exception:
                    dbapi_conn.rollback()
                finally:
                    cursor.close()

            logger.info(f"PostgreSQL engine created: {db_config.host}:{db_config.port}/{db_config.database}")
        return engine

    def get_session_factory(self) -> sessionmaker:
        """
        Get session factory.

        Returns:
            SQLAlchemy session factory
        """
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.get_engine(),
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
        return self._session_factory

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get database session context manager.

        Yields:
            SQLAlchemy Session
        """
        session_factory = self.get_session_factory()
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_tables(self) -> None:
        """Create all database tables."""
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=self.get_engine())
        logger.info("Database tables created successfully")

    def drop_tables(self) -> None:
        """Drop all database tables (use with caution!)."""
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=self.get_engine())
        logger.info("Database tables dropped")

    def close(self) -> None:
        """Close database connections."""
        if self._engine:
            self._engine.dispose()
            logger.info("Database connections closed")


# Global database instance
_database: Optional[Database] = None


def get_database() -> Database:
    """
    Get global database instance.

    Returns:
        Database instance
    """
    global _database
    if _database is None:
        _database = Database()
    return _database


def get_session() -> Generator[Session, None, None]:
    """
    Get database session (for dependency injection).

    Yields:
        SQLAlchemy Session
    """
    db = get_database()
    with db.get_session() as session:
        yield session


def init_db() -> None:
    """Initialize database (create tables)."""
    db = get_database()
    db.create_tables()


def close_db() -> None:
    """Close database connections."""
    global _database
    if _database:
        _database.close()
        _database = None
