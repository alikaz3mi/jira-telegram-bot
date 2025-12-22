"""Migration 009: Add delay_reason column to jira_tasks_enhanced table."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration009AddDelayReasonToJiraTasksEnhanced(MigrationInterface):
    """Add delay_reason column to jira_tasks_enhanced table for tracking task delays."""

    @property
    def version(self) -> str:
        """Migration version identifier.

        Returns:
            Version string.
        """
        return "009"

    @property
    def description(self) -> str:
        """Get migration description.

        Returns:
            Description string.
        """
        return "Add delay_reason column to jira_tasks_enhanced table"

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.

        Returns:
            True if rollback is supported.
        """
        return True

    def up(self, engine) -> None:
        """Add delay_reason column to jira_tasks_enhanced table.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Adding delay_reason column to jira_tasks_enhanced table")

        with engine.connect() as connection:
            connection.execute(
                text("""
                    ALTER TABLE jira_tasks_enhanced 
                    ADD COLUMN IF NOT EXISTS delay_reason TEXT
                """)
            )
            connection.commit()

        LOGGER.info("delay_reason column added successfully to jira_tasks_enhanced")

    def down(self, engine) -> None:
        """Rollback the migration - drop delay_reason column.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Removing delay_reason column from jira_tasks_enhanced table")

        with engine.connect() as connection:
            connection.execute(
                text("ALTER TABLE jira_tasks_enhanced DROP COLUMN IF EXISTS delay_reason")
            )
            connection.commit()

        LOGGER.info("delay_reason column removed successfully from jira_tasks_enhanced")
