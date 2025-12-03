"""Migration 003: Add root_cause column to jira_tasks_enhanced table."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER


class Migration003AddRootCause:
    """Add root_cause column to jira_tasks_enhanced table."""

    @staticmethod
    def get_version() -> str:
        """Get migration version number.
        
        Returns:
            Version string.
        """
        return "003"

    @staticmethod
    def get_description() -> str:
        """Get migration description.
        
        Returns:
            Description string.
        """
        return "Add root_cause column to jira_tasks_enhanced table"

    def upgrade(self, connection) -> None:
        """Apply the migration.
        
        Args:
            connection: Database connection.
        """
        try:
            with connection.begin():
                # Add root_cause column
                connection.execute(
                    text(
                        "ALTER TABLE jira_tasks_enhanced "
                        "ADD COLUMN IF NOT EXISTS root_cause TEXT"
                    )
                )
                LOGGER.info("Added root_cause column to jira_tasks_enhanced table")

        except Exception as e:
            LOGGER.error(f"Failed to add root_cause column: {e}")
            raise

    def downgrade(self, connection) -> None:
        """Revert the migration.
        
        Args:
            connection: Database connection.
        """
        try:
            with connection.begin():
                # Remove root_cause column
                connection.execute(
                    text(
                        "ALTER TABLE jira_tasks_enhanced "
                        "DROP COLUMN IF EXISTS root_cause"
                    )
                )
                LOGGER.info("Removed root_cause column from jira_tasks_enhanced table")

        except Exception as e:
            LOGGER.error(f"Failed to remove root_cause column: {e}")
            raise

