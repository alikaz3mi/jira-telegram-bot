from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timedelta
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from jira import Issue

from jira_telegram_bot.entities.deadline_alert import DeadlineAlert
from jira_telegram_bot.use_cases.send_deadline_alerts_use_case import SendDeadlineAlertsUseCase


class TestSendDeadlineAlertsUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for SendDeadlineAlertsUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.task_manager_repository = AsyncMock()
        self.user_config_repository = AsyncMock()
        self.telegram_notifier = AsyncMock()
        self.notification_log_repository = AsyncMock()
        
        self.use_case = SendDeadlineAlertsUseCase(
            task_manager_repository=self.task_manager_repository,
            user_config_repository=self.user_config_repository,
            telegram_notifier=self.telegram_notifier,
            notification_log_repository=self.notification_log_repository,
        )
    
    def _create_mock_issue(
        self,
        key: str,
        summary: str,
        assignee: str = "john.doe",
        due_date: str = None,
        status: str = "In Progress",
        priority: str = "High",
        project_key: str = "TEST",
    ) -> MagicMock:
        """Create a mock Jira issue."""
        issue = MagicMock(spec=Issue)
        issue.key = key
        issue.fields.summary = summary
        issue.fields.status.name = status
        issue.fields.project.key = project_key
        
        # Set up assignee
        if assignee:
            issue.fields.assignee = MagicMock()
            issue.fields.assignee.name = assignee
        else:
            issue.fields.assignee = None
        
        # Set up priority
        if priority:
            issue.fields.priority = MagicMock()
            issue.fields.priority.name = priority
        else:
            issue.fields.priority = None
        
        # Set up due date
        issue.fields.duedate = due_date
        issue.fields.customfield_10110 = None  # Target end field
        
        # Mock issue URL
        issue._options = {"server": "https://test.atlassian.net"}
        
        return issue
    
    def _create_mock_user_config(
        self,
        telegram_username: str,
        jira_username: str,
        chat_id: int,
    ) -> MagicMock:
        """Create a mock user config."""
        config = MagicMock()
        config.telegram_username = telegram_username
        config.jira_username = jira_username
        config.telegram_user_chat_id = chat_id
        return config
    
    async def test_execute_no_issues_found(self):
        """Test execution when no issues are found."""
        # Arrange
        self.task_manager_repository.get_issues_with_approaching_deadlines.return_value = []
        
        # Act
        stats = await self.use_case.execute()
        
        # Assert
        self.assertEqual(stats["issues_processed"], 0)
        self.assertEqual(stats["personal_notifications_sent"], 0)
        self.assertEqual(stats["group_notifications_sent"], 0)
        self.task_manager_repository.get_issues_with_approaching_deadlines.assert_called_once_with(
            lookahead_days=7,
            additional_jql=None,
        )
    
    async def test_execute_with_issues_and_notifications(self):
        """Test execution with issues and successful notifications."""
        # Arrange
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        mock_issue = self._create_mock_issue(
            key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            due_date=tomorrow.strftime("%Y-%m-%d"),
        )
        
        self.task_manager_repository.get_issues_with_approaching_deadlines.return_value = [mock_issue]
        
        mock_user_config = self._create_mock_user_config(
            telegram_username="johndoe",
            jira_username="john.doe",
            chat_id=12345,
        )
        
        self.user_config_repository.get_all_user_configs.return_value = {
            "johndoe": mock_user_config
        }
        self.user_config_repository.get_group_chat_ids.return_value = []
        
        self.notification_log_repository.has_notification_been_sent.return_value = False
        self.telegram_notifier.send_personal_notification.return_value = True
        
        # Act
        stats = await self.use_case.execute()
        
        # Assert
        self.assertEqual(stats["issues_processed"], 1)
        self.assertEqual(stats["personal_notifications_sent"], 1)
        self.assertEqual(stats["group_notifications_sent"], 0)
        self.assertEqual(stats["notifications_skipped"], 0)
        
        self.telegram_notifier.send_personal_notification.assert_called_once()
        self.notification_log_repository.log_notification_sent.assert_called_once()
    
    async def test_execute_skips_already_sent_notifications(self):
        """Test that already sent notifications are skipped."""
        # Arrange
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        mock_issue = self._create_mock_issue(
            key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            due_date=tomorrow.strftime("%Y-%m-%d"),
        )
        
        self.task_manager_repository.get_issues_with_approaching_deadlines.return_value = [mock_issue]
        
        mock_user_config = self._create_mock_user_config(
            telegram_username="johndoe",
            jira_username="john.doe",
            chat_id=12345,
        )
        
        self.user_config_repository.get_all_user_configs.return_value = {
            "johndoe": mock_user_config
        }
        self.user_config_repository.get_group_chat_ids.return_value = []
        
        # Notification already sent
        self.notification_log_repository.has_notification_been_sent.return_value = True
        
        # Act
        stats = await self.use_case.execute()
        
        # Assert
        self.assertEqual(stats["issues_processed"], 1)
        self.assertEqual(stats["personal_notifications_sent"], 0)
        self.assertEqual(stats["notifications_skipped"], 1)
        
        self.telegram_notifier.send_personal_notification.assert_not_called()
        self.notification_log_repository.log_notification_sent.assert_not_called()
    
    async def test_execute_with_group_notifications(self):
        """Test execution with group notifications for urgent issues."""
        # Arrange
        today = datetime.now()
        
        # Create overdue issue (urgent)
        mock_issue = self._create_mock_issue(
            key="TEST-123",
            summary="Urgent issue",
            assignee="john.doe",
            due_date=(today - timedelta(days=1)).strftime("%Y-%m-%d"),  # Overdue
        )
        
        self.task_manager_repository.get_issues_with_approaching_deadlines.return_value = [mock_issue]
        
        mock_user_config = self._create_mock_user_config(
            telegram_username="johndoe",
            jira_username="john.doe",
            chat_id=12345,
        )
        
        self.user_config_repository.get_all_user_configs.return_value = {
            "johndoe": mock_user_config
        }
        self.user_config_repository.get_group_chat_ids.return_value = [-98765]  # Group chat
        
        self.notification_log_repository.has_notification_been_sent.return_value = False
        self.telegram_notifier.send_personal_notification.return_value = True
        self.telegram_notifier.send_group_notification.return_value = True
        
        # Act
        stats = await self.use_case.execute()
        
        # Assert
        self.assertEqual(stats["issues_processed"], 1)
        self.assertEqual(stats["personal_notifications_sent"], 1)
        self.assertEqual(stats["group_notifications_sent"], 1)
        
        self.telegram_notifier.send_group_notification.assert_called_once()
        args, kwargs = self.telegram_notifier.send_group_notification.call_args
        self.assertEqual(args[0], -98765)  # Group chat ID
        self.assertTrue(kwargs.get("mention_users", False))
    
    async def test_create_deadline_alert_with_due_date(self):
        """Test creating deadline alert with due date."""
        # Arrange
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        mock_issue = self._create_mock_issue(
            key="TEST-123",
            summary="Test issue",
            due_date=tomorrow.strftime("%Y-%m-%d"),
        )
        
        # Act
        alert = await self.use_case._create_deadline_alert(mock_issue, today)
        
        # Assert
        self.assertIsNotNone(alert)
        self.assertEqual(alert.issue_key, "TEST-123")
        self.assertEqual(alert.summary, "Test issue")
        self.assertEqual(alert.days_remaining, 1)
        self.assertEqual(alert.urgency_level, "urgent")
        self.assertIsNotNone(alert.due_date)
    
    async def test_create_deadline_alert_with_target_end(self):
        """Test creating deadline alert with target end date."""
        # Arrange
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        mock_issue = self._create_mock_issue(
            key="TEST-123",
            summary="Test issue",
        )
        # Set target end instead of due date
        mock_issue.fields.duedate = None
        mock_issue.fields.customfield_10110 = tomorrow.strftime("%Y-%m-%d")
        
        # Act
        alert = await self.use_case._create_deadline_alert(mock_issue, today)
        
        # Assert
        self.assertIsNotNone(alert)
        self.assertEqual(alert.issue_key, "TEST-123")
        self.assertEqual(alert.days_remaining, 1)
        self.assertIsNone(alert.due_date)
        self.assertIsNotNone(alert.target_end)
    
    async def test_create_deadline_alert_no_deadline(self):
        """Test creating deadline alert when no deadline is set."""
        # Arrange
        today = datetime.now()
        
        mock_issue = self._create_mock_issue(
            key="TEST-123",
            summary="Test issue",
        )
        # No due date or target end
        mock_issue.fields.duedate = None
        mock_issue.fields.customfield_10110 = None
        
        # Act
        alert = await self.use_case._create_deadline_alert(mock_issue, today)
        
        # Assert
        self.assertIsNone(alert)
    
    async def test_parse_date_field_iso_format(self):
        """Test parsing ISO format date."""
        # Arrange
        date_str = "2025-06-05T14:30:00.000Z"
        
        # Act
        result = self.use_case._parse_date_field(date_str)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 5)
    
    async def test_parse_date_field_date_only(self):
        """Test parsing date-only format."""
        # Arrange
        date_str = "2025-06-05"
        
        # Act
        result = self.use_case._parse_date_field(date_str)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 5)
    
    async def test_parse_date_field_invalid(self):
        """Test parsing invalid date format."""
        # Arrange
        date_str = "invalid-date"
        
        # Act
        result = self.use_case._parse_date_field(date_str)
        
        # Assert
        self.assertIsNone(result)
    
    async def test_parse_date_field_none(self):
        """Test parsing None date."""
        # Act
        result = self.use_case._parse_date_field(None)
        
        # Assert
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
