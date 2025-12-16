"""Integration tests for TeamEvaluationRepository."""
from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal

from jira_telegram_bot.adapters.repositories.postgres.team_evaluation_repository import (
    PostgresTeamEvaluationRepository,
)
from jira_telegram_bot.adapters.repositories.postgres.database.postgresql_connection import (
    PostgreSQLConnection,
)
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.team_evaluation import (
    DeveloperMetrics,
    TeamEvaluationResult,
)
from jira_telegram_bot.settings.database_settings import DatabaseSettings
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)


class TestTeamEvaluationRepositoryIntegration(unittest.TestCase):
    """Integration tests for TeamEvaluationRepository with PostgreSQL."""

    @classmethod
    def setUpClass(cls):
        """Set up test database connection."""
        container = get_container()
        cls.db_connection = container[DatabaseConnectionInterface]
        cls.repository = PostgresTeamEvaluationRepository(cls.db_connection)

    def setUp(self):
        """Clean up test data before each test."""
        self._cleanup_test_data()

    def tearDown(self):
        """Clean up test data after each test."""
        self._cleanup_test_data()

    def _cleanup_test_data(self):
        """Remove test data from database."""
        engine = self.db_connection.get_engine()
        with engine.connect() as conn:
            # Delete test evaluations
            conn.execute(
                conn.text(
                    "DELETE FROM team_evaluations "
                    "WHERE sprint_id >= 999990"
                )
            )
            conn.commit()

    def test_save_and_get_evaluation(self):
        """Test saving and retrieving an evaluation."""
        # Arrange
        evaluation = TeamEvaluationResult(
            username="test_developer",
            sprint_id=999991,
            sprint_name="Test Sprint 1",
            sprint_start=datetime(2024, 12, 1),
            sprint_end=datetime(2024, 12, 14),
            metrics=DeveloperMetrics(
                username="test_developer",
                sprint_id=999991,
                completed_story_points=15,
                total_story_points=20,
                completion_rate=75.0,
                bug_count=2,
                average_review_time_hours=4.5,
                pr_count=8,
                documentation_score=85.0,
                working_days=10,
                leave_days=0,
            ),
            total_score=82.5,
            score_breakdown={
                "completion_rate": 18.75,
                "velocity": 16.0,
                "quality": 16.0,
                "responsiveness": 12.0,
                "collaboration": 8.0,
                "documentation": 8.5,
            },
        )
        
        # Act
        self.repository.save_evaluation(evaluation)
        result = self.repository.get_evaluation(
            username="test_developer",
            sprint_id=999991
        )
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.username, "test_developer")
        self.assertEqual(result.sprint_id, 999991)
        self.assertEqual(result.sprint_name, "Test Sprint 1")
        self.assertEqual(result.total_score, 82.5)
        self.assertEqual(result.metrics.completed_story_points, 15)
        self.assertEqual(result.metrics.bug_count, 2)

    def test_get_sprint_evaluations(self):
        """Test retrieving all evaluations for a sprint."""
        # Arrange
        sprint_id = 999992
        developers = ["dev1", "dev2", "dev3"]
        
        for i, dev in enumerate(developers):
            evaluation = TeamEvaluationResult(
                username=dev,
                sprint_id=sprint_id,
                sprint_name="Test Sprint 2",
                sprint_start=datetime(2024, 12, 1),
                sprint_end=datetime(2024, 12, 14),
                metrics=DeveloperMetrics(
                    username=dev,
                    sprint_id=sprint_id,
                    completed_story_points=10 + i * 5,
                    total_story_points=20,
                    completion_rate=50.0 + i * 25,
                    bug_count=i,
                    average_review_time_hours=4.0,
                    pr_count=5 + i * 2,
                    documentation_score=70.0 + i * 10,
                    working_days=10,
                    leave_days=0,
                ),
                total_score=60.0 + i * 15,
                score_breakdown={},
            )
            self.repository.save_evaluation(evaluation)
        
        # Act
        results = self.repository.get_sprint_evaluations(sprint_id)
        
        # Assert
        self.assertEqual(len(results), 3)
        usernames = [r.username for r in results]
        self.assertIn("dev1", usernames)
        self.assertIn("dev2", usernames)
        self.assertIn("dev3", usernames)

    def test_get_developer_history(self):
        """Test retrieving evaluation history for a developer."""
        # Arrange
        username = "history_dev"
        sprint_ids = [999993, 999994, 999995]
        
        for sprint_id in sprint_ids:
            evaluation = TeamEvaluationResult(
                username=username,
                sprint_id=sprint_id,
                sprint_name=f"Sprint {sprint_id}",
                sprint_start=datetime(2024, 12, 1),
                sprint_end=datetime(2024, 12, 14),
                metrics=DeveloperMetrics(
                    username=username,
                    sprint_id=sprint_id,
                    completed_story_points=15,
                    total_story_points=20,
                    completion_rate=75.0,
                    bug_count=1,
                    average_review_time_hours=4.0,
                    pr_count=8,
                    documentation_score=80.0,
                    working_days=10,
                    leave_days=0,
                ),
                total_score=80.0,
                score_breakdown={},
            )
            self.repository.save_evaluation(evaluation)
        
        # Act
        results = self.repository.get_developer_history(
            username=username,
            limit=10
        )
        
        # Assert
        self.assertEqual(len(results), 3)
        result_sprint_ids = [r.sprint_id for r in results]
        for sprint_id in sprint_ids:
            self.assertIn(sprint_id, result_sprint_ids)

    def test_update_existing_evaluation(self):
        """Test updating an existing evaluation."""
        # Arrange
        initial_evaluation = TeamEvaluationResult(
            username="update_dev",
            sprint_id=999996,
            sprint_name="Update Sprint",
            sprint_start=datetime(2024, 12, 1),
            sprint_end=datetime(2024, 12, 14),
            metrics=DeveloperMetrics(
                username="update_dev",
                sprint_id=999996,
                completed_story_points=10,
                total_story_points=20,
                completion_rate=50.0,
                bug_count=5,
                average_review_time_hours=8.0,
                pr_count=4,
                documentation_score=60.0,
                working_days=10,
                leave_days=0,
            ),
            total_score=55.0,
            score_breakdown={},
        )
        
        self.repository.save_evaluation(initial_evaluation)
        
        # Act - Update with new values
        updated_evaluation = TeamEvaluationResult(
            username="update_dev",
            sprint_id=999996,
            sprint_name="Update Sprint",
            sprint_start=datetime(2024, 12, 1),
            sprint_end=datetime(2024, 12, 14),
            metrics=DeveloperMetrics(
                username="update_dev",
                sprint_id=999996,
                completed_story_points=18,
                total_story_points=20,
                completion_rate=90.0,
                bug_count=1,
                average_review_time_hours=3.0,
                pr_count=10,
                documentation_score=95.0,
                working_days=10,
                leave_days=0,
            ),
            total_score=92.0,
            score_breakdown={},
        )
        
        self.repository.save_evaluation(updated_evaluation)
        result = self.repository.get_evaluation("update_dev", 999996)
        
        # Assert
        self.assertEqual(result.total_score, 92.0)
        self.assertEqual(result.metrics.completed_story_points, 18)
        self.assertEqual(result.metrics.bug_count, 1)

    def test_get_nonexistent_evaluation(self):
        """Test retrieving an evaluation that doesn't exist."""
        # Act
        result = self.repository.get_evaluation(
            username="nonexistent_user",
            sprint_id=999999
        )
        
        # Assert
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
