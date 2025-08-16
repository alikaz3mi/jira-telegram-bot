"""Interface for Synth repository operations."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMSheetSyncStatus 
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity, SprintInfo


class SynthPMRepositoryInterface(ABC):
    """Interface for Synth repository operations."""
    
    @abstractmethod
    async def get_developer_board_features(self) -> List[SynthPMFeatureEntity]:
        """Get all  features from Google Sheets.
        
        Returns:
            List of  feature entities
        """
        pass
    
    @abstractmethod
    async def get_release_notes(self) -> List[ReleaseNoteEntity]:
        """Get all release notes from Google Sheets.
        
        Returns:
            List of release note entities
        """
        pass
    
    @abstractmethod
    async def update_developer_board_feature(
        self, 
        row_number: int, 
        updates: Dict[str, any]
    ) -> bool:
        """Update a specific  feature in Google Sheets.
        
        Args:
            row_number: Row number to update
            updates: Dictionary of field updates
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def update_release_note(
        self, 
        row_number: int, 
        updates: Dict[str, any]
    ) -> bool:
        """Update a specific release note in Google Sheets.
        
        Args:
            row_number: Row number to update
            updates: Dictionary of field updates
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def create_jira_task_from_feature(
        self, 
        feature: SynthPMFeatureEntity
    ) -> Optional[str]:
        """Create a PM Board Jira task from a  feature.
        
        Args:
            feature:  feature entity
            
        Returns:
            PM Board Jira issue key if successful, None otherwise
        """
        pass
    
    @abstractmethod
    async def create_developer_board_task_from_feature(
        self, 
        feature: SynthPMFeatureEntity,
        sprint_info: SprintInfo,
        assignees: Optional[List[str]] = None
    ) -> Optional[str]:
        """Create a  Jira task from a  feature with sprint.
        
        Args:
            feature:  feature entity
            sprint_info: Sprint information for  board
            assignees: List of assignee usernames for the task
            
        Returns:
             Jira issue key if successful, None otherwise
        """
        pass
    
    @abstractmethod
    async def update_jira_task_from_feature(
        self, 
        feature: SynthPMFeatureEntity
    ) -> bool:
        """Update an existing PM Board Jira task from a  feature.
        
        Args:
            feature:  feature entity
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def update_developer_board_task_from_feature(
        self, 
        feature: SynthPMFeatureEntity,
        assignees: Optional[List[str]] = None
    ) -> bool:
        """Update an existing  Jira task from a  feature.
        
        Args:
            feature:  feature entity
            assignees: List of assignee usernames for the task
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def track_time_in_developer_board(
        self,
        developer_board_issue_key: str,
        time_spent: int,
        user: str
    ) -> bool:
        """Track time spent on  task and deduct from original story points.
        
        Args:
            developer_board_issue_key:  issue key
            time_spent: Time spent in hours
            user: User who spent the time
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_sync_status(self) -> Optional[SynthPMSheetSyncStatus]:
        """Get the current sync status.
        
        Returns:
            Sync status entity or None if not found
        """
        pass
    
    @abstractmethod
    async def update_sync_status(self, status: SynthPMSheetSyncStatus) -> bool:
        """Update the sync status.
        
        Args:
            status: Sync status entity
            
        Returns:
            True if successful, False otherwise
        """
        pass
