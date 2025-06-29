from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.jira_status_constants import JiraStatusConstants
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class JiraTransitionPermissionValidator:
    """
    Validates user permissions for Jira issue transitions.
    
    Handles business rules around who can perform specific status transitions.
    """
    
    def __init__(self, jira_repository: TaskManagerRepositoryInterface):
        self._jira_repository = jira_repository
    
    def check_transition_permission(
        self, 
        issue_data: Dict[str, Any], 
        webhook_body: Dict[str, Any], 
        from_status: str, 
        to_status: str
    ) -> bool:
        """
        Check if the user has permission to transition from one status to another.
        
        Args:
            issue_data: Jira issue data from webhook
            webhook_body: Full webhook payload
            from_status: Original status
            to_status: Target status
            
        Returns:
            True if transition is allowed, False otherwise
        """
        if not self._is_restricted_transition(from_status, to_status):
            return True
            
        return self._validate_review_to_done_permission(issue_data, webhook_body)
    
    def _is_restricted_transition(self, from_status: str, to_status: str) -> bool:
        """
        Check if this is a restricted transition that requires validation.
        
        Args:
            from_status: Original status
            to_status: Target status
            
        Returns:
            True if transition is restricted
        """
        return (
            from_status.lower() == JiraStatusConstants.REVIEW.value.lower() and
            to_status.lower() == JiraStatusConstants.DONE.value.lower()
        )
    
    def _validate_review_to_done_permission(
        self, 
        issue_data: Dict[str, Any], 
        webhook_body: Dict[str, Any]
    ) -> bool:
        """
        Validate permission for Review -> Done transition.
        Only reporter or Jira admin can perform this transition.
        
        Args:
            issue_data: Jira issue data from webhook
            webhook_body: Full webhook payload
            
        Returns:
            True if user has permission
        """
        user = webhook_body.get("user", {})
        user_name = user.get("name", "")
        
        if not user_name:
            return False
            
        issue_reporter = issue_data.get("fields", {}).get("reporter", {}).get("name", "")
        
        # Check if user is the reporter
        if user_name == issue_reporter:
            return True
            
        # Check if user is Jira admin
        return self._jira_repository.is_user_jira_admin(user_name)
