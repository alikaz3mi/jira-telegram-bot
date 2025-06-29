from __future__ import annotations

from typing import Any
from typing import Dict

from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings


class JiraWebhookMessageFormatter:
    """
    Formats messages for Jira webhook events to be sent via Telegram.
    
    Creates consistent and informative messages for different types of Jira events.
    """
    
    def __init__(self, jira_settings: JiraConnectionSettings):
        self.jira_settings = jira_settings
    
    def format_issue_created_message(
        self, 
        issue_data: Dict[str, Any], 
        webhook_body: Dict[str, Any]
    ) -> str:
        """
        Format message for issue creation events.
        
        Args:
            issue_data: Jira issue data from webhook
            webhook_body: Full webhook payload
            
        Returns:
            Formatted message string
        """
        summary = issue_data["fields"].get("summary", "")
        creator_name = webhook_body.get("user", {}).get("displayName", "someone")
        
        return (
            f"**Jira Event**\n"
            f"Issue *created* by {creator_name}\n"
            f"Key: {issue_data['key']}\n"
            f"Summary: {summary}"
        )
    
    def format_issue_generic_message(
        self, 
        issue_data: Dict[str, Any], 
        webhook_body: Dict[str, Any]
    ) -> str:
        """
        Format message for generic issue events.
        
        Args:
            issue_data: Jira issue data from webhook
            webhook_body: Full webhook payload
            
        Returns:
            Formatted message string
        """
        summary = issue_data["fields"].get("summary", "")
        creator_name = webhook_body.get("user", {}).get("displayName", "someone")
        issue_url = self._build_issue_url(issue_data["key"])
        
        return (
            f"🔔 *Jira Event*\n\n"
            f"🔑 Issue Key: {issue_url}\n\n"
            f"📝 Summary: {summary}\n\n"
            f"👤 Created by {creator_name}"
        )
    
    def format_comment_message(
        self, 
        issue_data: Dict[str, Any], 
        comment_info: Dict[str, Any]
    ) -> str:
        """
        Format message for comment events.
        
        Args:
            issue_data: Jira issue data from webhook
            comment_info: Comment information from webhook
            
        Returns:
            Formatted message string
        """
        commenter = comment_info["updateAuthor"]["displayName"]
        comment_body = comment_info["body"]
        
        return (
            f"**Jira Event**\n"
            f"New comment on *{issue_data['key']}* by {commenter}:\n\n"
            f"{comment_body}"
        )
    
    def format_status_change_message(
        self, 
        issue_key: str, 
        from_status: str, 
        to_status: str
    ) -> str:
        """
        Format message for status change events.
        
        Args:
            issue_key: The Jira issue key
            from_status: Original status
            to_status: New status
            
        Returns:
            Formatted message string
        """
        return (
            f"**Jira Event**\n"
            f"Issue *{issue_key}* moved from '{from_status}' to '{to_status}'."
        )
    
    def format_status_reversion_message(
        self, 
        issue_key: str, 
        from_status: str, 
        to_status: str
    ) -> str:
        """
        Format message for status reversion events.
        
        Args:
            issue_key: The Jira issue key
            from_status: Status reverted from
            to_status: Status reverted to
            
        Returns:
            Formatted message string
        """
        return (
            f"**Jira Event - Action Reverted**\n"
            f"Issue *{issue_key}* was reverted from '{from_status}' back to '{to_status}'.\n"
            f"Only the reporter or Jira administrators can move issues from Review to Done."
        )
    
    def _build_issue_url(self, issue_key: str) -> str:
        """
        Build the full URL for a Jira issue.
        
        Args:
            issue_key: The Jira issue key
            
        Returns:
            Full URL to the issue
        """
        return f"{self.jira_settings.domain.scheme}://{self.jira_settings.domain.host}/browse/{issue_key}"
