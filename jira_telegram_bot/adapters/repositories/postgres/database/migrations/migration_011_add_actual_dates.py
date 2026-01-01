"""Migration 011: Add actual_start_date and actual_end_date columns to jira_tasks_enhanced table."""
from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import MigrationInterface


class Migration011AddActualDates(MigrationInterface):
    """Add actual_start_date and actual_end_date columns to jira_tasks_enhanced table."""

    @property
    def version(self) -> str:
        """Return the migration version identifier."""
        return "011"

    @property
    def description(self) -> str:
        """Return the migration description."""
        return "Add actual_start_date and actual_end_date columns to jira_tasks_enhanced table"

    def up(self, engine: Engine) -> None:
        """Apply the migration.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        with engine.begin() as conn:
            try:
                # Add actual_start_date column if it doesn't exist
                conn.execute(text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "ADD COLUMN IF NOT EXISTS actual_start_date TIMESTAMP;"
                ))
                
                # Add actual_end_date column if it doesn't exist
                conn.execute(text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "ADD COLUMN IF NOT EXISTS actual_end_date TIMESTAMP;"
                ))
                
                LOGGER.info("Migration 011: Added actual_start_date and actual_end_date columns successfully")
                
            except Exception as e:
                LOGGER.error(f"Migration 011 failed: {e}")
                raise

    def down(self, engine: Engine) -> None:
        """Rollback the migration.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        with engine.begin() as conn:
            try:
                # Remove actual_start_date column
                conn.execute(text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "DROP COLUMN IF EXISTS actual_start_date;"
                ))
                
                # Remove actual_end_date column
                conn.execute(text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "DROP COLUMN IF EXISTS actual_end_date;"
                ))
                
                LOGGER.info("Migration 011: Rolled back actual_start_date and actual_end_date columns successfully")
                
            except Exception as e:
                LOGGER.error(f"Migration 011 rollback failed: {e}")
                raise

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back."""
        return True
