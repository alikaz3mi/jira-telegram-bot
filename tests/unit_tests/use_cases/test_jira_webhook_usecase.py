from __future__ import annotations

import unittest
from unittest.mock import Mock, patch, MagicMock

from jira_telegram_bot.entities.jira_status_constants import JiraStatusConstants
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.use_cases.handle_jira_webhook_usecase import HandleJiraWebhookUseCase
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class TestJiraWebhookUseCase(unittest.TestCase):
    """Test cases for Jira webhook functionality."""

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

    @patch('jira_telegram_bot.use_cases.handle_jira_webhook_usecase.get_mapping_by_issue_key')
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

    @patch('jira_telegram_bot.use_cases.handle_jira_webhook_usecase.get_mapping_by_issue_key')
    def test_status_change_review_to_done_by_admin_allowed(self, mock_get_mapping):
        """Test that Jira admin can move task from review to done."""
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
            "user": {"name": "admin.user", "displayName": "Admin User"},
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
        
        self.mock_jira_repository.is_user_jira_admin.return_value = True
        self.mock_jira_repository.update_time_estimate = Mock()
        
        # Act
        result = self.use_case.run(webhook_body)
        
        # Assert
        self.assertEqual(result["status"], "success")
        self.mock_jira_repository.update_time_estimate.assert_called_once_with("TEST-123", "0h")
        self.mock_telegram_gateway.send_message.assert_called()

    @patch('jira_telegram_bot.use_cases.handle_jira_webhook_usecase.get_mapping_by_issue_key')
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

    @patch('jira_telegram_bot.use_cases.handle_jira_webhook_usecase.get_mapping_by_issue_key')
    def test_status_change_other_transitions_allowed(self, mock_get_mapping):
        """Test that other status transitions are allowed for any user."""
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
            "user": {"name": "any.user", "displayName": "Any User"},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "To Do",
                        "toString": "In Progress",
                    }
                ]
            },
        }
        
        # Act
        result = self.use_case.run(webhook_body)
        
        # Assert
        self.assertEqual(result["status"], "success")
        self.mock_jira_repository.transition_task.assert_not_called()
        self.mock_jira_repository.add_comment.assert_not_called()
        self.mock_telegram_gateway.send_message.assert_called()

    def test_check_transition_permission_review_to_done_by_reporter(self):
        """Test permission check for reporter moving from review to done."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "john.doe"}}
        
        # Act
        result = self.use_case._check_transition_permission(
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
        result = self.use_case._check_transition_permission(
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
        result = self.use_case._check_transition_permission(
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
        result = self.use_case._check_transition_permission(
            issue_data, webhook_body, "To Do", "In Progress"
        )
        
        # Assert
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
