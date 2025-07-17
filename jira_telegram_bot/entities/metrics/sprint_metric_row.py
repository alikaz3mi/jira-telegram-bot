"""Sprint metric row entity for Google Sheets developer metrics matrix."""

from typing import Optional

from pydantic import BaseModel, Field


class SprintMetricRow(BaseModel):
    """Immutable sprint metrics row for Google Sheets.
    
    Args:
        developer_name: Display name of the developer
        all_tasks: Total number of tasks assigned
        completed_tasks: Number of completed tasks
        releases_related_to_person: Number of releases person contributed to
        stories_related_to_person: Number of stories person worked on
        resolved_stories: Number of stories resolved by person
        resolved_bugs: Number of bugs resolved by person
        delivery_delay_by_day: Days of delivery delay
        bug_delivery_delay_by_day: Days of bug delivery delay
        logged_time: Total hours logged in sprint
        eta_completing_all_tasks: Estimated time to complete all tasks
        logged_time_support_epic: Hours logged on support epic
        logged_meeting: Hours in meetings
        documentatio_merge_requests: Number of documentation merge requests
        merge_requests: Total number of merge requests
        successful_merges: Number of successful merges
    """
    
    developer_name: str = Field(description="Display name of the developer")
    all_tasks: int = Field(default=0, description="Total number of tasks assigned")
    completed_tasks: int = Field(default=0, description="Number of completed tasks")
    releases_related_to_person: int = Field(default=0, description="Number of releases person contributed to")
    stories_related_to_person: int = Field(default=0, description="Number of stories person worked on")
    resolved_stories: int = Field(default=0, description="Number of stories resolved by person")
    resolved_bugs: int = Field(default=0, description="Number of bugs resolved by person")
    delivery_delay_by_day: int = Field(default=0, description="Days of delivery delay")
    bug_delivery_delay_by_day: int = Field(default=0, description="Days of bug delivery delay")
    logged_time: float = Field(default=0.0, description="Total hours logged in sprint")
    eta_completing_all_tasks: float = Field(default=0.0, description="Estimated time to complete all tasks")
    logged_time_support_epic: float = Field(default=0.0, description="Hours logged on support epic")
    logged_meeting: float = Field(default=0.0, description="Hours in meetings")
    documentatio_merge_requests: int = Field(default=0, description="Number of documentation merge requests")
    merge_requests: int = Field(default=0, description="Total number of merge requests")
    successful_merges: int = Field(default=0, description="Number of successful merges")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
