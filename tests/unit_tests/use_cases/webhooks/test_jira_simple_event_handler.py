from __future__ import annotations

import unittest
from unittest.mock import Mock

from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.webhooks.jira_simple_event_handler import JiraSimpleEventHandler
from jira_telegram_bot.use_cases.webhooks.jira_webhook_message_formatter import (
    JiraWebhookMessageFormatter,
)


class TestJiraSimpleEventHandler(unittest.TestCase):
    """Test cases for simple Jira event handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_telegram_gateway = Mock(spec=NotificationGatewayInterface)
        self.mock_message_formatter = Mock(spec=JiraWebhookMessageFormatter)
        
        self.event_handler = JiraSimpleEventHandler(
            self.mock_telegram_gateway, self.mock_message_formatter
        )

    def test_handle_issue_created_success(self):
        """Test successful handling of issue creation event."""
        # Arrange
        issue_data = {
            "key": "TEST-123",
            "fields": {"summary": "Test issue"}
        }
        webhook_body = {"user": {"displayName": "John Doe"}}
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        
        self.mock_message_formatter.format_issue_created_message.return_value = "Test message"
        
        # Act
        result = self.event_handler.handle_issue_created(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        
        # Assert
        self.assertEqual(result["status"], "success")
        self.assertIn("Issue created", result["message"])
        self.assertIn("TEST-123", result["message"])
        
        self.mock_message_formatter.format_issue_created_message.assert_called_once_with(
            issue_data, webhook_body
        )
        
        # Check that notifications were sent
        self.mock_telegram_gateway.send_message.assert_any_call(
            channel_chat_id, "Test message", reply_message_id
        )
        self.mock_telegram_gateway.send_message.assert_any_call(
            group_chat_id, "Test message"
        )

    def test_handle_issue_created_same_channel_and_group(self):
        """Test handling when channel and group chat IDs are the same."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {"user": {"displayName": "John Doe"}}
        chat_id = "same-chat-123"
        
        self.mock_message_formatter.format_issue_created_message.return_value = "Test message"
        
        # Act
        result = self.event_handler.handle_issue_created(
            issue_data, webhook_body, chat_id, chat_id, "reply-789"
        )
        
        # Assert
        self.assertEqual(result["status"], "success")
        
        # Should only send one message since chat IDs are the same
        self.assertEqual(self.mock_telegram_gateway.send_message.call_count, 1)
        self.mock_telegram_gateway.send_message.assert_called_with(
            chat_id, "Test message", "reply-789"
        )

    def test_handle_issue_created_no_group_chat(self):
        """Test handling when group chat ID is None."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {"summary": "Test issue"}}
        webhook_body = {"user": {"displayName": "John Doe"}}
        channel_chat_id = "channel-123"
        
        self.mock_message_formatter.format_issue_created_message.return_value = "Test message"
        
        # Act
        result = self.event_handler.handle_issue_created(
            issue_data, webhook_body, channel_chat_id, None, "reply-789"
        )
        
        # Assert
        self.assertEqual(result["status"], "success")
        
        # Should only send one message to channel
        self.assertEqual(self.mock_telegram_gateway.send_message.call_count, 1)
        self.mock_telegram_gateway.send_message.assert_called_with(
            channel_chat_id, "Test message", "reply-789"
        )

    def test_handle_issue_generic_success(self):
        """Test successful handling of generic issue event."""
        # Arrange
        issue_data = {
            "key": "TEST-456",
            "fields": {"summary": "Generic test issue"}
        }
        webhook_body = {"user": {"displayName": "Jane Smith"}}
        channel_chat_id = "channel-123"
        group_chat_id = "group-456"
        reply_message_id = "reply-789"
        
        self.mock_message_formatter.format_issue_generic_message.return_value = "Generic message"
        
        # Act
        result = self.event_handler.handle_issue_generic(
            issue_data, webhook_body, channel_chat_id, group_chat_id, reply_message_id
        )
        
        # Assert
        self.assertEqual(result["status"], "success")
        self.assertIn("Issue created", result["message"])
        self.assertIn("TEST-456", result["message"])
        
        self.mock_message_formatter.format_issue_generic_message.assert_called_once_with(
            issue_data, webhook_body
        )
        
        # Check that notifications were sent
        self.mock_telegram_gateway.send_message.assert_any_call(
            channel_chat_id, "Generic message", reply_message_id
        )
        self.mock_telegram_gateway.send_message.assert_any_call(
            group_chat_id, "Generic message"
        )

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

    def test_send_notifications_channel_only(self):
        """Test sending notifications to channel only."""
        # Arrange
        channel_chat_id = "channel-123"
        reply_message_id = "reply-789"
        message_text = "Test notification"
        
        # Act
        self.event_handler._send_notifications(
            channel_chat_id, None, reply_message_id, message_text
        )
        
        # Assert
        self.mock_telegram_gateway.send_message.assert_called_once_with(
            channel_chat_id, message_text, reply_message_id
        )

    def test_send_notifications_no_channels(self):
        """Test sending notifications when no chat IDs are provided."""
        # Arrange
        message_text = "Test notification"
        
        # Act
        self.event_handler._send_notifications(
            None, None, "reply-789", message_text
        )
        
        # Assert
        self.mock_telegram_gateway.send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
