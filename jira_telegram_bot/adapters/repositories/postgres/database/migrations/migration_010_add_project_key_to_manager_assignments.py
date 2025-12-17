"""Migration 010: Add project_key to manager_developer_assignments table.

This migration adds project_key column to support project-specific manager assignments.
A manager can evaluate the same developer in different projects.
"""

from sqlalchemy import text

from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration010AddProjectKeyToManagerAssignments(MigrationInterface):
    """Add project_key column to manager_developer_assignments table."""

    @property
    def version(self) -> str:
        """Return migration version."""
        return "010"

    @property
    def description(self) -> str:
        """Return migration description."""
        return "Add project_key to manager_developer_assignments for project-specific assignments"

    def up(self, engine) -> None:
        """Add project_key column and update constraints.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        with engine.connect() as connection:
            # Add project_key column (nullable initially)
            connection.execute(
                text(
                    """
                    ALTER TABLE manager_developer_assignments 
                    ADD COLUMN IF NOT EXISTS project_key VARCHAR(50)
                    """
                )
            )
            connection.commit()

            # Drop old unique constraint if exists
            connection.execute(
                text(
                    """
                    DROP INDEX IF EXISTS idx_manager_dev_assignment_unique
                    """
                )
            )
            connection.commit()

            # Create new unique constraint including project_key
            # This allows same manager-developer pair in different projects
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_manager_dev_assignment_unique 
                    ON manager_developer_assignments(manager_name, developer_name, project_key)
                    WHERE is_active = TRUE
                    """
                )
            )
            connection.commit()

            # Add index on project_key for queries
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_manager_dev_assignments_project 
                    ON manager_developer_assignments(project_key)
                    """
                )
            )
            connection.commit()

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.
        
        Returns:
            True since this migration can be safely rolled back.
        """
        return True

    def down(self, engine) -> None:
        """Remove project_key column and restore old constraints.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        with engine.connect() as connection:
            # Drop new indexes
            connection.execute(
                text(
                    """
                    DROP INDEX IF EXISTS idx_manager_dev_assignment_unique
                    """
                )
            )
            connection.commit()

            connection.execute(
                text(
                    """
                    DROP INDEX IF EXISTS idx_manager_dev_assignments_project
                    """
                )
            )
            connection.commit()

            # Recreate old unique constraint (without project_key)
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_manager_dev_assignment_unique 
                    ON manager_developer_assignments(manager_name, developer_name)
                    WHERE is_active = TRUE
                    """
                )
            )
            connection.commit()

            # Drop project_key column
            connection.execute(
                text(
                    """
                    ALTER TABLE manager_developer_assignments 
                    DROP COLUMN IF EXISTS project_key
                    """
                )
            )
            connection.commit()
