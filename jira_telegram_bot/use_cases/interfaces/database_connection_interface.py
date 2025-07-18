"""Database connection interface for Clean Architecture compliance."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from contextlib import contextmanager
from typing import Any
from typing import Generator

from sqlalchemy import Engine
from sqlalchemy.orm import Session


class DatabaseConnectionInterface(ABC):
    """Interface for database connection management."""

    @abstractmethod
    def get_engine(self) -> Engine:
        """Get SQLAlchemy engine instance.
        
        Returns:
            SQLAlchemy engine.
        """
        pass

    @abstractmethod
    def get_session(self) -> Session:
        """Get SQLAlchemy session instance.
        
        Returns:
            SQLAlchemy session.
        """

    @abstractmethod
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations.
        
        Yields:
            SQLAlchemy session instance.
        """

    @abstractmethod
    @contextmanager
    def connection_scope(self) -> Generator[Any, None, None]:
        """Provide a connection scope for raw SQL operations.
        
        Yields:
            Database connection instance.
        """

    @abstractmethod
    def execute_query(self, query: str, params: dict[str, Any] = None) -> Any:
        """Execute raw SQL query.
        
        Args:
            query: SQL query string.
            params: Query parameters.
            
        Returns:
            Query result.
        """

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
