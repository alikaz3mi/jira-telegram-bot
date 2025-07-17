"""Metric event entity for tracking development activities."""

from datetime import datetime
from typing import Dict, Optional, Any

from pydantic import BaseModel, Field

from jira_telegram_bot.entities.metrics.constants import MetricType


class MetricEvent(BaseModel):
    """Immutable event representing a trackable metric occurrence.
    
    Args:
        event_id: Unique identifier for idempotency
        metric_type: Type of metric being tracked
        developer_key: Identifier for the developer (email, username, etc.)
        timestamp: When the event occurred
        value: Numeric value of the metric (e.g., hours logged, story points)
        project_key: Jira project key
        issue_key: Jira issue key (optional)
        sprint_id: Sprint identifier (optional)
        metadata: Additional event-specific data
    """
    
    event_id: str = Field(description="Unique identifier for idempotency")
    metric_type: MetricType = Field(description="Type of metric being tracked")
    developer_key: str = Field(description="Identifier for the developer")
    timestamp: datetime = Field(description="When the event occurred")
    value: float = Field(default=1.0, description="Numeric value of the metric")
    project_key: str = Field(description="Jira project key")
    issue_key: Optional[str] = Field(default=None, description="Jira issue key")
    sprint_id: Optional[str] = Field(default=None, description="Sprint identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional event data")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
