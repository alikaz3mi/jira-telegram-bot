"""Migration 005: Add team_evaluation table for storing team performance metrics."""
from __future__ import annotations

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_interface import (
    MigrationInterface,
)


class Migration005AddTeamEvaluation(MigrationInterface):
    """Add team_evaluation table for sprint performance tracking."""

    def get_migration_id(self) -> str:
        """Return unique migration identifier.
        
        Returns:
            Migration ID string.
        """
        return "005_add_team_evaluation"

    @property
    def version(self) -> str:
        """Get migration version number.
        
        Returns:
            Version string.
        """
        return "005"

    @property
    def description(self) -> str:
        """Get migration description.
        
        Returns:
            Description string.
        """
        return "Add team_evaluation table for storing developer performance metrics per sprint"

    @property
    def can_rollback(self) -> bool:
        """Check if migration can be rolled back.
        
        Returns:
            True if rollback is supported.
        """
        return True

    def up(self, engine) -> None:
        """Apply the migration - create team_evaluation table.
        
        Args:
            engine: SQLAlchemy engine object.
        """
        LOGGER.info("Creating team_evaluation table")

        with engine.connect() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS team_evaluation (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        
                        -- Sprint and developer identification
                        sprint_id INTEGER NOT NULL,
                        sprint_name VARCHAR(255) NOT NULL,
                        developer_name VARCHAR(255) NOT NULL,
                        department VARCHAR(100) NOT NULL,
                        project VARCHAR(100) NOT NULL,
                        
                        -- Task counts
                        development_count INTEGER NOT NULL DEFAULT 0,
                        bug_count INTEGER NOT NULL DEFAULT 0,
                        support_count INTEGER NOT NULL DEFAULT 0,
                        high_priority_count INTEGER NOT NULL DEFAULT 0,
                        
                        -- Time metrics (hours)
                        registered_hours_week FLOAT NOT NULL DEFAULT 0,
                        expected_hours_week FLOAT NOT NULL DEFAULT 0,
                        bug_hours FLOAT NOT NULL DEFAULT 0,
                        development_hours FLOAT NOT NULL DEFAULT 0,
                        support_hours FLOAT NOT NULL DEFAULT 0,
                        
                        -- Performance metrics
                        avg_deadline_delivery_days VARCHAR(50),
                        review_back_count INTEGER NOT NULL DEFAULT 0,
                        story_test_pass_rate VARCHAR(50),
                        acceptance_criteria_pass_rate VARCHAR(50),
                        
                        -- Completion metrics
                        high_priority_completed_count INTEGER NOT NULL DEFAULT 0,
                        development_delivered_count INTEGER NOT NULL DEFAULT 0,
                        bug_delivered_count INTEGER NOT NULL DEFAULT 0,
                        support_delivered_count INTEGER NOT NULL DEFAULT 0,
                        
                        -- Defect metrics
                        avg_support_bugs_per_story FLOAT NOT NULL DEFAULT 0,
                        avg_tester_bugs_per_story FLOAT NOT NULL DEFAULT 0,
                        
                        -- Quality score
                        quality_score INTEGER NOT NULL DEFAULT 0,
                        
                        -- Unique constraint to prevent duplicate entries
                        CONSTRAINT unique_sprint_developer_dept_project 
                            UNIQUE (sprint_id, developer_name, department, project)
                    );
                    
                    -- Create indexes for common queries
                    CREATE INDEX IF NOT EXISTS idx_team_eval_sprint_id 
                        ON team_evaluation (sprint_id);
                    CREATE INDEX IF NOT EXISTS idx_team_eval_developer 
                        ON team_evaluation (developer_name);
                    CREATE INDEX IF NOT EXISTS idx_team_eval_department 
                        ON team_evaluation (department);
                    CREATE INDEX IF NOT EXISTS idx_team_eval_created_at 
                        ON team_evaluation (created_at);
                    """
                )
            )
            connection.commit()

        LOGGER.info("Successfully created team_evaluation table")

    def down(self, engine) -> None:
        """Revert the migration - drop team_evaluation table.
        
        Args:
            engine: SQLAlchemy engine object.
        """
        LOGGER.info("Dropping team_evaluation table")

        with engine.connect() as connection:
            connection.execute(
                text("DROP TABLE IF EXISTS team_evaluation CASCADE")
            )
            connection.commit()

        LOGGER.info("Successfully dropped team_evaluation table")
