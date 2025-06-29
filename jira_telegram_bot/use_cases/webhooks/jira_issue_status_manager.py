from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.jira_status_constants import JiraStatusConstants
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class JiraIssueStatusManager:
    """
    Manages Jira issue status changes and related operations.
    
    Handles status reversions, time estimate updates, and comment additions.
    """
    
    def __init__(self, jira_repository: TaskManagerRepositoryInterface):
        self._jira_repository = jira_repository
    
    def revert_status_and_comment(
        self, 
        issue_key: str, 
        original_status: str, 
        user_display_name: str
    ) -> None:
        """
        Revert an issue status back to the original status and add a comment explaining why.
        
        Args:
            issue_key: The Jira issue key
            original_status: Status to revert back to
            user_display_name: Display name of user who attempted the change
        """
        try:
            # Transition back to original status
            self._jira_repository.transition_task(issue_key, original_status)
            
            # Add comment explaining the reversion
            comment = self._build_reversion_comment(original_status, user_display_name)
            self._jira_repository.add_comment(issue_key, comment)
            
            LOGGER.info(f"Reverted issue {issue_key} to {original_status} due to insufficient permissions")
            
        except Exception as e:
            LOGGER.error(f"Error reverting status for issue {issue_key}: {e}")
    
    def update_time_estimate_to_zero(self, issue_key: str) -> None:
        """
        Update the remaining time estimate to zero when issue is moved to done.
        
        Args:
            issue_key: The Jira issue key
        """
        try:
            self._jira_repository.update_time_estimate(issue_key, "0h")
            LOGGER.info(f"Updated remaining time estimate to 0h for issue {issue_key}")
        except Exception as e:
            LOGGER.error(f"Error updating time estimate for issue {issue_key}: {e}")
    
    def should_update_time_estimate(self, to_status: str) -> bool:
        """
        Check if time estimate should be updated for the given status transition.
        
        Args:
            to_status: Target status
            
        Returns:
            True if time estimate should be updated
        """
        if not to_status:
            return False
        return to_status.lower() == JiraStatusConstants.DONE.value.lower()
    
    def _build_reversion_comment(self, original_status: str, user_display_name: str) -> str:
        """
        Build the comment text for status reversion.
        
        Args:
            original_status: Status that was reverted to
            user_display_name: Display name of user who attempted the change
            
        Returns:
            Comment text explaining the reversion
        """
        return (
            f"Issue was reverted to '{original_status}' by system. "
            f"Only the reporter or Jira administrators can move issues from Review to Done. "
            f"User {user_display_name} does not have permission for this action."
        )
