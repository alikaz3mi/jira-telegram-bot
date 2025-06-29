from __future__ import annotations

import unittest
from unittest.mock import Mock

from jira_telegram_bot.entities.jira_status_constants import JiraStatusConstants
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.webhooks.jira_transition_permission_validator import (
    JiraTransitionPermissionValidator,
)


class TestJiraTransitionPermissionValidator(unittest.TestCase):
    """Test cases for Jira transition permission validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repository = Mock(spec=TaskManagerRepositoryInterface)
        self.validator = JiraTransitionPermissionValidator(self.mock_jira_repository)

    def test_check_transition_permission_review_to_done_by_reporter_allowed(self):
        """Test that reporter can move task from Review to Done."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "john.doe"}}
        
        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "Review", "Done"
        )
        
        # Assert
        self.assertTrue(result)

    def test_check_transition_permission_review_to_done_by_admin_allowed(self):
        """Test that Jira admin can move task from Review to Done."""
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

    def test_check_transition_permission_review_to_done_by_unauthorized_denied(self):
        """Test that unauthorized user cannot move task from Review to Done."""
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

    def test_check_transition_permission_other_transitions_always_allowed(self):
        """Test that other status transitions are always allowed."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "any.user"}}
        
        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "To Do", "In Progress"
        )
        
        # Assert
        self.assertTrue(result)
        self.mock_jira_repository.is_user_jira_admin.assert_not_called()

    def test_check_transition_permission_from_review_to_other_status_allowed(self):
        """Test that transitions from Review to statuses other than Done are allowed."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "any.user"}}
        
        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "Review", "In Progress"
        )
        
        # Assert
        self.assertTrue(result)
        self.mock_jira_repository.is_user_jira_admin.assert_not_called()

    def test_check_transition_permission_to_done_from_other_status_allowed(self):
        """Test that transitions to Done from statuses other than Review are allowed."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {"name": "any.user"}}
        
        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "In Progress", "Done"
        )
        
        # Assert
        self.assertTrue(result)
        self.mock_jira_repository.is_user_jira_admin.assert_not_called()

    def test_check_transition_permission_missing_user_name_denied(self):
        """Test that missing user name results in denial."""
        # Arrange
        issue_data = {"fields": {"reporter": {"name": "john.doe"}}}
        webhook_body = {"user": {}}  # No name field
        
        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "Review", "Done"
        )
        
        # Assert
        self.assertFalse(result)
        self.mock_jira_repository.is_user_jira_admin.assert_not_called()

    def test_check_transition_permission_missing_reporter_name_denied(self):
        """Test that missing reporter name results in denial for Review to Done."""
        # Arrange
        issue_data = {"fields": {"reporter": {}}}  # No name field
        webhook_body = {"user": {"name": "john.doe"}}
        self.mock_jira_repository.is_user_jira_admin.return_value = False
        
        # Act
        result = self.validator.check_transition_permission(
            issue_data, webhook_body, "Review", "Done"
        )
        
        # Assert
        self.assertFalse(result)
        # Should still check admin status since user name exists
        self.mock_jira_repository.is_user_jira_admin.assert_called_once_with("john.doe")


if __name__ == "__main__":
    unittest.main()
