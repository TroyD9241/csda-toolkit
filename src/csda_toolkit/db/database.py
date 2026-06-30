"""Database connection and session management for csda-toolkit."""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DATABASE_URL = "postgresql://csda:csda@localhost:5432/csda"


def get_database_url() -> str:
    """Get database URL from environment or return default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_db_engine(database_url: Optional[str] = None) -> Engine:
    """Create a SQLAlchemy engine connected to the csda database."""
    url = database_url or get_database_url()
    return create_engine(url, pool_pre_ping=True)


def init_db(engine: Engine) -> None:
    """Create all tables in the csda schema."""
    # Ensure the csda schema exists
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS csda"))
        conn.commit()
    Base.metadata.create_all(engine)


class Database:
    """Manages a database connection and session factory."""

    def __init__(self, database_url: Optional[str] = None):
        self.engine = create_db_engine(database_url)
        self._session_factory = sessionmaker(bind=self.engine)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_schema(self) -> None:
        """Create the csda schema and all tables."""
        with self.engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS csda"))
            conn.commit()
        Base.metadata.create_all(self.engine)

    def drop_schema(self) -> None:
        """Drop all tables in the csda schema."""
        Base.metadata.drop_all(self.engine)
