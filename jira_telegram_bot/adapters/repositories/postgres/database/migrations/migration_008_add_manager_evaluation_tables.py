"""Migration 008: Add manager evaluation tables.

This migration creates two tables:
1. manager_developer_assignments - Tracks which managers evaluate which developers
2. manager_evaluations - Stores manager evaluation scores for developers
"""
from sqlalchemy import text

from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import MigrationInterface


class Migration008AddManagerEvaluationTables(MigrationInterface):
    """Add manager evaluation tables."""

    @property
    def version(self) -> str:
        """Migration version number."""
        return "008"

    @property
    def description(self) -> str:
        """Migration description."""
        return "Add manager_developer_assignments and manager_evaluations tables"

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back."""
        return True

    def up(self, engine) -> None:
        """Create manager evaluation tables.
        
        Args:
            engine: SQLAlchemy engine
        """
        with engine.connect() as connection:
            # Create manager_developer_assignments table
            connection.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS manager_developer_assignments (
                        id SERIAL PRIMARY KEY,
                        manager_name VARCHAR(255) NOT NULL,
                        developer_name VARCHAR(255) NOT NULL,
                        department VARCHAR(100) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(manager_name, developer_name)
                    )
                """)
            )
            connection.commit()

            # Create index on manager_name for faster lookups
            connection.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS idx_manager_assignments_manager 
                    ON manager_developer_assignments(manager_name) 
                    WHERE is_active = TRUE
                """)
            )
            connection.commit()

            # Create index on developer_name
            connection.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS idx_manager_assignments_developer 
                    ON manager_developer_assignments(developer_name) 
                    WHERE is_active = TRUE
                """)
            )
            connection.commit()

            # Create manager_evaluations table
            connection.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS manager_evaluations (
                        id SERIAL PRIMARY KEY,
                        sprint_id BIGINT NOT NULL,
                        developer_name VARCHAR(255) NOT NULL,
                        manager_name VARCHAR(255) NOT NULL,
                        evaluation_month VARCHAR(7) NOT NULL,
                        collaboration_score INTEGER CHECK (collaboration_score >= 0 AND collaboration_score <= 100),
                        alignment_score INTEGER CHECK (alignment_score >= 0 AND alignment_score <= 100),
                        total_manager_score INTEGER CHECK (total_manager_score >= 0 AND total_manager_score <= 100),
                        comments TEXT,
                        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(sprint_id, developer_name, manager_name)
                    )
                """)
            )
            connection.commit()

            # Create composite index for faster queries
            connection.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS idx_manager_evaluations_sprint_dev 
                    ON manager_evaluations(sprint_id, developer_name)
                """)
            )
            connection.commit()

            # Create index on evaluation_month for monthly reports
            connection.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS idx_manager_evaluations_month 
                    ON manager_evaluations(evaluation_month)
                """)
            )
            connection.commit()

            # Create index on manager_name
            connection.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS idx_manager_evaluations_manager 
                    ON manager_evaluations(manager_name)
                """)
            )
            connection.commit()

    def down(self, engine) -> None:
        """Drop manager evaluation tables.
        
        Args:
            engine: SQLAlchemy engine
        """
        with engine.connect() as connection:
            # Drop tables in reverse order
            connection.execute(
                text("DROP TABLE IF EXISTS manager_evaluations CASCADE")
            )
            connection.commit()

            connection.execute(
                text("DROP TABLE IF EXISTS manager_developer_assignments CASCADE")
            )
            connection.commit()
