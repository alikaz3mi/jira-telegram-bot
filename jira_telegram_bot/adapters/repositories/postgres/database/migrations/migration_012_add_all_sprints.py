"""Migration 012: Add all_sprints array column to jira_tasks_enhanced table."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration012AddAllSprints(MigrationInterface):
    """Add all_sprints array column for historical sprint tracking."""

    @property
    def version(self) -> str:
        """Migration version identifier.

        Returns:
            Version string.
        """
        return "012"

    @property
    def description(self) -> str:
        """Get migration description.

        Returns:
            Description string.
        """
        return "Add all_sprints array column to jira_tasks_enhanced table"

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.

        Returns:
            True if rollback is supported.
        """
        return True

    def up(self, engine) -> None:
        """Add all_sprints column to jira_tasks_enhanced table.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Adding all_sprints column to jira_tasks_enhanced table")

        with engine.connect() as connection:
            connection.execute(
                text("""
                    ALTER TABLE jira_tasks_enhanced
                    ADD COLUMN IF NOT EXISTS all_sprints VARCHAR[] DEFAULT '{}'
                """)
            )
            connection.commit()

        LOGGER.info("all_sprints column added successfully")

    def down(self, engine) -> None:
        """Rollback the migration - drop all_sprints column.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Removing all_sprints column from jira_tasks_enhanced table")

        with engine.connect() as connection:
            connection.execute(
                text("ALTER TABLE jira_tasks_enhanced DROP COLUMN IF EXISTS all_sprints")
            )
            connection.commit()

        LOGGER.info("all_sprints column removed successfully")
