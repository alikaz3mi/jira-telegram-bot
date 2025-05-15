"""API schema models for webhook endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WebhookResponse(BaseModel):
    """Standard response for webhook endpoints.
    
    Args:
        status: Response status (success, error, ignored)
        message: Descriptive message about the outcome
    """
    status: str = Field(description="Status of the webhook processing")
    message: Optional[str] = Field(None, description="Additional information about the result")


class JiraWebhookRequest(BaseModel):
    """Jira webhook event payload.
    
    This is a simplified representation as Jira webhooks have complex schemas.
    The use case will handle detailed validation and parsing.
    
    Args:
        issue_event_type_name: Type of the event (e.g., issue_created, issue_updated)
        issue: Issue data
    """
    issue_event_type_name: Optional[str] = Field(None, description="Type of Jira event")
    issue: Optional[Dict[str, Any]] = Field(None, description="Issue data")
    changelog: Optional[Dict[str, Any]] = Field(None, description="Changes made in this event")
    comment: Optional[Dict[str, Any]] = Field(None, description="Comment information for comment events")
    user: Optional[Dict[str, Any]] = Field(None, description="User who triggered the event")


class TelegramUpdate(BaseModel):
    """Telegram update event.
    
    This is a simplified representation of Telegram's Update object.
    
    Args:
        update_id: Unique identifier for this update
        message: Optional message data
        edited_message: Optional edited message data
    """
    update_id: int = Field(description="The update's unique identifier")
    message: Optional[Dict[str, Any]] = Field(None, description="New incoming message")
    edited_message: Optional[Dict[str, Any]] = Field(None, description="Edit to a previously sent message")
    channel_post: Optional[Dict[str, Any]] = Field(None, description="New incoming channel post")
    callback_query: Optional[Dict[str, Any]] = Field(None, description="New incoming callback query")
