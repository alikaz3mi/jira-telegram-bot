"""Migration 001: Add due_date and project columns to jira_tasks_enhanced table."""
from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.database.migration_interface import MigrationInterface


class Migration001AddDueDateAndProject(MigrationInterface):
    """Add due_date and project columns to jira_tasks_enhanced table."""

    @property
    def version(self) -> str:
        """Return the migration version identifier."""
        return "001"

    @property
    def description(self) -> str:
        """Return the migration description."""
        return "Add due_date and project columns to jira_tasks_enhanced table"

    def up(self, engine: Engine) -> None:
        """Apply the migration.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        with engine.begin() as conn:
            try:
                # Add due_date column if it doesn't exist
                conn.execute(text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "ADD COLUMN IF NOT EXISTS due_date TIMESTAMP;"
                ))
                
                # Add project column if it doesn't exist
                conn.execute(text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "ADD COLUMN IF NOT EXISTS project VARCHAR;"
                ))
                
                LOGGER.info("Migration 001: Added due_date and project columns successfully")
                
            except Exception as e:
                LOGGER.error(f"Migration 001 failed: {e}")
                raise

    def down(self, engine: Engine) -> None:
        """Rollback the migration.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        with engine.begin() as conn:
            try:
                # Remove due_date column
                conn.execute(text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "DROP COLUMN IF EXISTS due_date;"
                ))
                
                # Remove project column
                conn.execute(text(
                    "ALTER TABLE jira_tasks_enhanced "
                    "DROP COLUMN IF EXISTS project;"
                ))
                
                LOGGER.info("Migration 001: Rolled back due_date and project columns successfully")
                
            except Exception as e:
                LOGGER.error(f"Migration 001 rollback failed: {e}")
                raise

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back."""
        return True
