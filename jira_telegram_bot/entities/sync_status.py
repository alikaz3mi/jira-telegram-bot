"""Entity for sync status tracking."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field


class SyncStatus(BaseModel):
    """Tracks the synchronization status for a Jira project.
    
    This entity maintains state about when projects were last synced,
    how many issues were processed, and any errors encountered.
    """

    project_key: str = Field(description="Jira project key (e.g., 'PROJ')")
    last_full_sync: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last full project sync",
    )
    last_incremental_sync: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last incremental sync",
    )
    last_sync_status: str = Field(
        default="never_synced",
        description="Status of last sync: success, partial, failed, never_synced",
    )
    issues_synced: int = Field(
        default=0,
        description="Number of issues successfully synced in last operation",
    )
    issues_failed: int = Field(
        default=0,
        description="Number of issues that failed to sync",
    )
    sync_duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration of last sync operation in seconds",
    )
    errors: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Error details from last sync, if any",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this record was first created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When this record was last updated",
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "project_key": "PROJ",
                "last_full_sync": "2025-12-03T10:00:00",
                "last_incremental_sync": "2025-12-03T10:30:00",
                "last_sync_status": "success",
                "issues_synced": 150,
                "issues_failed": 0,
                "sync_duration_seconds": 45.2,
                "errors": None,
            },
        }
