"""Migration to add sync_status tracking table."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration002AddSyncStatus(MigrationInterface):
    """Add sync_status table for tracking synchronization state."""

    def get_migration_id(self) -> str:
        """Return unique migration identifier.
        
        Returns:
            Migration ID string.
        """
        return "002_add_sync_status_table"

    @property
    def version(self) -> str:
        """Return migration version.
        
        Returns:
            Version string.
        """
        return "002"

    @property
    def description(self) -> str:
        """Return migration description.
        
        Returns:
            Description of what this migration does.
        """
        return "Add sync_status table for tracking Jira synchronization state"

    @property
    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.
        
        Returns:
            True if rollback is supported.
        """
        return True

    def up(self, engine) -> None:
        """Apply the migration - create sync_status table.
        
        Args:
            engine: SQLAlchemy engine object.
        """
        LOGGER.info("Creating sync_status table")

        with engine.connect() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sync_status (
                        project_key VARCHAR PRIMARY KEY,
                        last_full_sync TIMESTAMP,
                        last_incremental_sync TIMESTAMP,
                        last_sync_status VARCHAR(20),
                        issues_synced INTEGER DEFAULT 0,
                        issues_failed INTEGER DEFAULT 0,
                        sync_duration_seconds FLOAT,
                        errors JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """,
                ),
            )

            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sync_status_last_full_sync 
                    ON sync_status(last_full_sync DESC)
                    """,
                ),
            )

            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sync_status_last_incremental 
                    ON sync_status(last_incremental_sync DESC)
                    """,
                ),
            )
            
            connection.commit()

        LOGGER.info("sync_status table created successfully")

    def down(self, engine) -> None:
        """Rollback the migration - drop sync_status table.
        
        Args:
            engine: SQLAlchemy engine object.
        """
        LOGGER.info("Dropping sync_status table")

        with engine.connect() as connection:
            connection.execute(
                text("DROP INDEX IF EXISTS idx_sync_status_last_incremental"),
            )
            connection.execute(
                text("DROP INDEX IF EXISTS idx_sync_status_last_full_sync"),
            )
            connection.execute(
                text("DROP TABLE IF EXISTS sync_status"),
            )
            
            connection.commit()

        LOGGER.info("sync_status table dropped successfully")
