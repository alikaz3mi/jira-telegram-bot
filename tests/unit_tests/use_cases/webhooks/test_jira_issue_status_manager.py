from __future__ import annotations

import unittest
from unittest.mock import Mock

from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.webhooks.jira_issue_status_manager import JiraIssueStatusManager


class TestJiraIssueStatusManager(unittest.TestCase):
    """Test cases for Jira issue status management."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repository = Mock(spec=TaskManagerRepositoryInterface)
        self.status_manager = JiraIssueStatusManager(self.mock_jira_repository)

    def test_revert_status_and_comment_success(self):
        """Test successful status reversion with comment."""
        # Arrange
        issue_key = "TEST-123"
        original_status = "Review"
        user_display_name = "John Doe"
        
        # Act
        self.status_manager.revert_status_and_comment(
            issue_key, original_status, user_display_name
        )
        
        # Assert
        self.mock_jira_repository.transition_task.assert_called_once_with(
            issue_key, original_status
        )
        self.mock_jira_repository.add_comment.assert_called_once()
        
        # Check comment content
        call_args = self.mock_jira_repository.add_comment.call_args
        self.assertEqual(call_args[0][0], issue_key)
        comment_text = call_args[0][1]
        self.assertIn("reverted to 'Review'", comment_text)
        self.assertIn("John Doe", comment_text)
        self.assertIn("Review to Done", comment_text)

    def test_revert_status_and_comment_handles_transition_error(self):
        """Test that reversion handles transition errors gracefully."""
        # Arrange
        issue_key = "TEST-123"
        original_status = "Review"
        user_display_name = "John Doe"
        self.mock_jira_repository.transition_task.side_effect = Exception("Transition failed")
        
        # Act - should not raise exception
        self.status_manager.revert_status_and_comment(
            issue_key, original_status, user_display_name
        )
        
        # Assert
        self.mock_jira_repository.transition_task.assert_called_once_with(
            issue_key, original_status
        )
        # Comment should not be called if transition fails
        self.mock_jira_repository.add_comment.assert_not_called()

    def test_revert_status_and_comment_handles_comment_error(self):
        """Test that reversion handles comment errors gracefully."""
        # Arrange
        issue_key = "TEST-123"
        original_status = "Review"
        user_display_name = "John Doe"
        self.mock_jira_repository.add_comment.side_effect = Exception("Comment failed")
        
        # Act - should not raise exception
        self.status_manager.revert_status_and_comment(
            issue_key, original_status, user_display_name
        )
        
        # Assert
        self.mock_jira_repository.transition_task.assert_called_once_with(
            issue_key, original_status
        )
        self.mock_jira_repository.add_comment.assert_called_once()

    def test_update_time_estimate_to_zero_success(self):
        """Test successful time estimate update to zero."""
        # Arrange
        issue_key = "TEST-123"
        
        # Act
        self.status_manager.update_time_estimate_to_zero(issue_key)
        
        # Assert
        self.mock_jira_repository.update_time_estimate.assert_called_once_with(
            issue_key, "0h"
        )

    def test_update_time_estimate_to_zero_handles_error(self):
        """Test that time estimate update handles errors gracefully."""
        # Arrange
        issue_key = "TEST-123"
        self.mock_jira_repository.update_time_estimate.side_effect = Exception("Update failed")
        
        # Act - should not raise exception
        self.status_manager.update_time_estimate_to_zero(issue_key)
        
        # Assert
        self.mock_jira_repository.update_time_estimate.assert_called_once_with(
            issue_key, "0h"
        )

    def test_should_update_time_estimate_for_done_status(self):
        """Test that time estimate should be updated when transitioning to Done."""
        # Act
        result = self.status_manager.should_update_time_estimate("Done")
        
        # Assert
        self.assertTrue(result)

    def test_should_update_time_estimate_for_done_status_case_insensitive(self):
        """Test that time estimate check is case insensitive."""
        # Act & Assert
        self.assertTrue(self.status_manager.should_update_time_estimate("done"))
        self.assertTrue(self.status_manager.should_update_time_estimate("DONE"))
        self.assertTrue(self.status_manager.should_update_time_estimate("DoNe"))

    def test_should_not_update_time_estimate_for_other_status(self):
        """Test that time estimate should not be updated for other statuses."""
        # Act & Assert
        self.assertFalse(self.status_manager.should_update_time_estimate("In Progress"))
        self.assertFalse(self.status_manager.should_update_time_estimate("Review"))
        self.assertFalse(self.status_manager.should_update_time_estimate("To Do"))
        self.assertFalse(self.status_manager.should_update_time_estimate(""))
        self.assertFalse(self.status_manager.should_update_time_estimate(None))


if __name__ == "__main__":
    unittest.main()
