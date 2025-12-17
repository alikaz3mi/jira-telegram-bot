"""Migration 009: Add member_project_roles table for role and rank management.

This migration creates a table to track member roles and ranks across projects.
Members can have different roles in different projects, plus an overall role.
"""

from sqlalchemy import text

from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration009AddMemberProjectRoles(MigrationInterface):
    """Add member_project_roles table."""

    @property
    def version(self) -> str:
        """Return migration version."""
        return "009"

    @property
    def description(self) -> str:
        """Return migration description."""
        return "Add member_project_roles table for role and rank management"

    def up(self, engine) -> None:
        """Create member_project_roles table.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        with engine.connect() as connection:
            # Create member_project_roles table
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS member_project_roles (
                        id SERIAL PRIMARY KEY,
                        member_id VARCHAR(255) NOT NULL,
                        project_key VARCHAR(50),
                        role VARCHAR(100) NOT NULL,
                        rank VARCHAR(50),
                        is_overall BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.commit()

            # Create index on member_id for fast lookups
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_member_project_roles_member_id 
                    ON member_project_roles(member_id)
                    """
                )
            )
            connection.commit()

            # Create index on project_key for project-based queries
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_member_project_roles_project_key 
                    ON member_project_roles(project_key)
                    """
                )
            )
            connection.commit()

            # Create unique constraint for member + project combination
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_member_project_roles_unique 
                    ON member_project_roles(member_id, project_key) 
                    WHERE project_key IS NOT NULL
                    """
                )
            )
            connection.commit()

            # Create unique constraint for overall role (one per member)
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_member_project_roles_overall_unique 
                    ON member_project_roles(member_id) 
                    WHERE is_overall = TRUE
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
        """Drop member_project_roles table.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        with engine.connect() as connection:
            connection.execute(
                text("DROP TABLE IF EXISTS member_project_roles CASCADE")
            )
            connection.commit()
