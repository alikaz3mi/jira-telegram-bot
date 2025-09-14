"""Use case for synchronizing developer board features."""
from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.synth_pm.google_sheets_adapter import (
    SynthPMGoogleSheetsAdapter,
)
from jira_telegram_bot.adapters.synth_pm.jira_adapter import SynthPMJiraAdapter
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class SyncDeveloperBoardUseCase:
    """Use case for synchronizing developer board features."""

    def __init__(
        self,
        google_sheets_adapter: SynthPMGoogleSheetsAdapter,
        jira_adapter: SynthPMJiraAdapter,
        user_config: UserConfigInterface,
    ):
        """Initialize the use case.

        Args:
            google_sheets_adapter: Google Sheets adapter
            jira_adapter: Jira adapter
            user_config: User configuration interface
        """
        self.google_sheets_adapter = google_sheets_adapter
        self.jira_adapter = jira_adapter
        self.user_config = user_config

    async def sync_features(self) -> Dict[str, Any]:
        """Synchronize features between Google Sheets and Jira.

        Returns:
            Sync result summary
        """
        try:
            LOGGER.info("Starting developer board synchronization")

            # Get current features from Google Sheets
            current_features = (
                await self.google_sheets_adapter.get_developer_board_features()
            )

            sync_results = {
                "total_features": len(current_features),
                "created_pm_tasks": 0,
                "updated_pm_tasks": 0,
                "created_dev_tasks": 0,
                "updated_dev_tasks": 0,
                "errors": [],
            }

            for feature in current_features:
                try:
                    await self._process_feature(feature, sync_results)
                except Exception as e:
                    error_msg = f"Error processing feature {feature.task_title}: {e}"
                    LOGGER.error(error_msg)
                    sync_results["errors"].append(error_msg)

            LOGGER.info(f"Developer board synchronization completed: {sync_results}")
            return sync_results

        except Exception as e:
            error_msg = f"Error during developer board synchronization: {e}"
            LOGGER.error(error_msg)
            return {"error": error_msg}

    async def _process_feature(
        self,
        feature: SynthPMFeatureEntity,
        sync_results: Dict[str, Any],
    ):
        """Process a single feature.

        Args:
            feature: Feature entity
            sync_results: Dictionary to track sync results
        """
        # Process PM Board task
        if not feature.jira_issue_key:
            # Create new PM Board task
            pm_issue_key = await self.jira_adapter.create_pm_board_task(feature)
            if pm_issue_key:
                # Update Google Sheet with the new issue key
                await self.google_sheets_adapter.update_developer_board_feature(
                    feature.sheet_row_number,
                    {"jira_issue_key": pm_issue_key},
                )
                sync_results["created_pm_tasks"] += 1
        else:
            # Update existing PM Board task
            success = await self.jira_adapter.update_pm_board_task(feature)
            if success:
                sync_results["updated_pm_tasks"] += 1

        # Process Developer Board task if needed
        assignees = self._extract_assignees_from_feature(feature)
        if assignees and self._should_create_developer_task(feature):
            if not feature.developer_board_issue_key:
                # Create new Developer Board task
                dev_issue_key = await self._create_developer_board_task(
                    feature,
                    assignees,
                )
                if dev_issue_key:
                    await self.google_sheets_adapter.update_developer_board_feature(
                        feature.sheet_row_number,
                        {"developer_board_issue_key": dev_issue_key},
                    )
                    sync_results["created_dev_tasks"] += 1
            else:
                # Update existing Developer Board task
                success = await self.jira_adapter.update_developer_board_task(
                    feature,
                    assignees,
                )
                if success:
                    sync_results["updated_dev_tasks"] += 1

    def _extract_assignees_from_feature(
        self,
        feature: SynthPMFeatureEntity,
    ) -> List[str]:
        """Extract assignees from feature's people columns using UserConfig.

        Args:
            feature: Feature entity

        Returns:
            List of assignee Jira usernames
        """
        assignees = []

        if not feature.times:
            return assignees

        all_user_configs = self.user_config.get_all_user_configs()
        for user_config in all_user_configs.values():
            if user_config.google_sheet_name in feature.times:
                assignees.append(user_config.jira_username)

        return assignees

    def _should_create_developer_task(self, feature: SynthPMFeatureEntity) -> bool:
        """Determine if a developer board task should be created.

        Args:
            feature: Feature entity

        Returns:
            True if developer task should be created
        """
        # Check if feature has implementation requirements
        if not feature.status:
            return False

        # Only create developer tasks for features ready for implementation
        # Extract the status number from full status text (e.g., "۵. آماده پیاده سازی فنی" -> "۵")
        status_number = (
            feature.status.split(".")[0].strip()
            if "." in feature.status
            else feature.status.strip()
        )

        implementation_statuses = [
            "۵",  # Ready for tech implementation
            "۶",  # In progress
            "۷",  # Testing
        ]
        return status_number in implementation_statuses

    async def _create_developer_board_task(
        self,
        feature: SynthPMFeatureEntity,
        assignees: List[str],
    ) -> Optional[str]:
        """Create developer board task for feature.

        Args:
            feature: Feature entity
            assignees: List of assignees

        Returns:
            Developer board issue key if successful
        """
        try:
            # Parse sprint information from feature
            sprint_info = None
            if feature.sprint_list:
                # Handle sprint parsing
                # For now, use a simple approach
                from jira_telegram_bot.entities.release_notes import SprintInfo

                sprint_info = SprintInfo(
                    sprint_id="1",  # Changed from int to string
                    start_date="01-01",
                    end_date="01-15",
                )

            return await self.jira_adapter.create_developer_board_task(
                feature,
                sprint_info,
                assignees,
            )

        except Exception as e:
            LOGGER.error(
                f"Error creating developer board task for {feature.task_title}: {e}",
            )
            return None
