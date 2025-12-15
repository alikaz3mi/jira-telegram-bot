"""Migration 006: Add team evaluation calculation log table."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration006AddTeamEvaluationCalculationLog(MigrationInterface):
    """Migration to create team_evaluation_calculation_log table."""

    @property
    def version(self) -> str:
        """Migration version identifier.

        Returns:
            Version string.
        """
        return "006"

    @property
    def description(self) -> str:
        """Get migration description.

        Returns:
            Description string.
        """
        return "Add team_evaluation_calculation_log table for detailed score calculation audit trail"

    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.

        Returns:
            True if rollback is supported.
        """
        return True

    def up(self, engine) -> None:
        """Create team_evaluation_calculation_log table.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Creating team_evaluation_calculation_log table")

        with engine.connect() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS team_evaluation_calculation_log (
                        id SERIAL PRIMARY KEY,
                        sprint_id INTEGER NOT NULL,
                        sprint_name VARCHAR(255) NOT NULL,
                        developer_name VARCHAR(255) NOT NULL,
                        department VARCHAR(255) NOT NULL,
                        project VARCHAR(255) NOT NULL,
                        calculation_type VARCHAR(50) NOT NULL,
                        metric_name VARCHAR(255) NOT NULL,
                        metric_value FLOAT NOT NULL,
                        calculation_formula TEXT NOT NULL,
                        calculation_details TEXT NOT NULL,
                        weight FLOAT,
                        contribution_to_total FLOAT,
                        evaluation_id INTEGER,
                        timestamp TIMESTAMP NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.commit()

            # Create indexes
            LOGGER.info("Creating indexes on team_evaluation_calculation_log")
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_calc_log_sprint_developer 
                    ON team_evaluation_calculation_log (sprint_id, developer_name)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_calc_log_evaluation_id 
                    ON team_evaluation_calculation_log (evaluation_id)
                    """
                )
            )
            connection.commit()

        LOGGER.info("team_evaluation_calculation_log table created successfully")

    def down(self, engine) -> None:
        """Rollback the migration - drop team_evaluation_calculation_log table.

        Args:
            engine: SQLAlchemy engine.
        """
        LOGGER.info("Dropping team_evaluation_calculation_log table")

        with engine.connect() as connection:
            connection.execute(
                text("DROP TABLE IF EXISTS team_evaluation_calculation_log CASCADE")
            )
            connection.commit()

        LOGGER.info("team_evaluation_calculation_log table dropped successfully")

