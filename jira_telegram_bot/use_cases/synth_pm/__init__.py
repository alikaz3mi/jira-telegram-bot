"""Refactored SynthPM use case following SOLID principles."""
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
from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import (
    SynthPMSyncFilterCriteria,
)
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.synth_pm_repository_interface import (
    SynthPMRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.use_cases.synth_pm.sync_developer_board_use_case import (
    SyncDeveloperBoardUseCase,
)
from jira_telegram_bot.use_cases.synth_pm.sync_release_notes_use_case import (
    SyncReleaseNotesUseCase,
)


class SynthPMUseCase:
    """Refactored use case for managing SynthPM operations following SOLID principles."""

    def __init__(
        self,
        repository: SynthPMRepositoryInterface,
        settings: SynthPMSettings,
        user_config: UserConfigInterface,
        notification_gateway: NotificationGatewayInterface,
        google_sheets_adapter: SynthPMGoogleSheetsAdapter,
        jira_adapter: SynthPMJiraAdapter,
    ):
        """Initialize the use case.

        Args:
            repository: SynthPM repository interface
            settings: SynthPM settings
            user_config: User configuration interface
            notification_gateway: Notification gateway interface
            google_sheets_adapter: Google Sheets adapter
            jira_adapter: Jira adapter
        """
        self.repository = repository
        self.settings = settings
        self.user_config = user_config
        self.notification_gateway = notification_gateway

        # Initialize focused use cases
        self.sync_developer_board_use_case = SyncDeveloperBoardUseCase(
            google_sheets_adapter,
            jira_adapter,
            user_config,
        )

        self.sync_release_notes_use_case = SyncReleaseNotesUseCase(
            google_sheets_adapter,
            notification_gateway,
        )

    async def sync_developer_board_features(
        self,
        filter_criteria: Optional[SynthPMSyncFilterCriteria] = None,
    ) -> Dict[str, Any]:
        """Synchronize features between Google Sheets, Jira, and Telegram with optional filtering.

        Args:
            filter_criteria: Optional filter criteria for sprints/releases

        Returns:
            Sync result summary
        """
        try:
            LOGGER.info("Starting developer board synchronization")

            # Apply default filtering if no explicit filter provided
            effective_filter = (
                filter_criteria or self.settings.get_default_filter_criteria()
            )
            if effective_filter:
                LOGGER.info(
                    f"Applying sync filter criteria: sprints={effective_filter.sprints}, "
                    f"releases={effective_filter.releases}, versions={effective_filter.release_versions}",
                )

            # Use the focused use case for developer board sync
            sync_results = await self.sync_developer_board_use_case.sync_features()

            # Handle cleanup of deleted tasks
            if sync_results.get("total_features", 0) > 0:
                current_features = await self.repository.get_developer_board_features(
                    effective_filter,
                )
                await self._cleanup_deleted_tasks(current_features, sync_results)

            # Update change tracker
            if sync_results.get("total_features", 0) > 0:
                current_features = await self.repository.get_developer_board_features(
                    effective_filter,
                )
                await self.repository.update_change_tracker(current_features)

            LOGGER.info(f"Developer board synchronization completed: {sync_results}")
            return sync_results

        except Exception as e:
            error_msg = f"Error during developer board synchronization: {e}"
            LOGGER.error(error_msg)
            return {"error": error_msg}

    async def sync_release_notes(self) -> Dict[str, Any]:
        """Synchronize Release Notes and post to Telegram.

        Returns:
            Sync result summary
        """
        try:
            LOGGER.info("Starting release notes synchronization")

            # Use the focused use case for release notes sync
            sync_results = await self.sync_release_notes_use_case.sync_release_notes()

            LOGGER.info(f"Release notes synchronization completed: {sync_results}")
            return sync_results

        except Exception as e:
            error_msg = f"Error during release notes synchronization: {e}"
            LOGGER.error(error_msg)
            return {"error": error_msg}

    async def _cleanup_deleted_tasks(
        self,
        current_features: List[SynthPMFeatureEntity],
        sync_results: Dict[str, Any],
    ):
        """Clean up Jira tasks that are no longer in Google Sheets.

        Args:
            current_features: Current features from Google Sheets
            sync_results: Dictionary to track sync results
        """
        try:
            # Detect deleted features
            changes = await self.repository.detect_feature_changes(current_features)
            deleted_features = changes.get("deleted", [])

            if deleted_features:
                LOGGER.info(
                    f"Found {len(deleted_features)} deleted features to clean up",
                )

                for deleted_feature in deleted_features:
                    # Archive or transition deleted tasks instead of hard deletion
                    await self._archive_deleted_feature_tasks(deleted_feature)

                sync_results["cleaned_up_tasks"] = len(deleted_features)
            else:
                sync_results["cleaned_up_tasks"] = 0

        except Exception as e:
            LOGGER.error(f"Error cleaning up deleted tasks: {e}")
            sync_results["cleanup_errors"] = str(e)

    async def _archive_deleted_feature_tasks(
        self,
        deleted_feature: SynthPMFeatureEntity,
    ):
        """Archive tasks for a deleted feature.

        Args:
            deleted_feature: Deleted feature entity
        """
        try:
            # This would involve transitioning the associated Jira tasks to an archived state
            # rather than deleting them outright
            LOGGER.info(
                f"Archiving tasks for deleted feature: {deleted_feature.task_title}",
            )

            # Implementation would go here to:
            # 1. Find associated PM and Developer board tasks
            # 2. Transition them to "Archived" or "Cancelled" status
            # 3. Add a comment explaining the archival

        except Exception as e:
            LOGGER.error(
                f"Error archiving tasks for deleted feature {deleted_feature.task_title}: {e}",
            )

    async def handle_jira_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, str]:
        """Handle Jira webhook events.

        Args:
            webhook_data: Webhook payload data

        Returns:
            Response status
        """
        try:
            LOGGER.info("Processing Jira webhook")

            # Extract issue information from webhook
            issue_key = webhook_data.get("issue", {}).get("key")
            if not issue_key:
                return {"status": "error", "message": "No issue key in webhook"}

            # Find the corresponding feature
            features = await self.repository.get_developer_board_features()
            feature = None

            for f in features:
                if (
                    f.jira_issue_key == issue_key
                    or f.developer_board_issue_key == issue_key
                ):
                    feature = f
                    break

            if not feature:
                return {
                    "status": "warning",
                    "message": f"No feature found for issue {issue_key}",
                }

            # Handle the webhook based on event type
            event_type = webhook_data.get("webhookEvent", "")

            if event_type == "jira:issue_updated":
                await self._handle_jira_issue_updated(feature, webhook_data)

            return {
                "status": "success",
                "message": f"Processed webhook for {issue_key}",
            }

        except Exception as e:
            error_msg = f"Error handling Jira webhook: {e}"
            LOGGER.error(error_msg)
            return {"status": "error", "message": error_msg}

    async def _handle_jira_issue_updated(
        self,
        feature: SynthPMFeatureEntity,
        webhook_data: Dict[str, Any],
    ):
        """Handle Jira issue updated webhook.

        Args:
            feature: Feature entity
            webhook_data: Webhook payload data
        """
        try:
            issue_data = webhook_data.get("issue", {})
            issue_fields = issue_data.get("fields", {})

            # Determine which fields were updated and sync back to Google Sheets if needed
            updates = {}

            # Check status updates
            status = issue_fields.get("status", {}).get("name")
            if status:
                # Map Jira status back to Google Sheets status
                from jira_telegram_bot.entities.synth_pm.services import (
                    SynthPMStatusService,
                )

                sheet_status = SynthPMStatusService.map_jira_status_to_sheet(status)
                if sheet_status != feature.status:
                    updates["status"] = sheet_status

            # Update Google Sheets if there are changes
            if updates:
                await self.repository.update_developer_board_feature(
                    feature.sheet_row_number,
                    updates,
                )
                LOGGER.info(
                    f"Updated Google Sheets for feature {feature.task_title} with: {updates}",
                )

        except Exception as e:
            LOGGER.error(f"Error handling issue updated webhook: {e}")

    async def handle_sheet_update(
        self,
        row_number: int,
        updates: Dict[str, Any],
    ) -> Dict[str, str]:
        """Handle Google Sheets update events.

        Args:
            row_number: Row number that was updated
            updates: Dictionary of updates

        Returns:
            Response status
        """
        try:
            LOGGER.info(f"Processing Google Sheets update for row {row_number}")

            # Get the current features to find the one that was updated
            features = await self.repository.get_developer_board_features()
            feature = None

            for f in features:
                if f.sheet_row_number == row_number:
                    feature = f
                    break

            if not feature:
                return {
                    "status": "warning",
                    "message": f"No feature found for row {row_number}",
                }

            # Process the update through the normal sync flow
            sync_results = {"processed_features": 0, "errors": []}

            # This would trigger a focused sync for just this feature
            # For now, we'll use the existing sync mechanism
            await self.sync_developer_board_use_case._process_feature(
                feature,
                sync_results,
            )

            return {
                "status": "success",
                "message": f"Processed update for row {row_number}",
            }

        except Exception as e:
            error_msg = f"Error handling sheet update: {e}"
            LOGGER.error(error_msg)
            return {"status": "error", "message": error_msg}

    async def force_documentation_regeneration(
        self,
        sheet_row_numbers: List[int],
    ) -> bool:
        """Force documentation regeneration for specific features.

        Args:
            sheet_row_numbers: List of sheet row numbers to regenerate docs for

        Returns:
            True if successful, False otherwise
        """
        try:
            # Force regeneration in the repository
            success = await self.repository.force_documentation_regeneration(
                sheet_row_numbers,
            )

            if success:
                # Trigger actual documentation generation here
                # This would involve calling the documentation generation use case
                LOGGER.info(
                    f"Forced documentation regeneration for rows: {sheet_row_numbers}",
                )

            return success

        except Exception as e:
            LOGGER.error(f"Error forcing documentation regeneration: {e}")
            return False

    # Convenience methods for common filtering scenarios

    async def sync_features_by_sprint(
        self,
        sprints: List[str],
        include_empty: bool = False,
    ) -> Dict[str, Any]:
        """Synchronize features for specific sprints only.

        Args:
            sprints: List of sprint names to sync
            include_empty: Whether to include features with no sprint assigned

        Returns:
            Sync result summary
        """
        filter_criteria = SynthPMSyncFilterCriteria.create_sprint_filter(
            sprints=sprints,
            include_empty=include_empty,
        )
        return await self.sync_developer_board_features(filter_criteria)

    async def sync_features_by_release(
        self,
        releases: Optional[List[str]] = None,
        versions: Optional[List[str]] = None,
        include_empty: bool = False,
    ) -> Dict[str, Any]:
        """Synchronize features for specific releases or versions only.

        Args:
            releases: List of release names to sync
            versions: List of version numbers to sync
            include_empty: Whether to include features with no release assigned

        Returns:
            Sync result summary
        """
        filter_criteria = SynthPMSyncFilterCriteria.create_release_filter(
            releases=releases,
            versions=versions,
            include_empty=include_empty,
        )
        return await self.sync_developer_board_features(filter_criteria)

    async def sync_current_sprint_features(self) -> Dict[str, Any]:
        """Synchronize features for the current active sprint only.

        Returns:
            Sync result summary
        """
        # For now, this method would need to be enhanced to detect the current sprint
        # This could be done by integrating with Jira's sprint information
        LOGGER.warning(
            "Current sprint detection not implemented - syncing all features",
        )
        return await self.sync_developer_board_features()

    # Legacy methods for backward compatibility - these delegate to the appropriate focused use cases

    def _should_post_to_telegram(self, feature: SynthPMFeatureEntity) -> bool:
        """Check if feature should be posted to Telegram.

        Args:
            feature: Feature entity

        Returns:
            True if should post to Telegram
        """
        from jira_telegram_bot.entities.synth_pm.constants import (
            TELEGRAM_TRIGGER_STATUSES,
        )

        return feature.status in TELEGRAM_TRIGGER_STATUSES if feature.status else False

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
        return self.sync_developer_board_use_case._extract_assignees_from_feature(
            feature,
        )
