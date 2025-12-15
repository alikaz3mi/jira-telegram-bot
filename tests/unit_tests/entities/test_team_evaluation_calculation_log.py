"""Unit tests for TeamEvaluationCalculationLog entity."""
import unittest
from datetime import datetime

from jira_telegram_bot.entities.team_evaluation_calculation_log import (
    TeamEvaluationCalculationLog,
)


class TestTeamEvaluationCalculationLog(unittest.TestCase):
    """Test cases for TeamEvaluationCalculationLog entity."""

    def test_create_calculation_log_with_all_fields(self):
        """Test creating a calculation log with all fields populated."""
        timestamp = datetime.utcnow()
        
        log = TeamEvaluationCalculationLog(
            sprint_id=123,
            sprint_name="PARSCHAT SPRINT 50",
            developer_name="کاظمی",
            department="DevOps",
            project="PARSCHAT",
            calculation_type="score_component",
            metric_name="deadline_score",
            metric_value=85.5,
            calculation_formula="max(0, 100 - per_task_deadline_penalties)",
            calculation_details="Deadline score: Started with 100, subtracted penalty of 14.5",
            weight=0.3,
            contribution_to_total=25.65,
            timestamp=timestamp,
            evaluation_id=456
        )
        
        self.assertEqual(log.sprint_id, 123)
        self.assertEqual(log.sprint_name, "PARSCHAT SPRINT 50")
        self.assertEqual(log.developer_name, "کاظمی")
        self.assertEqual(log.department, "DevOps")
        self.assertEqual(log.project, "PARSCHAT")
        self.assertEqual(log.calculation_type, "score_component")
        self.assertEqual(log.metric_name, "deadline_score")
        self.assertEqual(log.metric_value, 85.5)
        self.assertEqual(log.calculation_formula, "max(0, 100 - per_task_deadline_penalties)")
        self.assertIn("penalty of 14.5", log.calculation_details)
        self.assertEqual(log.weight, 0.3)
        self.assertEqual(log.contribution_to_total, 25.65)
        self.assertEqual(log.timestamp, timestamp)
        self.assertEqual(log.evaluation_id, 456)

    def test_create_calculation_log_with_optional_fields_none(self):
        """Test creating a calculation log with optional fields as None."""
        log = TeamEvaluationCalculationLog(
            sprint_id=123,
            sprint_name="PARSCHAT SPRINT 50",
            developer_name="کاظمی",
            department="DevOps",
            project="PARSCHAT",
            calculation_type="metric",
            metric_name="development_task_count",
            metric_value=5.0,
            calculation_formula="COUNT(issues WHERE type IN development_types)",
            calculation_details="Counted 5 development tasks out of 8 total issues",
            weight=None,
            contribution_to_total=None,
            timestamp=None,
            evaluation_id=None
        )
        
        self.assertEqual(log.sprint_id, 123)
        self.assertEqual(log.metric_value, 5.0)
        self.assertIsNone(log.weight)
        self.assertIsNone(log.contribution_to_total)
        self.assertIsNone(log.timestamp)
        self.assertIsNone(log.evaluation_id)

    def test_create_metric_type_log(self):
        """Test creating a metric type calculation log."""
        log = TeamEvaluationCalculationLog(
            sprint_id=123,
            sprint_name="DASH Sprint 42",
            developer_name="حامد",
            department="AI",
            project="DASH",
            calculation_type="metric",
            metric_name="registered_hours_total",
            metric_value=38.5,
            calculation_formula="SUM(worklogs.hours WHERE worklog.date IN sprint_range)",
            calculation_details="Summed 38.5 hours from 15 worklogs within sprint date range"
        )
        
        self.assertEqual(log.calculation_type, "metric")
        self.assertEqual(log.metric_name, "registered_hours_total")
        self.assertEqual(log.metric_value, 38.5)

    def test_create_final_score_type_log(self):
        """Test creating a final score type calculation log."""
        log = TeamEvaluationCalculationLog(
            sprint_id=228,
            sprint_name="PARS Sprint 24",
            developer_name="اعتماد",
            department="AI",
            project="PARS",
            calculation_type="final_score",
            metric_name="quality_score_total",
            metric_value=75.0,
            calculation_formula="max(-50, round(weighted_sum - penalties + bonuses))",
            calculation_details="Final score: Composite 73.5, penalties: 5.0, bonuses: 6.5 = 75"
        )
        
        self.assertEqual(log.calculation_type, "final_score")
        self.assertEqual(log.metric_name, "quality_score_total")
        self.assertEqual(log.metric_value, 75.0)

    def test_calculation_log_dataclass_immutability(self):
        """Test that calculation log behaves as expected for a dataclass."""
        log = TeamEvaluationCalculationLog(
            sprint_id=123,
            sprint_name="Test Sprint",
            developer_name="Test Dev",
            department="Test Dept",
            project="TEST",
            calculation_type="metric",
            metric_name="test_metric",
            metric_value=100.0,
            calculation_formula="test",
            calculation_details="test details"
        )
        
        # Dataclasses are mutable by default, but we can modify fields
        log.metric_value = 200.0
        self.assertEqual(log.metric_value, 200.0)


if __name__ == "__main__":
    unittest.main()
