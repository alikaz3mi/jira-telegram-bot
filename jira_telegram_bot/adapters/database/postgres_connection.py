"""PostgreSQL database connection implementation."""
from __future__ import annotations

import urllib
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface


class PostgresConnection(DatabaseConnectionInterface):
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
            SQLAlchemy engine.
        """
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    def get_session(self) -> Session:
        """Get SQLAlchemy session instance.
        
        Returns:
            SQLAlchemy session.
        """
        if self._session_maker is None:
            self._session_maker = sessionmaker(bind=self.get_engine())
        return self._session_maker()

    def execute_query(self, query: str, params: dict[str, Any] = None) -> Any:
        """Execute raw SQL query.
        
        Args:
            query: SQL query string.
            params: Query parameters.
            
        Returns:
            Query result.
        """
        try:
            with self.get_engine().begin() as conn:
                if params:
                    return conn.execute(text(query), params)
                else:
                    return conn.execute(text(query))
        except Exception as e:
            LOGGER.error(f"Failed to execute query: {e}")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_maker = None

    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with PostgreSQL connection.
        
        Returns:
            SQLAlchemy engine.
        """
        encoded_password = urllib.parse.quote_plus(self.settings.db_password)
        database_url = (
            f"postgresql://{self.settings.db_user}:"
            f"{encoded_password}@{self.settings.db_host}:"
            f"{self.settings.db_port}/{self.settings.db_name}"
        )
        return create_engine(database_url)
