"""Migration 004: Add reviewed_at column to jira_tasks_enhanced table."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration004AddReviewedAt(MigrationInterface):
    """Add reviewed_at column to jira_tasks_enhanced table."""

    def get_migration_id(self) -> str:
        """Return unique migration identifier.
        
        Returns:
            Migration ID string.
        """
        return "004_add_reviewed_at"

    @property
    def version(self) -> str:
        """Get migration version number.
        
        Returns:
            Version string.
        """
        return "004"

    @property
    def description(self) -> str:
        """Get migration description.
        
        Returns:
            Description string.
        """
        return "Add reviewed_at column to jira_tasks_enhanced table"

    @property
    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.
        
        Returns:
            True if rollback is supported.
        """
        return True

    def up(self, engine) -> None:
        """Apply the migration.
        
        Args:
            engine: SQLAlchemy engine object.
        """
        LOGGER.info("Adding reviewed_at column to jira_tasks_enhanced table")

        with engine.connect() as connection:
            connection.execute(
                text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP"
                )
            )
            connection.commit()

        LOGGER.info("Successfully added reviewed_at column")

    def down(self, engine) -> None:
        """Revert the migration.
        
        Args:
            engine: SQLAlchemy engine object.
        """
        LOGGER.info("Removing reviewed_at column from jira_tasks_enhanced table")

        with engine.connect() as connection:
            connection.execute(
                text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "DROP COLUMN IF EXISTS reviewed_at"
                )
            )
            connection.commit()

        LOGGER.info("Successfully removed reviewed_at column")
