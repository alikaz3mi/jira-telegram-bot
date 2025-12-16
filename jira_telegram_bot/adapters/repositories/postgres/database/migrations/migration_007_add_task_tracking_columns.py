"""Migration 007: Add due_date_first_set_at and involved_users to jira_tasks_enhanced."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration007AddTaskTrackingColumns(MigrationInterface):
    """Add columns for tracking due date history and involved users."""

    @property
    def version(self) -> str:
        """Migration version identifier.

        Returns:
            Version string.
        """
        return "007"

    @property
    def description(self) -> str:
        """Get migration description.

        Returns:
            Description string.
        """
        return "Add due_date_first_set_at and involved_users columns to jira_tasks_enhanced"

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.

        Returns:
            True if rollback is supported.
        """
        return True

    def up(self, engine) -> None:
        """Add new columns to jira_tasks_enhanced table.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Adding due_date_first_set_at and involved_users columns to jira_tasks_enhanced")

        with engine.connect() as connection:
            # Add due_date_first_set_at column
            connection.execute(
                text("""
                    ALTER TABLE jira_tasks_enhanced 
                    ADD COLUMN IF NOT EXISTS due_date_first_set_at TIMESTAMP
                """)
            )
            
            # Add involved_users column (JSON array of usernames)
            connection.execute(
                text("""
                    ALTER TABLE jira_tasks_enhanced 
                    ADD COLUMN IF NOT EXISTS involved_users TEXT
                """)
            )
            
            connection.commit()

        LOGGER.info("Columns added successfully")

    def down(self, engine) -> None:
        """Rollback the migration - drop added columns.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Removing due_date_first_set_at and involved_users columns from jira_tasks_enhanced")

        with engine.connect() as connection:
            connection.execute(
                text("ALTER TABLE jira_tasks_enhanced DROP COLUMN IF EXISTS due_date_first_set_at")
            )
            connection.execute(
                text("ALTER TABLE jira_tasks_enhanced DROP COLUMN IF EXISTS involved_users")
            )
            connection.commit()

        LOGGER.info("Columns removed successfully")
