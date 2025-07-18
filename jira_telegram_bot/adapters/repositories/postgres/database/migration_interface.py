"""Base migration interface for Clean Architecture compliance."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any

from sqlalchemy import Engine


class MigrationInterface(ABC):
    """Interface for database migrations."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the migration version identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the migration description."""
        pass

    @abstractmethod
    def up(self, engine: Engine) -> None:
        """Apply the migration.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        pass

    @abstractmethod
    def down(self, engine: Engine) -> None:
        """Rollback the migration.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        pass

    @abstractmethod
    def can_rollback(self) -> bool:
        """Check if migration can be rolled back."""
        pass
