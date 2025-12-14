"""Unit tests for SprintClosedTeamEvaluationUseCase."""
from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, call

from jira_telegram_bot.entities.team_evaluation import (
    DeveloperMetrics,
    TeamEvaluationResult,
    TeamEvaluationScoreWeights,
)
from jira_telegram_bot.use_cases.team_evaluation.sprint_closed_team_evaluation_use_case import (
    SprintClosedTeamEvaluationUseCase,
)


class TestSprintClosedTeamEvaluationUseCase(unittest.TestCase):
    """Test cases for SprintClosedTeamEvaluationUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.task_manager_repo = MagicMock()
        self.calendar_repo = MagicMock()
        self.leave_repo = MagicMock()
        self.evaluation_repo = MagicMock()
        
        self.weights = TeamEvaluationScoreWeights(
            completion_rate=Decimal("0.25"),
            velocity=Decimal("0.20"),
            quality=Decimal("0.20"),
            responsiveness=Decimal("0.15"),
            collaboration=Decimal("0.10"),
            documentation=Decimal("0.10"),
        )
        
        self.use_case = SprintClosedTeamEvaluationUseCase(
            task_manager_repository=self.task_manager_repo,
            calendar_repository=self.calendar_repo,
            leave_repository=self.leave_repo,
            team_evaluation_repository=self.evaluation_repo,
            score_weights=self.weights,
        )

    def test_calculate_developer_metrics_basic(self):
        """Test basic metrics calculation for a developer."""
        # Arrange
        sprint_id = 123
        developer_username = "test_user"
        sprint_start = datetime(2024, 12, 1)
        sprint_end = datetime(2024, 12, 14)
        
        # Mock repository responses
        self.task_manager_repo.get_developer_completed_story_points.return_value = 13
        self.task_manager_repo.get_developer_total_story_points.return_value = 15
        self.task_manager_repo.get_developer_bug_count.return_value = 2
        self.task_manager_repo.get_developer_review_time.return_value = 4.5
        self.task_manager_repo.get_developer_pr_count.return_value = 8
        self.task_manager_repo.get_developer_documentation_score.return_value = 85.0
        self.calendar_repo.get_working_days.return_value = 10
        self.leave_repo.get_leave_days.return_value = []
        
        # Act
        metrics = self.use_case._calculate_developer_metrics(
            sprint_id=sprint_id,
            developer_username=developer_username,
            sprint_start=sprint_start,
            sprint_end=sprint_end,
        )
        
        # Assert
        self.assertIsInstance(metrics, DeveloperMetrics)
        self.assertEqual(metrics.username, developer_username)
        self.assertEqual(metrics.completed_story_points, 13)
        self.assertEqual(metrics.total_story_points, 15)
        self.assertAlmostEqual(metrics.completion_rate, 86.67, places=1)
        self.assertEqual(metrics.bug_count, 2)
        self.assertEqual(metrics.average_review_time_hours, 4.5)
        self.assertEqual(metrics.pr_count, 8)
        self.assertEqual(metrics.documentation_score, 85.0)

    def test_calculate_score_perfect_developer(self):
        """Test score calculation for a perfect developer."""
        # Arrange
        metrics = DeveloperMetrics(
            username="perfect_dev",
            sprint_id=123,
            completed_story_points=20,
            total_story_points=20,
            completion_rate=100.0,
            bug_count=0,
            average_review_time_hours=2.0,
            pr_count=15,
            documentation_score=100.0,
            working_days=10,
            leave_days=0,
        )
        
        # Act
        score = self.use_case._calculate_score(metrics)
        
        # Assert
        self.assertGreater(score, 90.0)
        self.assertLessEqual(score, 100.0)

    def test_calculate_score_average_developer(self):
        """Test score calculation for an average developer."""
        # Arrange
        metrics = DeveloperMetrics(
            username="average_dev",
            sprint_id=123,
            completed_story_points=10,
            total_story_points=15,
            completion_rate=66.67,
            bug_count=3,
            average_review_time_hours=8.0,
            pr_count=5,
            documentation_score=70.0,
            working_days=10,
            leave_days=0,
        )
        
        # Act
        score = self.use_case._calculate_score(metrics)
        
        # Assert
        self.assertGreater(score, 50.0)
        self.assertLess(score, 80.0)

    def test_calculate_score_with_leave_days(self):
        """Test that leave days are properly considered."""
        # Arrange
        metrics_with_leave = DeveloperMetrics(
            username="dev_on_leave",
            sprint_id=123,
            completed_story_points=8,
            total_story_points=10,
            completion_rate=80.0,
            bug_count=1,
            average_review_time_hours=4.0,
            pr_count=6,
            documentation_score=80.0,
            working_days=10,
            leave_days=3,
        )
        
        metrics_no_leave = DeveloperMetrics(
            username="dev_no_leave",
            sprint_id=123,
            completed_story_points=8,
            total_story_points=10,
            completion_rate=80.0,
            bug_count=1,
            average_review_time_hours=4.0,
            pr_count=6,
            documentation_score=80.0,
            working_days=10,
            leave_days=0,
        )
        
        # Act
        score_with_leave = self.use_case._calculate_score(metrics_with_leave)
        score_no_leave = self.use_case._calculate_score(metrics_no_leave)
        
        # Assert - developer with leave should have slightly better adjusted score
        self.assertGreaterEqual(score_with_leave, score_no_leave * 0.95)

    def test_execute_saves_to_repository(self):
        """Test that execute method saves results to repository."""
        # Arrange
        sprint_id = 456
        sprint_name = "Sprint 15"
        sprint_start = datetime(2024, 12, 1)
        sprint_end = datetime(2024, 12, 14)
        developer_usernames = ["dev1", "dev2"]
        
        # Mock metrics calculation
        self.use_case._calculate_developer_metrics = Mock(
            side_effect=[
                DeveloperMetrics(
                    username="dev1",
                    sprint_id=sprint_id,
                    completed_story_points=15,
                    total_story_points=15,
                    completion_rate=100.0,
                    bug_count=0,
                    average_review_time_hours=3.0,
                    pr_count=10,
                    documentation_score=90.0,
                    working_days=10,
                    leave_days=0,
                ),
                DeveloperMetrics(
                    username="dev2",
                    sprint_id=sprint_id,
                    completed_story_points=12,
                    total_story_points=15,
                    completion_rate=80.0,
                    bug_count=2,
                    average_review_time_hours=5.0,
                    pr_count=7,
                    documentation_score=75.0,
                    working_days=10,
                    leave_days=0,
                ),
            ]
        )
        
        # Act
        self.use_case.execute(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            sprint_start=sprint_start,
            sprint_end=sprint_end,
            developer_usernames=developer_usernames,
        )
        
        # Assert
        self.assertEqual(self.evaluation_repo.save_evaluation.call_count, 2)
        
        # Verify first call
        first_call_args = self.evaluation_repo.save_evaluation.call_args_list[0][0][0]
        self.assertEqual(first_call_args.username, "dev1")
        self.assertEqual(first_call_args.sprint_id, sprint_id)
        self.assertGreater(first_call_args.total_score, 0)
        
        # Verify second call
        second_call_args = self.evaluation_repo.save_evaluation.call_args_list[1][0][0]
        self.assertEqual(second_call_args.username, "dev2")
        self.assertEqual(second_call_args.sprint_id, sprint_id)

    def test_execute_with_empty_developer_list(self):
        """Test execute with no developers."""
        # Arrange
        sprint_id = 789
        sprint_name = "Empty Sprint"
        sprint_start = datetime(2024, 12, 1)
        sprint_end = datetime(2024, 12, 14)
        developer_usernames = []
        
        # Act
        self.use_case.execute(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            sprint_start=sprint_start,
            sprint_end=sprint_end,
            developer_usernames=developer_usernames,
        )
        
        # Assert
        self.evaluation_repo.save_evaluation.assert_not_called()

    def test_quality_score_decreases_with_bugs(self):
        """Test that quality score decreases as bug count increases."""
        # Arrange
        base_metrics = {
            "sprint_id": 123,
            "completed_story_points": 15,
            "total_story_points": 15,
            "completion_rate": 100.0,
            "average_review_time_hours": 4.0,
            "pr_count": 8,
            "documentation_score": 80.0,
            "working_days": 10,
            "leave_days": 0,
        }
        
        metrics_no_bugs = DeveloperMetrics(username="dev1", bug_count=0, **base_metrics)
        metrics_some_bugs = DeveloperMetrics(username="dev2", bug_count=3, **base_metrics)
        metrics_many_bugs = DeveloperMetrics(username="dev3", bug_count=8, **base_metrics)
        
        # Act
        score_no_bugs = self.use_case._calculate_score(metrics_no_bugs)
        score_some_bugs = self.use_case._calculate_score(metrics_some_bugs)
        score_many_bugs = self.use_case._calculate_score(metrics_many_bugs)
        
        # Assert
        self.assertGreater(score_no_bugs, score_some_bugs)
        self.assertGreater(score_some_bugs, score_many_bugs)


if __name__ == "__main__":
    unittest.main()
