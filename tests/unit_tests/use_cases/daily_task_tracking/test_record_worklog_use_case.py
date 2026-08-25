"""Unit tests for RecordWorklogUseCase."""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.use_cases.daily_task_tracking.record_worklog_use_case import (
    RecordWorklogUseCase,
)


class TestRecordWorklogUseCase(unittest.TestCase):
    """Test cases for RecordWorklogUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_task_manager = Mock()
        self.mock_tracking_repo = Mock()
        self.mock_tracking_repo.save_progress_report = AsyncMock()
        
        self.use_case = RecordWorklogUseCase(
            task_manager_repository=self.mock_task_manager,
            tracking_repository=self.mock_tracking_repo,
        )

    async def test_execute_adds_worklog_to_jira(self):
        """Test that execute adds worklog to Jira."""
        mock_worklog = Mock()
        self.mock_task_manager.jira.add_worklog.return_value = mock_worklog
        
        report = await self.use_case.execute(
            issue_key="TEST-123",
            jira_username="testuser",
            telegram_username="tg_testuser",
            hours=4.0,
        )
        
        self.assertEqual(report.issue_key, "TEST-123")
        self.assertEqual(report.hours_spent, 4.0)
        self.assertTrue(report.worklog_added)
        
        self.mock_task_manager.jira.add_worklog.assert_called_once()
        call_args = self.mock_task_manager.jira.add_worklog.call_args
        self.assertEqual(call_args[1]["issue"], "TEST-123")
        self.assertEqual(call_args[1]["timeSpent"], "4h")

    async def test_execute_handles_jira_failure(self):
        """Test that execute handles Jira worklog failure gracefully."""
        self.mock_task_manager.jira.add_worklog.side_effect = Exception(
            "Jira error"
        )
        
        report = await self.use_case.execute(
            issue_key="TEST-123",
            jira_username="testuser",
            telegram_username="tg_testuser",
            hours=4.0,
        )
        
        self.assertFalse(report.worklog_added)
        self.mock_tracking_repo.save_progress_report.assert_called_once()

    async def test_execute_formats_time_correctly(self):
        """Test that execute formats time with hours and minutes."""
        self.mock_task_manager.jira.add_worklog.return_value = Mock()
        
        await self.use_case.execute(
            issue_key="TEST-123",
            jira_username="testuser",
            telegram_username="tg_testuser",
            hours=2.5,
        )
        
        call_args = self.mock_task_manager.jira.add_worklog.call_args
        self.assertEqual(call_args[1]["timeSpent"], "2h 30m")


if __name__ == "__main__":
    unittest.main()
