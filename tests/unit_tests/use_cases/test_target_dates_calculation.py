"""Tests for target_start and target_end calculation based on story points and deadline."""
import datetime
import unittest
from unittest.mock import MagicMock

from jira_telegram_bot.use_cases.telegram_commands.create_task import (
    JiraTaskCreation,
)


class TestTargetDatesCalculation(unittest.TestCase):
    """Test target_start calculation based on story points and deadline."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repo = MagicMock()
        self.mock_user_config = MagicMock()
        self.task_creation = JiraTaskCreation(
            jira_repository=self.mock_jira_repo,
            user_config=self.mock_user_config,
        )

    def test_calculate_target_start_basic(self):
        """Test basic target_start calculation."""
        story_points = 1.0
        target_end = datetime.date(2025, 12, 13)
        
        target_start = self.task_creation._calculate_target_start(
            story_points,
            target_end,
        )
        
        expected_start = datetime.date(2025, 12, 12)
        self.assertEqual(target_start, expected_start)

    def test_calculate_target_start_multiple_days(self):
        """Test target_start calculation with multiple working days."""
        story_points = 5.0
        target_end = datetime.date(2025, 12, 13)
        
        target_start = self.task_creation._calculate_target_start(
            story_points,
            target_end,
        )
        
        expected_start = datetime.date(2025, 12, 8)
        self.assertEqual(target_start, expected_start)

    def test_calculate_target_start_skip_weekends(self):
        """Test that weekends are skipped in calculation."""
        story_points = 3.0
        target_end = datetime.date(2025, 12, 15)
        
        target_start = self.task_creation._calculate_target_start(
            story_points,
            target_end,
        )
        
        expected_start = datetime.date(2025, 12, 10)
        self.assertEqual(target_start, expected_start)

    def test_calculate_target_start_fractional_story_points(self):
        """Test target_start calculation with fractional story points."""
        story_points = 0.5
        target_end = datetime.date(2025, 12, 13)
        
        target_start = self.task_creation._calculate_target_start(
            story_points,
            target_end,
        )
        
        expected_start = datetime.date(2025, 12, 13)
        self.assertEqual(target_start, expected_start)

    def test_calculate_target_start_large_story_points(self):
        """Test target_start calculation with large story points (crosses multiple weeks)."""
        story_points = 13.0
        target_end = datetime.date(2025, 12, 26)
        
        target_start = self.task_creation._calculate_target_start(
            story_points,
            target_end,
        )
        
        expected_start = datetime.date(2025, 12, 9)
        self.assertEqual(target_start, expected_start)

    def test_hours_per_story_point_constant(self):
        """Test that HOURS_PER_STORY_POINT is correctly set."""
        self.assertEqual(self.task_creation.HOURS_PER_STORY_POINT, 8)

    def test_hours_per_working_day_constant(self):
        """Test that HOURS_PER_WORKING_DAY is correctly set."""
        self.assertEqual(self.task_creation.HOURS_PER_WORKING_DAY, 8)


if __name__ == "__main__":
    unittest.main()
