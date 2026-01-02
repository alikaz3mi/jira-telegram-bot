"""Unit tests for RecordDelayReasonUseCase."""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    DelayReason,
)
from jira_telegram_bot.use_cases.daily_task_tracking.record_delay_reason_use_case import (
    RecordDelayReasonUseCase,
)


class TestRecordDelayReasonUseCase(unittest.TestCase):
    """Test cases for RecordDelayReasonUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_tracking_repo = Mock()
        self.mock_tracking_repo.save_progress_report = AsyncMock()
        
        self.use_case = RecordDelayReasonUseCase(
            tracking_repository=self.mock_tracking_repo,
        )

    async def test_execute_saves_delay_reason(self):
        """Test that execute saves delay reason correctly."""
        report = await self.use_case.execute(
            issue_key="TEST-123",
            jira_username="testuser",
            telegram_username="tg_testuser",
            delay_reason=DelayReason.TECHNICAL_BLOCKER,
        )
        
        self.assertEqual(report.issue_key, "TEST-123")
        self.assertEqual(report.user_jira_username, "testuser")
        self.assertEqual(report.delay_reason, DelayReason.TECHNICAL_BLOCKER)
        
        self.mock_tracking_repo.save_progress_report.assert_called_once()

    async def test_execute_saves_custom_delay_reason(self):
        """Test that execute saves custom delay reason text."""
        report = await self.use_case.execute(
            issue_key="TEST-123",
            jira_username="testuser",
            telegram_username="tg_testuser",
            delay_reason=DelayReason.OTHER,
            delay_reason_text="Custom reason",
        )
        
        self.assertEqual(report.delay_reason, DelayReason.OTHER)
        self.assertEqual(report.delay_reason_text, "Custom reason")


if __name__ == "__main__":
    unittest.main()
