"""PostgreSQL database connection implementation."""
from __future__ import annotations

import urllib
from contextlib import contextmanager
from typing import Any
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy import Engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface


class PostgreSQLConnection(DatabaseConnectionInterface):
    """PostgreSQL database connection implementation."""

    def __init__(self, settings: PostgresSettings) -> None:
        """Initialize PostgreSQL connection.
        
        Args:
            settings: PostgreSQL connection settings.
        """
        self.settings = settings
        self._engine = None
        self._session_maker = None

    def get_engine(self) -> Engine:
        """Get SQLAlchemy engine instance.
        
        Returns:
            SQLAlchemy engine instance.
        """
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    def get_session(self) -> Session:
        """Get SQLAlchemy session instance.
        
        Returns:
            SQLAlchemy session instance.
        """
        if self._session_maker is None:
            self._session_maker = sessionmaker(bind=self.get_engine())
        return self._session_maker()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations.
        
        Yields:
            SQLAlchemy session instance.
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def connection_scope(self) -> Generator[Any, None, None]:
        """Provide a connection scope for raw SQL operations.
        
        Yields:
            Database connection instance.
        """
        engine = self.get_engine()
        with engine.begin() as conn:
            yield conn

    def execute_query(self, query: str, params: dict[str, Any] = None) -> Any:
        """Execute raw SQL query.
        
        Args:
            query: SQL query string.
            params: Query parameters.
            
        Returns:
            Query result.
        """
        with self.connection_scope() as conn:
            return conn.execute(text(query), params or {})

    def close(self) -> None:
        """Close database connection."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
        self._session_maker = None

    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with PostgreSQL connection.
        
        Returns:
            SQLAlchemy engine instance.
        """
        encoded_password = urllib.parse.quote_plus(self.settings.db_password)
        database_url = (
            f"postgresql://{self.settings.db_user}:"
            f"{encoded_password}@{self.settings.db_host}:"
            f"{self.settings.db_port}/{self.settings.db_name}"
        )
        
        engine = create_engine(database_url)
        LOGGER.info(f"Created PostgreSQL engine for {self.settings.db_host}:{self.settings.db_port}/{self.settings.db_name}")
        
        return engine
