"""Migration 008: Add delay_reason column to manager_evaluations table."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration008AddDelayReasonToManagerEvaluations(MigrationInterface):
    """Add delay_reason column to manager_evaluations table."""

    @property
    def version(self) -> str:
        """Migration version identifier.

        Returns:
            Version string.
        """
        return "008"

    @property
    def description(self) -> str:
        """Get migration description.

        Returns:
            Description string.
        """
        return "Add delay_reason column to manager_evaluations table"

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.

        Returns:
            True if rollback is supported.
        """
        return True

    def up(self, engine) -> None:
        """Add delay_reason column to manager_evaluations table.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Adding delay_reason column to manager_evaluations table")

        with engine.connect() as connection:
            connection.execute(
                text("""
                    ALTER TABLE manager_evaluations 
                    ADD COLUMN IF NOT EXISTS delay_reason TEXT
                """)
            )
            connection.commit()

        LOGGER.info("delay_reason column added successfully")

    def down(self, engine) -> None:
        """Rollback the migration - drop delay_reason column.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Removing delay_reason column from manager_evaluations table")

        with engine.connect() as connection:
            connection.execute(
                text("ALTER TABLE manager_evaluations DROP COLUMN IF EXISTS delay_reason")
            )
            connection.commit()

        LOGGER.info("delay_reason column removed successfully")
