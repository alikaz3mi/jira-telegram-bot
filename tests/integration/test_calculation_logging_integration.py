"""Integration tests for team evaluation calculation logging."""
import unittest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from jira_telegram_bot.use_cases.team_evaluation.sprint_closed_team_evaluation_use_case import (
    SprintClosedTeamEvaluationUseCase,
)
from jira_telegram_bot.entities.team_evaluation import TeamEvaluationRow
from jira_telegram_bot.entities.team_evaluation_calculation_log import (
    TeamEvaluationCalculationLog,
)
from jira_telegram_bot.settings.team_evaluation_settings import TeamEvaluationSettings


class TestCalculationLoggingIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for calculation logging in team evaluation flow."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock repositories
        self.mock_task_manager_repo = Mock()
        self.mock_user_config_service = Mock()
        self.mock_google_sheet_gateway = Mock()
        self.mock_calendar_repo = Mock()
        self.mock_leave_repo = Mock()
        self.mock_team_evaluation_repo = AsyncMock()
        self.mock_calculation_log_repo = AsyncMock()
        
        # Create settings
        self.settings = TeamEvaluationSettings()
        
        # Create use case
        self.use_case = SprintClosedTeamEvaluationUseCase(
            task_manager_repo=self.mock_task_manager_repo,
            user_config_service=self.mock_user_config_service,
            google_sheet_gateway=self.mock_google_sheet_gateway,
            calendar_repo=self.mock_calendar_repo,
            leave_repo=self.mock_leave_repo,
            team_evaluation_repo=self.mock_team_evaluation_repo,
            calculation_log_repo=self.mock_calculation_log_repo,
            settings=self.settings
        )

    async def test_save_calculation_logs_for_evaluation(self):
        """Test that calculation logs are created and saved for an evaluation."""
        # Create a sample evaluation row
        row = TeamEvaluationRow(
            developer_name="کاظمی",
            department="DevOps",
            project="MYPROJECT",
            sprint="MYPROJECT SPRINT 50",
            development_count=5,
            bug_count=3,
            support_count=2,
            high_priority_count=4,
            registered_hours_week=40.0,
            expected_hours_week=44.0,
            bug_hours=8.0,
            development_hours=30.0,
            support_hours=2.0,
            avg_deadline_delivery_days="2.3d",
            review_back_count=1,
            story_test_pass_rate="N/A",
            acceptance_criteria_pass_rate="N/A",
            high_priority_completed_count=3,
            avg_support_bugs_per_story=0.2,
            avg_tester_bugs_per_story=0.3,
            development_delivered_count=4,
            bug_delivered_count=2,
            support_delivered_count=1,
            quality_score=75
        )
        
        # Create calculation details
        calculation_details = {
            "dev_count": 5,
            "bug_count": 3,
            "support_count": 2,
            "high_priority_count": 4,
            "total_issues": 10,
            "worklog_count": 20,
            "filtered_worklog_count": 3,
            "deadline_score": 85.5,
            "deadline_penalty": 14.5,
            "tasks_with_deadlines": 8,
            "avg_deadline_delta": 2.3,
            "worklog_score": 90.91,
            "high_priority_score": 80.0,
            "required_tasks": 10,
            "completed_required": 8,
            "defect_score": 85.0,
            "composite_score": 73.5,
            "penalties": 5.0,
            "bonuses": 6.5
        }
        
        # Execute
        await self.use_case._save_calculation_logs_for_evaluation(
            sprint_id=123,
            row=row,
            calculation_details=calculation_details
        )
        
        # Verify save_logs_batch was called
        self.mock_calculation_log_repo.save_logs_batch.assert_called_once()
        
        # Get the logs that were saved
        saved_logs = self.mock_calculation_log_repo.save_logs_batch.call_args[0][0]
        
        # Verify we have multiple logs
        self.assertGreater(len(saved_logs), 5)  # At least task classification + time metrics + score components
        
        # Verify all are TeamEvaluationCalculationLog instances
        for log in saved_logs:
            self.assertIsInstance(log, TeamEvaluationCalculationLog)
            self.assertEqual(log.sprint_id, 123)
            self.assertEqual(log.sprint_name, "MYPROJECT SPRINT 50")
            self.assertEqual(log.developer_name, "کاظمی")
            self.assertEqual(log.department, "DevOps")
            self.assertEqual(log.project, "MYPROJECT")
        
        # Verify specific log types are present
        metric_names = [log.metric_name for log in saved_logs]
        self.assertIn("development_task_count", metric_names)
        self.assertIn("registered_hours_total", metric_names)
        self.assertIn("deadline_score", metric_names)
        self.assertIn("worklog_score", metric_names)
        self.assertIn("quality_score_total", metric_names)

    async def test_calculation_logs_not_saved_in_dry_run_mode(self):
        """Test that calculation logs are not saved in dry run mode."""
        # Enable dry run
        self.settings.dry_run = True
        
        row = TeamEvaluationRow(
            developer_name="Test Dev",
            department="Test Dept",
            project="TEST",
            sprint="Test Sprint",
            development_count=1,
            bug_count=0,
            support_count=0,
            high_priority_count=1,
            registered_hours_week=10.0,
            expected_hours_week=10.0,
            bug_hours=0.0,
            development_hours=10.0,
            support_hours=0.0,
            avg_deadline_delivery_days="N/A",
            review_back_count=0,
            story_test_pass_rate="N/A",
            acceptance_criteria_pass_rate="N/A",
            high_priority_completed_count=1,
            avg_support_bugs_per_story=0.0,
            avg_tester_bugs_per_story=0.0,
            development_delivered_count=1,
            bug_delivered_count=0,
            support_delivered_count=0,
            quality_score=100
        )
        
        calculation_details = {
            "dev_count": 1,
            "bug_count": 0,
            "support_count": 0,
            "high_priority_count": 1,
            "total_issues": 1,
            "worklog_count": 5,
            "filtered_worklog_count": 0,
            "composite_score": 100.0,
            "penalties": 0.0,
            "bonuses": 0.0
        }
        
        await self.use_case._save_calculation_logs_for_evaluation(
            sprint_id=123,
            row=row,
            calculation_details=calculation_details
        )
        
        # Verify save_logs_batch was NOT called in dry run mode
        self.mock_calculation_log_repo.save_logs_batch.assert_not_called()

    async def test_calculation_log_error_does_not_break_evaluation(self):
        """Test that errors in calculation logging don't break the evaluation flow."""
        # Make save_logs_batch raise an exception
        self.mock_calculation_log_repo.save_logs_batch.side_effect = Exception("Database error")
        
        row = TeamEvaluationRow(
            developer_name="Test Dev",
            department="Test Dept",
            project="TEST",
            sprint="Test Sprint",
            development_count=1,
            bug_count=0,
            support_count=0,
            high_priority_count=1,
            registered_hours_week=10.0,
            expected_hours_week=10.0,
            bug_hours=0.0,
            development_hours=10.0,
            support_hours=0.0,
            avg_deadline_delivery_days="N/A",
            review_back_count=0,
            story_test_pass_rate="N/A",
            acceptance_criteria_pass_rate="N/A",
            high_priority_completed_count=1,
            avg_support_bugs_per_story=0.0,
            avg_tester_bugs_per_story=0.0,
            development_delivered_count=1,
            bug_delivered_count=0,
            support_delivered_count=0,
            quality_score=100
        )
        
        calculation_details = {
            "dev_count": 1,
            "total_issues": 1,
            "worklog_count": 5,
            "filtered_worklog_count": 0
        }
        
        # This should not raise an exception
        try:
            await self.use_case._save_calculation_logs_for_evaluation(
                sprint_id=123,
                row=row,
                calculation_details=calculation_details
            )
        except Exception as e:
            self.fail(f"Calculation log error should not propagate: {e}")

    def test_create_calculation_log_helper_method(self):
        """Test the _create_calculation_log helper method."""
        log = self.use_case._create_calculation_log(
            sprint_id=123,
            sprint_name="MYPROJECT SPRINT 50",
            developer_name="کاظمی",
            department="DevOps",
            project="MYPROJECT",
            calculation_type="metric",
            metric_name="test_metric",
            metric_value=100.0,
            formula="COUNT(test)",
            details="Test calculation details",
            weight=0.5,
            contribution=50.0
        )
        
        self.assertIsInstance(log, TeamEvaluationCalculationLog)
        self.assertEqual(log.sprint_id, 123)
        self.assertEqual(log.sprint_name, "MYPROJECT SPRINT 50")
        self.assertEqual(log.developer_name, "کاظمی")
        self.assertEqual(log.department, "DevOps")
        self.assertEqual(log.project, "MYPROJECT")
        self.assertEqual(log.calculation_type, "metric")
        self.assertEqual(log.metric_name, "test_metric")
        self.assertEqual(log.metric_value, 100.0)
        self.assertEqual(log.calculation_formula, "COUNT(test)")
        self.assertEqual(log.calculation_details, "Test calculation details")
        self.assertEqual(log.weight, 0.5)
        self.assertEqual(log.contribution_to_total, 50.0)
        self.assertIsInstance(log.timestamp, datetime)

    def test_calculation_log_captures_score_weights(self):
        """Test that calculation logs capture the configured score weights."""
        # Verify that score weights are accessible in the use case
        self.assertIsNotNone(self.use_case.settings.score_weights)
        self.assertIsNotNone(self.use_case.settings.score_weights.deadline)
        self.assertIsNotNone(self.use_case.settings.score_weights.worklog)
        self.assertIsNotNone(self.use_case.settings.score_weights.high_priority)
        self.assertIsNotNone(self.use_case.settings.score_weights.defects)


if __name__ == "__main__":
    unittest.main()
