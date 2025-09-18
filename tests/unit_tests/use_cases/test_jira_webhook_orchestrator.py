from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from jira_telegram_bot.entities.jira_status_constants import JiraStatusConstants
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import HandleJiraWebhookUseCase
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.webhooks.jira_issue_status_manager import JiraIssueStatusManager
from jira_telegram_bot.use_cases.webhooks.jira_transition_permission_validator import (
    JiraTransitionPermissionValidator,
)
from jira_telegram_bot.use_cases.webhooks.jira_webhook_message_formatter import (
    JiraWebhookMessageFormatter,
)


class TestJiraWebhookOrchestrator(unittest.TestCase):
    """Test cases for modular Jira webhook orchestrator."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_settings = Mock(spec=JiraConnectionSettings)

        # Create a mock domain object with the required attributes
        mock_domain = Mock()
        mock_domain.scheme = "https"
        mock_domain.host = "example.atlassian.net"
        self.mock_jira_settings.domain = mock_domain

        self.mock_telegram_gateway = Mock(spec=NotificationGatewayInterface)
        self.mock_jira_repository = Mock(spec=TaskManagerRepositoryInterface)

        self.use_case = HandleJiraWebhookUseCase(
            jira_settings=self.mock_jira_settings,
            telegram_gateway=self.mock_telegram_gateway,
            jira_repository=self.mock_jira_repository,
        )

    @patch('jira_telegram_bot.use_cases.handle_jira_webhook_usecase_refactored.get_mapping_by_issue_key')
    def test_status_change_review_to_done_by_reporter_allowed(self, mock_get_mapping):
        """Test that reporter can move task from review to done."""
        # Arrange
        mock_get_mapping.return_value = {
            "channel_chat_id": "123",
            "group_chat_id": "456",
            "reply_message_id": "789",
        }

        webhook_body = {
            "issue_event_type_name": "issue_updated",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "summary": "Test issue",
                    "reporter": {"name": "john.doe"},
                },
            },
            "user": {"name": "john.doe", "displayName": "John Doe"},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "Review",
                        "toString": "Done",
                    }
                ]
            },
        }

        self.mock_jira_repository.is_user_jira_admin.return_value = False
        self.mock_jira_repository.update_time_estimate = Mock()

        # Act
        result = self.use_case.run(webhook_body)

        # Assert
        self.assertEqual(result["status"], "success")
        self.mock_jira_repository.update_time_estimate.assert_called_once_with("TEST-123", "0h")
        self.mock_telegram_gateway.send_message.assert_called()

    @patch('jira_telegram_bot.use_cases.handle_jira_webhook_usecase_refactored.get_mapping_by_issue_key')
    def test_status_change_review_to_done_by_unauthorized_user_reverted(self, mock_get_mapping):
        """Test that unauthorized user cannot move task from review to done."""
        # Arrange
        mock_get_mapping.return_value = {
            "channel_chat_id": "123",
            "group_chat_id": "456",
            "reply_message_id": "789",
        }

        webhook_body = {
            "issue_event_type_name": "issue_updated",
            "issue": {
                "key": "TEST-123",
                "fields": {
                    "summary": "Test issue",
                    "reporter": {"name": "john.doe"},
                },
            },
            "user": {"name": "unauthorized.user", "displayName": "Unauthorized User"},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "Review",
                        "toString": "Done",
                    }
                ]
            },
        }

        self.mock_jira_repository.is_user_jira_admin.return_value = False
        self.mock_jira_repository.transition_task = Mock()
        self.mock_jira_repository.add_comment = Mock()

        # Act
        result = self.use_case.run(webhook_body)

        # Assert
        self.assertEqual(result["status"], "reverted")
        self.mock_jira_repository.transition_task.assert_called_once_with("TEST-123", "Review")
        self.mock_jira_repository.add_comment.assert_called_once()
        self.mock_telegram_gateway.send_message.assert_called()


class TestJiraTransitionPermissionValidator(unittest.TestCase):
    """Test cases for permission validator."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repository = Mock(spec=TaskManagerRepositoryInterface)
        self.validator = JiraTransitionPermissionValidator(self.mock_jira_repository)

    def test_check_transition_permission_review_to_done_by_reporter(self):
        """Test permission check for reporter moving from review to done."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "john.doe"}}

        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "Review", "Done"
        )

        # Assert
        self.assertTrue(result)

    def test_check_transition_permission_review_to_done_by_admin(self):
        """Test permission check for admin moving from review to done."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "admin.user"}}
        self.mock_jira_repository.is_user_jira_admin.return_value = True

        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "Review", "Done"
        )

        # Assert
        self.assertTrue(result)
        self.mock_jira_repository.is_user_jira_admin.assert_called_once_with("admin.user")

    def test_check_transition_permission_review_to_done_by_unauthorized(self):
        """Test permission check for unauthorized user moving from review to done."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "unauthorized.user"}}
        self.mock_jira_repository.is_user_jira_admin.return_value = False

        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "Review", "Done"
        )

        # Assert
        self.assertFalse(result)
        self.mock_jira_repository.is_user_jira_admin.assert_called_once_with("unauthorized.user")

    def test_check_transition_permission_other_transitions(self):
        """Test permission check for other transitions always returns True."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "any.user"}}

        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "To Do", "In Progress"
        )

        # Assert
        self.assertTrue(result)


class TestJiraIssueStatusManager(unittest.TestCase):
    """Test cases for status manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repository = Mock(spec=TaskManagerRepositoryInterface)
        self.status_manager = JiraIssueStatusManager(self.mock_jira_repository)

    def test_should_update_time_estimate_for_done_status(self):
        """Test that time estimate should be updated when moving to Done."""
        # Act
        result = self.status_manager.should_update_time_estimate("Done")

        # Assert
        self.assertTrue(result)

    def test_should_not_update_time_estimate_for_other_status(self):
        """Test that time estimate should not be updated for other statuses."""
        # Act
        result = self.status_manager.should_update_time_estimate("In Progress")

        # Assert
        self.assertFalse(result)

    def test_update_time_estimate_to_zero(self):
        """Test updating time estimate to zero."""
        # Act
        self.status_manager.update_time_estimate_to_zero("TEST-123")

        # Assert
        self.mock_jira_repository.update_time_estimate.assert_called_once_with("TEST-123", "0h")

    def test_revert_status_and_comment(self):
        """Test reverting status and adding comment."""
        # Act
        self.status_manager.revert_status_and_comment("TEST-123", "Review", "John Doe")

        # Assert
        self.mock_jira_repository.transition_task.assert_called_once_with("TEST-123", "Review")
        self.mock_jira_repository.add_comment.assert_called_once()


class TestJiraWebhookMessageFormatter(unittest.TestCase):
    """Test cases for message formatter."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_settings = Mock(spec=JiraConnectionSettings)

        # Create a mock domain object with the required attributes
        mock_domain = Mock()
        mock_domain.scheme = "https"
        mock_domain.host = "example.atlassian.net"
        self.mock_jira_settings.domain = mock_domain

        self.formatter = JiraWebhookMessageFormatter(self.mock_jira_settings)

    def test_format_issue_created_message(self):
        """Test formatting issue created message."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {"user": {"displayName": "John Doe"}}

        # Act
        result = self.formatter.format_issue_created_message(issue_data, webhook_body)

        # Assert
        self.assertIn("TEST-123", result)
        self.assertIn("John Doe", result)
        self.assertIn("Test issue", result)

    def test_format_status_change_message(self):
        """Test formatting status change message."""
        # Act
        result = self.formatter.format_status_change_message("TEST-123", "To Do", "In Progress")

        # Assert
        self.assertIn("TEST-123", result)
        self.assertIn("To Do", result)
        self.assertIn("In Progress", result)

    def test_format_status_reversion_message(self):
        """Test formatting status reversion message."""
        # Act
        result = self.formatter.format_status_reversion_message("TEST-123", "Done", "Review")

        # Assert
        self.assertIn("TEST-123", result)
        self.assertIn("reverted", result)
        self.assertIn("Done", result)
        self.assertIn("Review", result)


if __name__ == "__main__":
    unittest.main()
