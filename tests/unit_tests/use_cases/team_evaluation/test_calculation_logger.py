"""Unit tests for CalculationLogger helper."""
import unittest
from datetime import datetime

from jira_telegram_bot.use_cases.team_evaluation.calculation_logger import CalculationLogger
from jira_telegram_bot.entities.team_evaluation_calculation_log import (
    TeamEvaluationCalculationLog,
)


class TestCalculationLogger(unittest.TestCase):
    """Test cases for CalculationLogger helper class."""

    def setUp(self):
        """Set up test fixtures."""
        self.sprint_id = 123
        self.sprint_name = "MYPROJECT SPRINT 50"
        self.developer = "کاظمی"
        self.department = "DevOps"
        self.project = "MYPROJECT"

    def test_log_task_classification(self):
        """Test logging task classification metrics."""
        logs = CalculationLogger.log_task_classification(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            dev_count=5,
            bug_count=3,
            support_count=2,
            high_priority_count=4,
            total_issues=10
        )
        
        # Should create 4 log entries
        self.assertEqual(len(logs), 4)
        
        # All should be TeamEvaluationCalculationLog instances
        for log in logs:
            self.assertIsInstance(log, TeamEvaluationCalculationLog)
            self.assertEqual(log.sprint_id, self.sprint_id)
            self.assertEqual(log.developer_name, self.developer)
            self.assertEqual(log.calculation_type, "metric")
        
        # Verify metric names
        metric_names = [log.metric_name for log in logs]
        self.assertIn("development_task_count", metric_names)
        self.assertIn("bug_task_count", metric_names)
        self.assertIn("support_task_count", metric_names)
        self.assertIn("high_priority_count", metric_names)
        
        # Verify values
        dev_log = next(log for log in logs if log.metric_name == "development_task_count")
        self.assertEqual(dev_log.metric_value, 5.0)
        
        bug_log = next(log for log in logs if log.metric_name == "bug_task_count")
        self.assertEqual(bug_log.metric_value, 3.0)

    def test_log_time_metrics(self):
        """Test logging time tracking metrics."""
        logs = CalculationLogger.log_time_metrics(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            total_hours=40.0,
            expected_hours=44.0,
            dev_hours=30.0,
            bug_hours=8.0,
            support_hours=2.0,
            worklog_count=20,
            filtered_count=3
        )
        
        # Should create 5 log entries
        self.assertEqual(len(logs), 5)
        
        # Verify metric names
        metric_names = [log.metric_name for log in logs]
        self.assertIn("registered_hours_total", metric_names)
        self.assertIn("expected_hours_week", metric_names)
        self.assertIn("development_hours", metric_names)
        self.assertIn("bug_hours", metric_names)
        self.assertIn("support_hours", metric_names)
        
        # Verify total hours log
        total_hours_log = next(log for log in logs if log.metric_name == "registered_hours_total")
        self.assertEqual(total_hours_log.metric_value, 40.0)
        self.assertIn("40.0 hours", total_hours_log.calculation_details)
        self.assertIn("20 worklogs", total_hours_log.calculation_details)
        
        # Verify expected hours log
        expected_log = next(log for log in logs if log.metric_name == "expected_hours_week")
        self.assertEqual(expected_log.metric_value, 44.0)

    def test_log_deadline_score(self):
        """Test logging deadline score calculation."""
        log = CalculationLogger.log_deadline_score(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            deadline_penalty=14.5,
            deadline_score=85.5,
            tasks_with_deadlines=8,
            avg_delta_days=2.3,
            weight=0.3
        )
        
        self.assertIsInstance(log, TeamEvaluationCalculationLog)
        self.assertEqual(log.calculation_type, "score_component")
        self.assertEqual(log.metric_name, "deadline_score")
        self.assertEqual(log.metric_value, 85.5)
        self.assertEqual(log.weight, 0.3)
        self.assertEqual(log.contribution_to_total, 85.5 * 0.3)
        
        # Verify details contain key information
        self.assertIn("penalty of 14.5", log.calculation_details)
        self.assertIn("8 tasks", log.calculation_details)
        self.assertIn("2.3 days", log.calculation_details)

    def test_log_worklog_score(self):
        """Test logging worklog score calculation."""
        log = CalculationLogger.log_worklog_score(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            registered_hours=40.0,
            expected_hours=44.0,
            worklog_score=90.91,
            weight=0.25
        )
        
        self.assertIsInstance(log, TeamEvaluationCalculationLog)
        self.assertEqual(log.calculation_type, "score_component")
        self.assertEqual(log.metric_name, "worklog_score")
        self.assertEqual(log.metric_value, 90.91)
        self.assertEqual(log.weight, 0.25)
        
        # Verify formula and details
        self.assertIn("registered_hours / expected_hours", log.calculation_formula)
        self.assertIn("40.0 hours", log.calculation_details)
        self.assertIn("44.0 hours", log.calculation_details)

    def test_log_high_priority_score(self):
        """Test logging high priority score calculation."""
        log = CalculationLogger.log_high_priority_score(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            required_tasks=10,
            completed_required=8,
            high_priority_score=80.0,
            weight=0.25
        )
        
        self.assertIsInstance(log, TeamEvaluationCalculationLog)
        self.assertEqual(log.metric_name, "high_priority_score")
        self.assertEqual(log.metric_value, 80.0)
        self.assertEqual(log.weight, 0.25)
        
        # Verify details
        self.assertIn("8 out of 10", log.calculation_details)
        self.assertIn("50% of capacity", log.calculation_details)

    def test_log_defect_score(self):
        """Test logging defect score calculation."""
        log = CalculationLogger.log_defect_score(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            support_bugs_per_story=0.2,
            tester_bugs_per_story=0.3,
            defect_score=85.0,
            weight=0.2,
            support_threshold=0.3,
            tester_threshold=0.4
        )
        
        self.assertIsInstance(log, TeamEvaluationCalculationLog)
        self.assertEqual(log.metric_name, "defect_score")
        self.assertEqual(log.metric_value, 85.0)
        self.assertEqual(log.weight, 0.2)
        
        # Verify details contain threshold information
        self.assertIn("0.20", log.calculation_details)
        self.assertIn("0.30", log.calculation_details)
        self.assertIn("threshold", log.calculation_details)

    def test_log_final_score(self):
        """Test logging final composite score."""
        log = CalculationLogger.log_final_score(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            composite_score=73.5,
            penalties_applied=5.0,
            bonuses_applied=6.5,
            final_score=75
        )
        
        self.assertIsInstance(log, TeamEvaluationCalculationLog)
        self.assertEqual(log.calculation_type, "final_score")
        self.assertEqual(log.metric_name, "quality_score_total")
        self.assertEqual(log.metric_value, 75.0)
        
        # Verify details contain all components
        self.assertIn("73.5", log.calculation_details)
        self.assertIn("5.0", log.calculation_details)
        self.assertIn("6.5", log.calculation_details)
        self.assertIn("75", log.calculation_details)

    def test_all_logs_have_timestamps(self):
        """Test that all generated logs have timestamps."""
        logs = CalculationLogger.log_task_classification(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            dev_count=5,
            bug_count=3,
            support_count=2,
            high_priority_count=4,
            total_issues=10
        )
        
        for log in logs:
            self.assertIsNotNone(log.timestamp)
            self.assertIsInstance(log.timestamp, datetime)

    def test_logs_maintain_consistency(self):
        """Test that all logs for same developer maintain consistent data."""
        logs = CalculationLogger.log_task_classification(
            sprint_id=self.sprint_id,
            sprint_name=self.sprint_name,
            developer=self.developer,
            department=self.department,
            project=self.project,
            dev_count=5,
            bug_count=3,
            support_count=2,
            high_priority_count=4,
            total_issues=10
        )
        
        # All logs should have same sprint/developer/department/project
        for log in logs:
            self.assertEqual(log.sprint_id, self.sprint_id)
            self.assertEqual(log.sprint_name, self.sprint_name)
            self.assertEqual(log.developer_name, self.developer)
            self.assertEqual(log.department, self.department)
            self.assertEqual(log.project, self.project)


if __name__ == "__main__":
    unittest.main()
