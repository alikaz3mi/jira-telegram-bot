from __future__ import annotations

import unittest
from unittest.mock import Mock

from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.use_cases.webhooks.jira_webhook_message_formatter import (
    JiraWebhookMessageFormatter,
)


class TestJiraWebhookMessageFormatter(unittest.TestCase):
    """Test cases for Jira webhook message formatting."""

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
        """Test formatting of issue creation messages."""
        # Arrange
        issue_data = {
            "key": "TEST-123",
            "fields": {"summary": "Test issue for creation"}
        }
        webhook_body = {"user": {"displayName": "John Doe"}}
        
        # Act
        result = self.formatter.format_issue_created_message(issue_data, webhook_body)
        
        # Assert
        self.assertIn("**Jira Event**", result)
        self.assertIn("Issue *created* by John Doe", result)
        self.assertIn("Key: TEST-123", result)
        self.assertIn("Summary: Test issue for creation", result)

    def test_format_issue_created_message_missing_summary(self):
        """Test formatting when summary is missing."""
        # Arrange
        issue_data = {"key": "TEST-123", "fields": {}}
        webhook_body = {"user": {"displayName": "John Doe"}}
        
        # Act
        result = self.formatter.format_issue_created_message(issue_data, webhook_body)
        
        # Assert
        self.assertIn("Summary: ", result)  # Should have empty summary

    def test_format_issue_created_message_missing_user(self):
        """Test formatting when user display name is missing."""
        # Arrange
        issue_data = {
            "key": "TEST-123",
            "fields": {"summary": "Test issue"}
        }
        webhook_body = {"user": {}}
        
        # Act
        result = self.formatter.format_issue_created_message(issue_data, webhook_body)
        
        # Assert
        self.assertIn("Issue *created* by someone", result)

    def test_format_issue_generic_message(self):
        """Test formatting of generic issue messages."""
        # Arrange
        issue_data = {
            "key": "TEST-123",
            "fields": {"summary": "Test generic issue"}
        }
        webhook_body = {"user": {"displayName": "Jane Smith"}}
        
        # Act
        result = self.formatter.format_issue_generic_message(issue_data, webhook_body)
        
        # Assert
        self.assertIn("🔔 *Jira Event*", result)
        self.assertIn("🔑 Issue Key: https://example.atlassian.net/browse/TEST-123", result)
        self.assertIn("📝 Summary: Test generic issue", result)
        self.assertIn("👤 Created by Jane Smith", result)

    def test_format_comment_message(self):
        """Test formatting of comment messages."""
        # Arrange
        issue_data = {"key": "TEST-123"}
        comment_info = {
            "updateAuthor": {"displayName": "Alice Johnson"},
            "body": "This is a test comment with some details."
        }
        
        # Act
        result = self.formatter.format_comment_message(issue_data, comment_info)
        
        # Assert
        self.assertIn("**Jira Event**", result)
        self.assertIn("New comment on *TEST-123* by Alice Johnson:", result)
        self.assertIn("This is a test comment with some details.", result)

    def test_format_status_change_message(self):
        """Test formatting of status change messages."""
        # Arrange
        issue_key = "TEST-123"
        from_status = "In Progress"
        to_status = "Review"
        
        # Act
        result = self.formatter.format_status_change_message(
            issue_key, from_status, to_status
        )
        
        # Assert
        self.assertIn("**Jira Event**", result)
        self.assertIn("Issue *TEST-123* moved from 'In Progress' to 'Review'.", result)

    def test_format_status_reversion_message(self):
        """Test formatting of status reversion messages."""
        # Arrange
        issue_key = "TEST-123"
        from_status = "Done"
        to_status = "Review"
        
        # Act
        result = self.formatter.format_status_reversion_message(
            issue_key, from_status, to_status
        )
        
        # Assert
        self.assertIn("**Jira Event - Action Reverted**", result)
        self.assertIn("Issue *TEST-123* was reverted from 'Done' back to 'Review'.", result)
        self.assertIn("Only the reporter or Jira administrators", result)
        self.assertIn("Review to Done", result)

    def test_build_issue_url(self):
        """Test building of issue URLs."""
        # Arrange
        issue_key = "TEST-123"
        
        # Act
        result = self.formatter._build_issue_url(issue_key)
        
        # Assert
        expected_url = "https://example.atlassian.net/browse/TEST-123"
        self.assertEqual(result, expected_url)

    def test_build_issue_url_different_domain(self):
        """Test building URLs with different domain settings."""
        # Arrange
        mock_domain = Mock()
        mock_domain.scheme = "http"
        mock_domain.host = "company.atlassian.net"
        self.mock_jira_settings.domain = mock_domain
        
        formatter = JiraWebhookMessageFormatter(self.mock_jira_settings)
        issue_key = "PROJ-456"
        
        # Act
        result = formatter._build_issue_url(issue_key)
        
        # Assert
        expected_url = "http://company.atlassian.net/browse/PROJ-456"
        self.assertEqual(result, expected_url)


if __name__ == "__main__":
    unittest.main()
