"""Interface for Synth repository operations."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.release_notes import SprintInfo
from jira_telegram_bot.entities.synth_pm.change_tracker import SynthPMChangeTracker
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMSheetSyncStatus
from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import (
    SynthPMSyncFilterCriteria,
)


class SynthPMRepositoryInterface(ABC):
    """Interface for Synth repository operations."""

    def clear_sprint_cache(self) -> None:
        """Clear the in-memory sprint cache."""
        pass

    @abstractmethod
    async def get_developer_board_features(
        self,
        filter_criteria: Optional[SynthPMSyncFilterCriteria] = None,
    ) -> List[SynthPMFeatureEntity]:
        """Get features from Google Sheets with optional filtering.

        Args:
            filter_criteria: Optional filter criteria for sprints/releases

        Returns:
            List of feature entities matching the filter criteria
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
        updates: Dict[str, any],
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
        updates: Dict[str, any],
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
        feature: SynthPMFeatureEntity,
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
        assignees: Optional[List[str]] = None,
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
        feature: SynthPMFeatureEntity,
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
        feature_assignees: Optional[List[str]] = None,
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
        user: str,
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

    @abstractmethod
    def get_reverse_status_mapping(self) -> Dict[str, str]:
        """Get the reverse status mapping for Jira statuses.

        Returns:
            Dictionary mapping Jira statuses to their reverse values
        """
        pass

    @abstractmethod
    async def get_project_info(self, project_key: str) -> Dict[str, any]:
        """Get project information from projects_info.json.

        Args:
            project_key: Project key to get info for

        Returns:
            Project information dictionary
        """
        pass

    @abstractmethod
    async def update_jira_task_description(
        self,
        issue_key: str,
        description: str,
    ) -> bool:
        """Update Jira task description with generated documentation.

        Args:
            issue_key: Jira issue key
            description: New description content

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def update_jira_release(
        self,
        project_key: str,
        release_name: str,
        description: str,
    ) -> bool:
        """Update Jira release description with enhanced content.

        Args:
            project_key: Jira project key
            release_name: Name of the release to update
            description: New description content

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def update_google_sheet_custom_fields(
        self,
        issue_key: str,
        custom_fields: Dict[str, Any],
    ) -> bool:
        """Update custom fields for a Google Sheet row by issue key.

        Args:
            issue_key: The Jira issue key to match
            custom_fields: Dictionary of field names to values

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_change_tracker(self) -> SynthPMChangeTracker:
        """Get the current change tracker state.

        Returns:
            SynthPMChangeTracker instance
        """
        pass

    @abstractmethod
    async def save_change_tracker(self, tracker: SynthPMChangeTracker) -> bool:
        """Save the change tracker state.

        Args:
            tracker: SynthPMChangeTracker instance to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def detect_feature_changes(
        self,
        current_features: List[SynthPMFeatureEntity],
    ) -> Dict[str, List[SynthPMFeatureEntity]]:
        """Detect what features have changed since last sync.

        Args:
            current_features: Current list of features from Google Sheets

        Returns:
            Dictionary categorizing features by change type
        """
        pass

    @abstractmethod
    async def update_change_tracker(
        self,
        processed_features: List[SynthPMFeatureEntity],
        generated_docs_for: Optional[List[int]] = None,
    ) -> bool:
        """Update change tracker after processing features.

        Args:
            processed_features: List of processed features
            generated_docs_for: List of sheet_row_numbers that got documentation generated

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def force_documentation_regeneration(
        self,
        sheet_row_numbers: List[int],
    ) -> bool:
        """Force documentation regeneration for specific features.

        Args:
            sheet_row_numbers: List of row numbers to force regeneration for

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_story_by_release_name(self, release_name: str) -> Optional[str]:
        """Check if a story already exists for the given release name.

        Args:
            release_name: Name of the release to search for

        Returns:
            Story issue key if found, None otherwise
        """
        pass

    @abstractmethod
    async def sync_remaining_hours_to_sheet(
        self,
        feature: SynthPMFeatureEntity,
    ) -> bool:
        """Fetch remaining estimate from Jira worklog and update Google Sheet.

        Args:
            feature: Feature entity with developer_board_issue_key.

        Returns:
            True if the sheet was updated, False otherwise.
        """
        pass

    @abstractmethod
    async def create_release_story(
        self,
        release_name: str,
        features: List[SynthPMFeatureEntity],
        release_note: Optional['ReleaseNoteEntity'] = None,
    ) -> Optional[str]:
        """Create a story for a release based on features.

        Args:
            release_name: Name of the release
            features: List of features in this release
            release_note: Optional release note entity for description and metadata

        Returns:
            Story issue key if successful, None otherwise
        """
        pass

    @abstractmethod
    async def create_subtask_for_release(
        self,
        parent_story_key: str,
        feature: SynthPMFeatureEntity,
        assignees: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Create a subtask for a feature under a release story.

        Args:
            parent_story_key: Parent story issue key
            feature: Feature entity
            assignees: List of assignee usernames

        Returns:
            Subtask issue key if successful, None otherwise
        """
        pass
