from __future__ import annotations

import unittest
from unittest.mock import Mock

from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.webhooks.jira_issue_status_manager import JiraIssueStatusManager
from jira_telegram_bot.use_cases.webhooks.jira_issue_updated_event_handler import (
    JiraIssueUpdatedEventHandler,
)
from jira_telegram_bot.use_cases.webhooks.jira_transition_permission_validator import (
    JiraTransitionPermissionValidator,
)
from jira_telegram_bot.use_cases.webhooks.jira_webhook_message_formatter import (
    JiraWebhookMessageFormatter,
)


class TestJiraIssueUpdatedEventHandler(unittest.TestCase):
    """Test cases for Jira issue updated event handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_telegram_gateway = Mock(spec=NotificationGatewayInterface)
        self.mock_status_manager = Mock(spec=JiraIssueStatusManager)
        self.mock_permission_validator = Mock(spec=JiraTransitionPermissionValidator)
        self.mock_message_formatter = Mock(spec=JiraWebhookMessageFormatter)
        
        self.event_handler = JiraIssueUpdatedEventHandler(
            self.mock_telegram_gateway,
            self.mock_status_manager,
            self.mock_permission_validator,
            self.mock_message_formatter,
        )

    def test_handle_comment_event(self):
        """Test handling of comment events."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {
            "comment": {
                "updateAuthor": {"displayName": "John Doe"},
                "body": "This is a test comment",
            }
        }
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        
        self.mock_message_formatter.format_comment_message.return_value = "Comment message"
        
        # Act
        result = self.event_handler.handle(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        
        # Assert
        self.assertEqual(result["status"], "success")
        self.assertIn("Comment", result["message"])
        self.assertIn("TEST-123", result["message"])
        
        self.mock_message_formatter.format_comment_message.assert_called_once_with(
            issue_data, webhook_body["comment"]
        )
        
        # Check that notifications were sent
        self.mock_telegram_gateway.send_message.assert_any_call(
            channel_chat_id, "Comment message", reply_message_id
        )
        self.mock_telegram_gateway.send_message.assert_any_call(
            group_chat_id, "Comment message"
        )

    def test_handle_status_change_authorized(self):
        """Test handling of authorized status change."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "In Progress",
                        "toString": "Review",
                    }
                ]
            }
        }
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        
        self.mock_permission_validator.check_transition_permission.return_value = True
        self.mock_status_manager.should_update_time_estimate.return_value = False
        self.mock_message_formatter.format_status_change_message.return_value = "Status change message"
        
        # Act
        result = self.event_handler.handle(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        
        # Assert
        self.assertEqual(result["status"], "success")
        self.assertIn("Status changed", result["message"])
        self.assertIn("TEST-123", result["message"])
        
        self.mock_permission_validator.check_transition_permission.assert_called_once_with(
            issue_data, webhook_body, "In Progress", "Review"
        )
        self.mock_message_formatter.format_status_change_message.assert_called_once_with(
            "TEST-123", "In Progress", "Review"
        )

    def test_handle_status_change_unauthorized_reverted(self):
        """Test handling of unauthorized status change that gets reverted."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {
            "user": {"displayName": "Unauthorized User"},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "Review",
                        "toString": "Done",
                    }
                ]
            }
        }
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        
        self.mock_permission_validator.check_transition_permission.return_value = False
        self.mock_message_formatter.format_status_reversion_message.return_value = "Reversion message"
        
        # Act
        result = self.event_handler.handle(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        
        # Assert
        self.assertEqual(result["status"], "reverted")
        self.assertIn("reverted", result["message"])
        self.assertIn("TEST-123", result["message"])
        
        self.mock_permission_validator.check_transition_permission.assert_called_once_with(
            issue_data, webhook_body, "Review", "Done"
        )
        self.mock_status_manager.revert_status_and_comment.assert_called_once_with(
            "TEST-123", "Review", "Unauthorized User"
        )
        self.mock_message_formatter.format_status_reversion_message.assert_called_once_with(
            "TEST-123", "Done", "Review"
        )

    def test_handle_status_change_to_done_updates_time_estimate(self):
        """Test that transitioning to Done updates time estimate."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "Review",
                        "toString": "Done",
                    }
                ]
            }
        }
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        
        self.mock_permission_validator.check_transition_permission.return_value = True
        self.mock_status_manager.should_update_time_estimate.return_value = True
        self.mock_message_formatter.format_status_change_message.return_value = "Status change message"
        
        # Act
        result = self.event_handler.handle(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        
        # Assert
        self.assertEqual(result["status"], "success")
        
        self.mock_status_manager.should_update_time_estimate.assert_called_once_with("Done")
        self.mock_status_manager.update_time_estimate_to_zero.assert_called_once_with("TEST-123")

    def test_handle_no_relevant_changes(self):
        """Test handling when there are no relevant changes."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {
            "changelog": {
                "items": [
                    {
                        "field": "priority",  # Not a status change
                        "fromString": "Medium",
                        "toString": "High",
                    }
                ]
            }
        }
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        
        # Act
        result = self.event_handler.handle(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        
        # Assert
        self.assertEqual(result["status"], "ignored")
        self.assertIn("no relevant event", result["message"])

    def test_handle_empty_changelog(self):
        """Test handling when changelog is empty."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {"changelog": {"items": []}}
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        
        # Act
        result = self.event_handler.handle(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        
        # Assert
        self.assertEqual(result["status"], "ignored")
        self.assertIn("no relevant event", result["message"])

    def test_send_notifications_both_chats(self):
        """Test sending notifications to both channel and group."""
        # Arrange
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        message_text = "Test notification"
        
        # Act
        self.event_handler._send_notifications(
            channel_chat_id, group_chat_id, reply_message_id, message_text
        )
        
        # Assert
        self.mock_telegram_gateway.send_message.assert_any_call(
            channel_chat_id, message_text, reply_message_id
        )
        self.mock_telegram_gateway.send_message.assert_any_call(
            group_chat_id, message_text
        )
        self.assertEqual(self.mock_telegram_gateway.send_message.call_count, 2)


if __name__ == "__main__":
    unittest.main()
