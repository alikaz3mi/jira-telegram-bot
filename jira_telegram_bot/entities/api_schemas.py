"""API schemas for webhook responses."""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class WebhookResponse(BaseModel):
    """Standard webhook response schema."""
    
    status: str = Field(description="Response status (success, error, ignored)")
    message: str = Field(description="Response message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional response data")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class TelegramUpdate(BaseModel):
    """Telegram update schema."""
    
    update_id: int = Field(description="Update identifier")
    message: Optional[Dict[str, Any]] = Field(default=None, description="Message data")
    edited_message: Optional[Dict[str, Any]] = Field(default=None, description="Edited message data")
    channel_post: Optional[Dict[str, Any]] = Field(default=None, description="Channel post data")
    edited_channel_post: Optional[Dict[str, Any]] = Field(default=None, description="Edited channel post data")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
