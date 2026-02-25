"""SynthPM use case for managing bidirectional synchronization."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.ai_agent_models.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaInput,
)
from jira_telegram_bot.entities.ai_agent_models.generate_test_scenarios import (
    GenerateTestScenariosInput,
)
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.release_notes import SprintInfo
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMSheetSyncStatus
from jira_telegram_bot.entities.synth_pm.constants import StatusDescriptions
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.ai_agents.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaUseCase,
)
from jira_telegram_bot.use_cases.ai_agents.generate_test_scenarios import (
    GenerateTestScenariosUseCase,
)
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.synth_pm_repository_interface import (
    SynthPMRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class SynthPMUseCase:
    """Use case for managing SynthPM feature synchronization."""

    def __init__(
        self,
        repository: SynthPMRepositoryInterface,
        settings: SynthPMSettings,
        user_config: UserConfigInterface,
        notification_gateway: NotificationGatewayInterface,
        generate_acceptance_criteria_use_case: GenerateAcceptanceCriteriaUseCase,
        generate_test_scenarios_use_case: GenerateTestScenariosUseCase,
    ):
        """Initialize the use case.

        Args:
            repository: SynthPM repository interface
            settings: SynthPM settings
            user_config: User configuration interface
            notification_gateway: Notification gateway interface
            generate_acceptance_criteria_use_case: Use case for generating acceptance criteria
            generate_test_scenarios_use_case: Use case for generating test scenarios
        """
        self.repository = repository
        self.settings = settings
        self.user_config = user_config
        self.notification_gateway = notification_gateway
        self.generate_acceptance_criteria_use_case = generate_acceptance_criteria_use_case
        self.generate_test_scenarios_use_case = generate_test_scenarios_use_case

    async def sync_developer_board_features(self) -> Dict[str, Any]:
        """Synchronize features between Google Sheets, Jira, and Telegram using intelligent change detection.

        Returns:
            Sync result summary
        """
        try:
            LOGGER.info("Starting intelligent SynthPM synchronization")

            self.repository.clear_sprint_cache()

            # Get current features from sheet
            features = await self.repository.get_developer_board_features()
            if not features:
                return {"status": "success", "message": "No features found to sync"}

            # Detect what has changed
            changes = await self.repository.detect_feature_changes(features)
            new_features = changes["new"]
            modified_features = changes["modified"]
            features_needing_docs = changes["needs_docs"]

            LOGGER.info(
                f"Change analysis: {len(new_features)} new, "
                f"{len(modified_features)} modified, "
                f"{len(features_needing_docs)} need documentation"
            )

            sync_results = {
                "created_jira_tasks": 0,
                "updated_jira_tasks": 0,
                "created_developer_board_tasks": 0,
                "updated_developer_board_tasks": 0,
                "converted_to_subtasks": 0,
                "deleted_tasks": 0,
                "synced_statuses": 0,
                "generated_documentation": 0,
                "skipped": [],
                "errors": [],
            }

            # Handle task cleanup - check for tasks that no longer exist in sheet
            await self._cleanup_deleted_tasks(features, sync_results)

            # Read Features sheet once to avoid multiple reads in loop
            release_notes = await self.repository.get_release_notes()
            # Map by both release_version AND release_components (descriptive name)
            # Since Tasks sheet uses descriptive names, not version numbers
            release_notes_map = {}
            for rn in release_notes:
                release_notes_map[rn.release_version] = rn
                release_notes_map[rn.release_components] = rn
            LOGGER.info(f"Loaded {len(release_notes)} release notes from Features sheet (mapped by {len(release_notes_map)} keys)")

            # Group features by release column
            release_groups = self._group_features_by_release(features)
            LOGGER.info(f"Grouped features into {len(release_groups)} releases: {list(release_groups.keys())}")

            # Process features efficiently based on change detection
            processed_features = []
            doc_generated_rows = []

            # Process each release group
            for release_name, release_features in release_groups.items():
                try:
                    LOGGER.info(f"Processing release '{release_name}' with {len(release_features)} features")
                    # Create release story with subtasks
                    story_key = await self._create_release_story_with_subtasks(
                        release_name,
                        release_features,
                        sync_results,
                        release_notes_map,
                    )
                    
                    if story_key:
                        LOGGER.info(f"Successfully processed release '{release_name}' with story {story_key}")
                        processed_features.extend(release_features)
                    else:
                        reason = "No valid features or all features skipped"
                        LOGGER.warning(f"Failed to process release '{release_name}': {reason}")
                        sync_results["errors"].append(f"Release '{release_name}' processing failed: {reason}")
                
                except Exception as e:
                    error_msg = f"Error processing release '{release_name}': {e}"
                    LOGGER.error(error_msg, exc_info=True)
                    sync_results["errors"].append(error_msg)

            # Sync remaining hours from Jira worklogs to Google Sheet
            await self._sync_remaining_hours(features, sync_results)

            # Sync Jira statuses back to Google Sheet
            await self._sync_jira_statuses_to_sheet(features, sync_results)

            # Update change tracker
            await self.repository.update_change_tracker(
                processed_features=processed_features,
                generated_docs_for=doc_generated_rows,
            )

            # Update sync status
            project_config = self.repository.project_config
            sync_status = SynthPMSheetSyncStatus(
                sheet_id=project_config.spreadsheet_id,
                worksheet_name=project_config.boards.developer_board.sheet_name,
                last_sync_time=datetime.now(),
                total_rows_synced=len(features),
                errors=sync_results["errors"],
            )

            await self.repository.update_sync_status(sync_status)

            # Log summary
            LOGGER.info(
                f"SynthPM sync completed - "
                f"Created: {sync_results['created_jira_tasks']} PM tasks, "
                f"{sync_results['created_developer_board_tasks']} dev tasks | "
                f"Updated: {sync_results['updated_jira_tasks']} PM tasks, "
                f"{sync_results['updated_developer_board_tasks']} dev tasks | "
                f"Converted: {sync_results['converted_to_subtasks']} tasks→subtasks | "
                f"Synced statuses: {sync_results['synced_statuses']} | "
                f"Deleted: {sync_results['deleted_tasks']} | "
                f"Skipped: {len(sync_results['skipped'])} | "
                f"Errors: {len(sync_results['errors'])}"
            )
            
            if sync_results["skipped"]:
                LOGGER.info(f"Skipped items summary: {len(sync_results['skipped'])} features did not meet requirements")
                for skip_msg in sync_results["skipped"][:5]:  # Show first 5
                    LOGGER.debug(f"  - {skip_msg}")
                if len(sync_results["skipped"]) > 5:
                    LOGGER.debug(f"  ... and {len(sync_results['skipped']) - 5} more")
            
            return {
                "status": "success",
                "message": "Sync completed successfully",
                "results": sync_results,
            }

        except Exception as e:
            error_msg = f"Error during SynthPM sync: {e}"
            LOGGER.error(error_msg)
            return {"status": "error", "message": error_msg}

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
            # Get previous sync status to see what tasks existed before
            previous_sync = await self.repository.get_sync_status()
            if not previous_sync:
                return  # No previous sync, nothing to clean up

            # Get all PM Board issues created by this system
            current_jira_keys = {
                f.jira_issue_key for f in current_features if f.jira_issue_key
            }
            current_developer_board_keys = {
                f.developer_board_issue_key
                for f in current_features
                if f.developer_board_issue_key
            }

            LOGGER.info(f"Current PM Board tasks: {len(current_jira_keys)}")
            LOGGER.info(
                f"Current Developer board tasks: {len(current_developer_board_keys)}",
            )

            # TODO: Implement actual cleanup logic when task deletion is confirmed
            # - Query Jira for all PM Board/Developer board tasks created by this system
            # - Compare with current sheet data
            # - Delete tasks that no longer exist in sheet
            # sync_results["deleted_tasks"] = deleted_count

        except Exception as e:
            LOGGER.error(f"Error during task cleanup: {e}")
            sync_results["errors"].append(f"Task cleanup error: {e}")

    async def _sync_remaining_hours(
        self,
        features: List[SynthPMFeatureEntity],
        sync_results: Dict[str, Any],
    ) -> None:
        """Sync remaining hours from Jira worklogs to Google Sheet.

        For every feature that has a developer board issue key, checks
        whether any work has been logged. If so, writes the remaining
        estimate back to the Remaining (h) column in the sheet.

        Args:
            features: All features from the current sync cycle.
            sync_results: Dictionary to track sync results.
        """
        updated_count = 0
        for feature in features:
            if not feature.developer_board_issue_key:
                continue
            try:
                updated = await self.repository.sync_remaining_hours_to_sheet(
                    feature,
                )
                if updated:
                    updated_count += 1
            except Exception as e:
                LOGGER.warning(
                    f"Failed to sync remaining hours for "
                    f"{feature.developer_board_issue_key}: {e}",
                )
        if updated_count:
            LOGGER.info(
                f"Synced remaining hours for {updated_count} features",
            )

    async def _sync_jira_statuses_to_sheet(
        self,
        features: List[SynthPMFeatureEntity],
        sync_results: Dict[str, Any],
    ) -> None:
        """Sync Jira task statuses back to Google Sheet.

        For every feature that has a developer board issue key, reads
        the current Jira status, maps it via the per-project mapping,
        and writes the result to the sheet when it differs.

        Args:
            features: All features from the current sync cycle.
            sync_results: Dictionary to track sync results.
        """
        updated_count = 0
        for feature in features:
            if not feature.developer_board_issue_key:
                continue
            try:
                updated = await self.repository.sync_jira_status_to_sheet(
                    feature,
                )
                if updated:
                    updated_count += 1
            except Exception as e:
                LOGGER.warning(
                    f"Failed to sync Jira status to sheet for "
                    f"{feature.developer_board_issue_key}: {e}",
                )
        if updated_count:
            LOGGER.info(
                f"Synced Jira statuses to sheet for {updated_count} features",
            )
        sync_results["synced_statuses"] = updated_count

    def _group_features_by_release(
        self,
        features: List[SynthPMFeatureEntity],
    ) -> Dict[str, List[SynthPMFeatureEntity]]:
        """Group features by their story/feature name column value.

        Features are grouped by ``story_name`` (the raw value from the
        ریلیز / Feature column).  Features whose ``story_name`` is
        ``None`` are collected under ``"No Release"``.

        Args:
            features: List of feature entities

        Returns:
            Dictionary mapping story/feature names to lists of features
        """
        release_groups: Dict[str, List[SynthPMFeatureEntity]] = {}
        for feature in features:
            raw_name = feature.story_name.strip() if feature.story_name else ""
            release_name = raw_name if raw_name else "No Release"
            if release_name not in release_groups:
                release_groups[release_name] = []
            release_groups[release_name].append(feature)
        return release_groups

    def _extract_assignees_from_feature(
        self,
        feature: SynthPMFeatureEntity,
    ) -> List[str]:
        """Extract assignees from feature's people columns using UserConfig.

        Args:
            feature: feature entity

        Returns:
            List of assignee Jira usernames
        """
        assignees = []

        all_user_configs = self.user_config.get_all_user_configs()
        seen_users = set()
        for user_config in all_user_configs.values():
            assignee = user_config.jira_username
            if (user_config.google_sheet_name and 
                feature.involved_people and 
                user_config.google_sheet_name in feature.involved_people):
                user_identifier = user_config.email or user_config.telegram_id
                if user_identifier and user_identifier in seen_users:
                    LOGGER.debug(f"Skipping duplicate user {assignee} with identifier {user_identifier}")
                    continue
                if user_identifier:
                    seen_users.add(user_identifier)
                assignees.append(assignee)

        return assignees

    async def _create_release_story_with_subtasks(
        self,
        release_name: str,
        features: List[SynthPMFeatureEntity],
        sync_results: Dict[str, Any],
        release_notes_map: Optional[Dict[str, 'ReleaseNoteEntity']] = None,
    ) -> Optional[str]:
        """Create a story for a release and add features as subtasks.
        
        If release is 'No Release' or only has 1 feature, creates regular tasks instead.

        Args:
            release_name: Name of the release
            features: List of features in this release
            sync_results: Dictionary to track sync results
            release_notes_map: Optional mapping of release versions to ReleaseNoteEntity

        Returns:
            Story issue key if created successfully, None otherwise
        """
        try:
            # Get the first feature to extract common data
            if not features:
                return None
            
            first_feature = features[0]
            
            # Validate if any feature needs to be created
            project_config = self.repository.project_config # BIG TODO
            minimum_status = project_config.sync_settings.minimum_status_for_task_creation
            
            valid_features = []
            for feature in features:
                is_valid, error_message = self.repository.validate_feature_for_task_creation(
                    feature,
                    minimum_status=minimum_status,
                )
                if is_valid:
                    valid_features.append(feature)
                else:
                    sync_results["skipped"].append(error_message)
            
            if not valid_features:
                LOGGER.info(f"No valid features found for release {release_name}")
                return None
            
            # If no release or only 1 feature, create as regular task instead of story+subtask
            if release_name == "No Release" or len(valid_features) == 1:
                LOGGER.info(f"Creating regular task for {'no release' if release_name == 'No Release' else 'singular release'}: {release_name}")
                await self._create_regular_tasks_for_features(valid_features, sync_results)
                return None
            
            # Check if story already exists for this release
            # We'll use the release name as a unique identifier
            existing_story_key = await self.repository.get_story_by_release_name(release_name)
            if existing_story_key:
                LOGGER.info(f"Story already exists for release {release_name}: {existing_story_key}")
                story_key = existing_story_key
                
                # Update story description from release note if available
                release_note = release_notes_map.get(release_name) if release_notes_map else None
                if release_note:
                    description = self.repository._build_story_description(release_note)
                    LOGGER.info(f"Building description for story {existing_story_key}: doc_link={release_note.documentation_link}, desc_len={len(release_note.description) if release_note.description else 0}")
                    try:
                        await self.repository.update_jira_task_description(existing_story_key, description)
                        LOGGER.info(f"Updated description for story {existing_story_key} from release note (length: {len(description)})")
                    except Exception as e:
                        LOGGER.warning(f"Could not update description for story {existing_story_key}: {e}")
                else:
                    available_keys = list(release_notes_map.keys()) if release_notes_map else []
                    LOGGER.warning(f"No release note found for release '{release_name}' in release_notes_map (available: {available_keys})")
            else:
                # Create the story
                release_note = release_notes_map.get(release_name) if release_notes_map else None
                if release_note:
                    LOGGER.info(f"Creating new story for '{release_name}' with release note: doc_link={release_note.documentation_link}, desc_len={len(release_note.description) if release_note.description else 0}")
                else:
                    available_keys = list(release_notes_map.keys()) if release_notes_map else []
                    LOGGER.warning(f"Creating new story for '{release_name}' WITHOUT release note (available: {available_keys})")
                story_key = await self.repository.create_release_story(
                    release_name=release_name,
                    features=valid_features,
                    release_note=release_note,
                )
                if story_key:
                    LOGGER.info(f"Created release story {story_key} for {release_name}")
                    sync_results["created_developer_board_tasks"] = (
                        sync_results.get("created_developer_board_tasks", 0) + 1
                    )
                else:
                    sync_results["errors"].append(f"Failed to create story for release: {release_name}")
                    return None
            
            release_note = release_notes_map.get(release_name) if release_notes_map else None

            await self._write_story_key_to_sheet(story_key, release_note)
            await self._sync_story_dependencies(story_key, release_note)

            # Get existing subtasks from Jira to detect deletions
            existing_jira_subtasks = set()
            try:
                story_issue = self.repository.jira_repository.get_issue(story_key)
                if story_issue and story_issue.fields.subtasks:
                    existing_jira_subtasks = {subtask.key for subtask in story_issue.fields.subtasks}
                    LOGGER.info(f"Found {len(existing_jira_subtasks)} existing subtasks in story {story_key}")
            except Exception as e:
                LOGGER.warning(f"Could not fetch existing subtasks for story {story_key}: {e}")
            
            # Track which subtasks are still valid (present in Google Sheet)
            valid_subtask_keys = set()
            
            # Create or update subtasks for each feature
            for feature in valid_features:
                # Track this subtask as valid if it exists
                if feature.developer_board_issue_key:
                    valid_subtask_keys.add(feature.developer_board_issue_key)
                
                # Update existing subtask if it already exists
                if feature.developer_board_issue_key:
                    LOGGER.info(f"Developer board task already exists for {feature.task_title}: {feature.developer_board_issue_key}")
                    
                    # Check if status allows updating
                    if feature.status in [
                        StatusDescriptions.INITIATION_AND_PRIORITIZATION.value,
                        StatusDescriptions.ANALYSIS_AND_RFP.value,
                        StatusDescriptions.USER_STORY_PREPARATION.value,
                        StatusDescriptions.COMPLETED.value
                    ]:
                        LOGGER.info(f"Skipping subtask update for {feature.task_title} - status {feature.status} does not allow updates")
                        continue
                    
                    # Convert standalone Task to Sub-task if needed
                    # (preserves all worklogs, comments, and attachments)
                    resulting_key = await self.repository.convert_existing_task_to_subtask(
                        issue_key=feature.developer_board_issue_key,
                        parent_story_key=story_key,
                    )
                    if resulting_key:
                        LOGGER.info(
                            f"Ensured {feature.developer_board_issue_key} is a "
                            f"Sub-task of {story_key} (result: {resulting_key})",
                        )
                        sync_results["converted_to_subtasks"] = (
                            sync_results.get("converted_to_subtasks", 0) + 1
                        )
                        if resulting_key != feature.developer_board_issue_key:
                            valid_subtask_keys.discard(feature.developer_board_issue_key)
                            valid_subtask_keys.add(resulting_key)
                            feature = feature.copy(
                                update={"developer_board_issue_key": resulting_key},
                            )

                    # Update the existing subtask
                    assignees = self._extract_assignees_from_feature(feature)

                    update_success = await self.repository.update_developer_board_task_from_feature(
                        feature,
                        feature_assignees=assignees,
                    )
                    
                    if update_success:
                        LOGGER.info(f"Updated subtask {feature.developer_board_issue_key} for feature {feature.task_title}")
                        sync_results["updated_developer_board_tasks"] = (
                            sync_results.get("updated_developer_board_tasks", 0) + 1
                        )
                    elif update_success is False:
                        LOGGER.debug(f"No changes needed for subtask {feature.developer_board_issue_key}")
                    continue
                    
                # Check if status allows Developer Board task creation
                if feature.status in [
                    StatusDescriptions.INITIATION_AND_PRIORITIZATION.value,
                    StatusDescriptions.ANALYSIS_AND_RFP.value,
                    StatusDescriptions.USER_STORY_PREPARATION.value,
                    StatusDescriptions.COMPLETED.value
                ]:
                    LOGGER.info(f"Skipping subtask creation for {feature.task_title} - status is {feature.status}")
                    continue
                
                # Create PM Board task first if needed (only if PM Board is enabled)
                if not feature.jira_issue_key:
                    if (self.repository.project_config.boards.pm_board and 
                        self.repository.project_config.boards.pm_board.enabled):
                        issue_key = await self.repository.create_jira_task_from_feature(feature)
                        if issue_key:
                            sync_results["created_jira_tasks"] += 1
                            feature = feature.copy(update={"jira_issue_key": issue_key})
                        else:
                            LOGGER.warning(f"Failed to create PM task for: {feature.task_title}, will create subtask without PM task")
                    else:
                        LOGGER.debug(f"PM Board disabled, skipping PM task creation for {feature.task_title}, creating subtask directly")
                
                # Create subtask for this feature
                assignees = self._extract_assignees_from_feature(feature)
                subtask_key = await self.repository.create_subtask_for_release(
                    parent_story_key=story_key,
                    feature=feature,
                    assignees=assignees,
                )
                
                if subtask_key:
                    LOGGER.info(f"Created subtask {subtask_key} for feature {feature.task_title}")
                    feature = feature.copy(
                        update={"developer_board_issue_key": subtask_key}
                    )
                    sync_results["created_developer_board_tasks"] = (
                        sync_results.get("created_developer_board_tasks", 0) + 1
                    )
                else:
                    sync_results["errors"].append(
                        f"Failed to create subtask for: {feature.task_title}",
                    )
            
            # Delete orphaned subtasks (exist in Jira but not in Google Sheet)
            orphaned_subtasks = existing_jira_subtasks - valid_subtask_keys
            if orphaned_subtasks:
                LOGGER.info(f"Found {len(orphaned_subtasks)} orphaned subtasks to delete: {orphaned_subtasks}")
                for orphaned_key in orphaned_subtasks:
                    try:
                        self.repository.jira_repository.delete_issue(orphaned_key)
                        LOGGER.info(f"Deleted orphaned subtask {orphaned_key} from story {story_key}")
                        sync_results["deleted_developer_board_tasks"] = (
                            sync_results.get("deleted_developer_board_tasks", 0) + 1
                        )
                    except Exception as e:
                        LOGGER.error(f"Failed to delete orphaned subtask {orphaned_key}: {e}")
                        sync_results["errors"].append(f"Failed to delete orphaned subtask {orphaned_key}")
            
            # Update story with components and dates from subtasks
            if story_key:
                try:
                    await self.repository.update_story_from_subtasks(story_key)
                    LOGGER.info(f"Updated story {story_key} metadata from subtasks")
                except Exception as e:
                    LOGGER.warning(f"Could not update story {story_key} metadata: {e}")
            
            return story_key
            
        except Exception as e:
            error_msg = f"Error creating release story for {release_name}: {e}"
            LOGGER.error(error_msg)
            sync_results["errors"].append(error_msg)
            return None

    async def _write_story_key_to_sheet(
        self,
        story_key: str,
        release_note: Optional[ReleaseNoteEntity],
    ) -> None:
        """Write story issue key back to the Issue Link column in Features sheet.

        Args:
            story_key: Jira story issue key
            release_note: Release note entity with the row number
        """
        if not release_note:
            return
        try:
            if release_note.issue_link == story_key:
                return
            success = await self.repository.update_release_note(
                release_note.row_number,
                {"issue_link": story_key},
            )
            if success:
                LOGGER.info(
                    f"Updated Issue Link for release '{release_note.release_components}' "
                    f"row {release_note.row_number} with story {story_key}"
                )
            else:
                LOGGER.warning(
                    f"Failed to write story key {story_key} to sheet "
                    f"row {release_note.row_number}"
                )
        except Exception as e:
            LOGGER.warning(
                f"Could not write story key {story_key} to sheet "
                f"row {release_note.row_number}: {e}"
            )

    async def _sync_story_dependencies(
        self,
        story_key: str,
        release_note: Optional[ReleaseNoteEntity],
    ) -> None:
        """Sync dependency links between stories based on release note dependencies.

        Args:
            story_key: Current story issue key
            release_note: Release note entity with dependencies information
        """
        if not release_note:
            return
        try:
            await self.repository.link_story_dependencies(
                story_key, release_note,
            )
        except Exception as e:
            LOGGER.warning(
                f"Could not sync story dependencies for {story_key}: {e}"
            )

    async def _create_regular_tasks_for_features(
        self,
        features: List[SynthPMFeatureEntity],
        sync_results: Dict[str, Any],
    ):
        """Create regular developer board tasks for features (not as story+subtask).
        
        Args:
            features: List of features to create tasks for
            sync_results: Dictionary to track sync results
        """
        for feature in features:
            # Update existing task if it already exists
            if feature.developer_board_issue_key:
                LOGGER.info(f"Developer board task already exists for {feature.task_title}: {feature.developer_board_issue_key}")
                
                # Check if status allows updating
                if feature.status in [
                    StatusDescriptions.INITIATION_AND_PRIORITIZATION.value,
                    StatusDescriptions.ANALYSIS_AND_RFP.value,
                    StatusDescriptions.USER_STORY_PREPARATION.value,
                    StatusDescriptions.COMPLETED.value
                ]:
                    LOGGER.info(f"Skipping task update for {feature.task_title} - status {feature.status} does not allow updates")
                    continue
                
                # Update the existing task
                assignees = self._extract_assignees_from_feature(feature)
                update_success = await self.repository.update_developer_board_task_from_feature(
                    feature,
                    feature_assignees=assignees,
                )
                
                if update_success:
                    LOGGER.info(f"Updated developer board task {feature.developer_board_issue_key} for {feature.task_title}")
                    sync_results["updated_developer_board_tasks"] = (
                        sync_results.get("updated_developer_board_tasks", 0) + 1
                    )
                    try:
                        issue = self.repository.jira_repository.get_issue(
                            feature.developer_board_issue_key,
                        )
                        if (
                            issue
                            and issue.fields.issuetype.name == "Story"
                            and issue.fields.subtasks
                        ):
                            await self.repository.update_story_from_subtasks(
                                feature.developer_board_issue_key,
                            )
                            LOGGER.info(
                                f"Updated story {feature.developer_board_issue_key} "
                                "metadata from subtasks"
                            )
                    except Exception as e:
                        LOGGER.warning(
                            f"Could not update story metadata for "
                            f"{feature.developer_board_issue_key}: {e}"
                        )
                elif update_success is False:
                    LOGGER.debug(f"No changes needed for developer board task {feature.developer_board_issue_key}")
                continue
                
            # Check if status allows Developer Board task creation
            if feature.status in [
                StatusDescriptions.INITIATION_AND_PRIORITIZATION.value,
                StatusDescriptions.ANALYSIS_AND_RFP.value,
                StatusDescriptions.USER_STORY_PREPARATION.value,
                StatusDescriptions.COMPLETED.value
            ]:
                LOGGER.info(f"Skipping task creation for {feature.task_title} - status is {feature.status}")
                continue
            
            # Create PM Board task first if needed (only if PM Board is enabled)
            if not feature.jira_issue_key:
                if (self.repository.project_config.boards.pm_board and 
                    self.repository.project_config.boards.pm_board.enabled):
                    issue_key = await self.repository.create_jira_task_from_feature(feature)
                    if issue_key:
                        sync_results["created_jira_tasks"] += 1
                        feature = feature.copy(update={"jira_issue_key": issue_key})
                    else:
                        LOGGER.warning(f"Failed to create PM task for: {feature.task_title}, will create developer board task without PM task")
                else:
                    LOGGER.debug(f"PM Board disabled, skipping PM task creation for {feature.task_title}, creating developer board task directly")
            
            # Create regular developer board task
            if feature.sprint_list and len(feature.sprint_list) > 0:
                assignees = self._extract_assignees_from_feature(feature)
                developer_board_key = await self.repository.create_developer_board_task_from_feature(
                    feature,
                    assignees=assignees,
                )
                if developer_board_key:
                    LOGGER.info(f"Created developer board task {developer_board_key} for {feature.task_title}")
                    feature = feature.copy(
                        update={"developer_board_issue_key": developer_board_key}
                    )
                    sync_results["created_developer_board_tasks"] = (
                        sync_results.get("created_developer_board_tasks", 0) + 1
                    )
                else:
                    sync_results["errors"].append(
                        f"Failed to create developer board task for: {feature.task_title}",
                    )
            else:
                LOGGER.warning(f"No valid sprints found for feature {feature.task_title}, skipping Developer Board task creation")

    async def _process_feature(
        self,
        feature: SynthPMFeatureEntity,
        sync_results: Dict[str, Any],
    ):
        """Process a single feature.

        Args:
            feature: feature entity
            sync_results: Dictionary to track sync results
        """
        try:
            # Skip completely empty rows
            if not feature.task_title or not feature.task_title.strip():
                LOGGER.debug(f"Row {feature.row_number}: Empty row, skipping")
                return

            # Validate feature meets minimum requirements for task creation
            project_config = self.repository.project_config
            minimum_status = project_config.sync_settings.minimum_status_for_task_creation
            
            is_valid, error_message = self.repository.validate_feature_for_task_creation(
                feature,
                minimum_status=minimum_status,
            )

            if not is_valid:
                LOGGER.warning(error_message)
                sync_results["skipped"].append(error_message)
                return

            if not (
                feature.jira_issue_key
                and feature.task_title is not None
                and feature.developer_board_issue_key is not None
            ):  
                # Create PM Board task if doesn't exist
                if feature.jira_issue_key is None:
                    issue_key = await self.repository.create_jira_task_from_feature(feature)
                    if issue_key:
                        sync_results["created_jira_tasks"] += 1
                        feature = feature.copy(update={"jira_issue_key": issue_key})
                    else:
                        sync_results["errors"].append(
                            f"Failed to create Jira task for: {feature.task_title}",
                        )
                        return
                else:
                    issue_key = feature.jira_issue_key
                
                # Check if status allows Developer Board task creation
                if feature.status in [
                    StatusDescriptions.INITIATION_AND_PRIORITIZATION.value, 
                    StatusDescriptions.ANALYSIS_AND_RFP.value,
                    StatusDescriptions.USER_STORY_PREPARATION.value, 
                    StatusDescriptions.COMPLETED.value
                ]:
                    LOGGER.info(f"Skipping Developer Board task creation for {feature.task_title} - status is {feature.status}")
                    return
                
                # Create Developer Board task if doesn't exist and status allows
                if not feature.developer_board_issue_key:
                    # Repository will handle sprint selection from feature.sprint_list
                    if feature.sprint_list and len(feature.sprint_list) > 0:
                        assignees = self._extract_assignees_from_feature(feature)
                        developer_board_key = await self.repository.create_developer_board_task_from_feature(
                            feature,
                            assignees=assignees,
                        )
                        if developer_board_key:
                            feature = feature.copy(
                                update={
                                    "developer_board_issue_key": developer_board_key,
                                },
                            )
                            sync_results["created_developer_board_tasks"] = (
                                sync_results.get("created_developer_board_tasks", 0) + 1
                            )
                    else:
                        LOGGER.warning(f"No valid sprints found for feature {feature.task_title}, skipping Developer Board task creation")

            elif feature.jira_issue_key and feature.developer_board_issue_key:
                if feature.status in [StatusDescriptions.INITIATION_AND_PRIORITIZATION.value, StatusDescriptions.ANALYSIS_AND_RFP.value,
                                StatusDescriptions.USER_STORY_PREPARATION.value, StatusDescriptions.COMPLETED.value]:
                    return # TODO: update sync_result status
                success = await self.repository.update_jira_task_from_feature(feature)
                if success:
                    sync_results["updated_jira_tasks"] += 1
                elif success is False:
                    LOGGER.debug(f"No changes needed for PM board task {feature.jira_issue_key}")

                if feature.developer_board_issue_key:
                    assignees = self._extract_assignees_from_feature(feature)
                    developer_board_success = (
                        await self.repository.update_developer_board_task_from_feature(
                            feature,
                            feature_assignees=assignees,
                        )
                    )
                    if developer_board_success:
                        sync_results["updated_developer_board_tasks"] = (
                            sync_results.get("updated_developer_board_tasks", 0) + 1
                        )
            else:
                raise ValueError(
                    f"Feature {feature.task_title} has no Jira or Developer Board issue key",
                )

            # NO DIRECT TELEGRAM POSTING - Only for releases
            # Telegram notifications are now handled via sync_release_notes method

        except Exception as e:
            error_msg = f"Error processing feature '{feature.task_title}': {e}"
            LOGGER.error(error_msg)
            sync_results["errors"].append(error_msg)

    async def sync_release_notes(self) -> Dict[str, Any]:
        """Synchronize Release Notes and post to Telegram.

        Returns:
            Sync result summary
        """
        try:
            LOGGER.info("Starting Release Notes synchronization")

            release_notes = await self.repository.get_release_notes()
            features = await self.repository.get_developer_board_features()
            if not release_notes:
                return {"status": "success", "message": "No release notes found"}

            sync_results = {
                "posted_releases": 0,
                "updated_releases": 0,
                "enhanced_with_test_scenarios": 0,
                "errors": [],
            }

            for release in release_notes:
                try:
                    # First, enhance release note with test scenarios from related tasks
                    enhanced_description = await self._enhance_release_with_test_scenarios(release, features)
                    if enhanced_description != release.description:
                        # Update Google Sheets release note
                        await self.repository.update_release_note(
                            release.row_number,
                            {"description": enhanced_description}
                        )
                        
                        # Update Jira release in developer board project
                        await self.repository.update_jira_release(
                            project_key=self.settings.developer_board_project_key,
                            release_name=release.release_version,
                            description=enhanced_description,
                        )
                        
                        sync_results["enhanced_with_test_scenarios"] += 1
                        # Update the release object for further processing
                        release = release.copy(update={"description": enhanced_description})

                    if not release.telegram_message_id:
                        message_id = await self._post_release_to_telegram(release)
                        if message_id:
                            await self.repository.update_release_note(
                                release.row_number,
                                {
                                    "telegram_message_id": message_id,
                                    "last_updated": datetime.now(),
                                },
                            )
                            sync_results["posted_releases"] += 1
                    else:
                        should_update = await self._should_update_release(release)
                        if should_update:
                            success = await self._update_release_in_telegram(release)
                            if success:
                                sync_results["updated_releases"] += 1

                except Exception as e:
                    error_msg = (
                        f"Error processing release {release.release_version}: {e}"
                    )
                    LOGGER.error(error_msg)
                    sync_results["errors"].append(error_msg)

            LOGGER.info(f"Release Notes sync completed: {sync_results}")
            return {
                "status": "success",
                "message": "Release Notes sync completed",
                "results": sync_results,
            }

        except Exception as e:
            error_msg = f"Error during Release Notes sync: {e}"
            LOGGER.error(error_msg)
            return {"status": "error", "message": error_msg}

    async def _post_release_to_telegram(
        self,
        release: ReleaseNoteEntity,
    ) -> Optional[str]:
        """Post release note to Telegram and return message ID.

        Args:
            release: Release note entity

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            message = self._format_release_message(release)

            sent_message_id = await self.notification_gateway.send_message_async(
                chat_id=int(self.settings.telegram_channel_id),
                text=message,
                parse_mode="HTML",
            )

            if sent_message_id:
                LOGGER.info(f"Posted release {release.release_version} to Telegram")
                return sent_message_id
            else:
                LOGGER.error(
                    f"Failed to post release {release.release_version} to Telegram",
                )
                return None

        except Exception as e:
            LOGGER.error(f"Error posting release to Telegram: {e}")
            return None

    async def _update_release_in_telegram(self, release: ReleaseNoteEntity) -> bool:
        """Update existing release message in Telegram.

        Args:
            release: Release note entity

        Returns:
            True if successful, False otherwise
        """
        try:
            message = self._format_release_message(release)

            success = await self.notification_gateway.edit_message_text(
                chat_id=int(self.settings.telegram_channel_id),
                message_id=int(release.telegram_message_id),
                text=message,
                parse_mode="Markdown",
            )

            if success:
                await self.repository.update_release_note(
                    release.row_number,
                    {"last_updated": datetime.now()},
                )

                LOGGER.info(f"Updated release {release.release_version} in Telegram")
                return True
            else:
                LOGGER.error(
                    f"Failed to update release {release.release_version} in Telegram",
                )
                return False

        except Exception as e:
            LOGGER.error(f"Error updating release in Telegram: {e}")
            return False

    async def _enhance_release_with_test_scenarios(self, release: ReleaseNoteEntity, features: List[SynthPMFeatureEntity]) -> str:
        """Enhance release note description with test scenarios from related developer board tasks.

        Args:
            release: Release note entity

        Returns:
            Enhanced description with test scenarios appended
        """
        try:
            LOGGER.info(f"Enhancing release {release.release_version} with test scenarios")

            # Get all features from developer board
            if not features:
                LOGGER.warning("No developer board features found")
                return release.description

            # Filter features that belong to this release and have test scenarios
            related_features = []
            for feature in features:
                if (feature.release and 
                    feature.release.strip() == release.release_version.strip() and
                    feature.test_cases and 
                    feature.test_cases.strip()):
                    related_features.append(feature)

            if not related_features:
                LOGGER.info(f"No features with test scenarios found for release {release.release_version}")
                return release.description

            LOGGER.info(f"Found {len(related_features)} features with test scenarios for release {release.release_version}")

            # Collect and format test scenarios
            test_scenarios_section = self._format_release_test_scenarios(related_features)
            
            # If test scenarios already exist in description, don't add again
            if "سناریوهای تست" in release.description or "Test Scenarios" in release.description:
                LOGGER.info(f"Test scenarios already exist in release {release.release_version} description")
                return release.description

            # Append test scenarios to the original description
            enhanced_description = f"{release.description}\n\n{test_scenarios_section}"
            
            LOGGER.info(f"Enhanced release {release.release_version} with {len(related_features)} task test scenarios")
            return enhanced_description

        except Exception as e:
            LOGGER.error(f"Error enhancing release {release.release_version} with test scenarios: {e}")
            return release.description

    def _format_release_test_scenarios(self, features: List[SynthPMFeatureEntity]) -> str:
        """Format test scenarios from features for release note.

        Args:
            features: List of features with test scenarios

        Returns:
            Formatted test scenarios section
        """
        test_scenarios_parts = [
            "## سناریوهای تست (Test Scenarios)",
            "",
            "سناریوهای تست مربوط به وظایف این ریلیز:",
            ""
        ]

        for feature in features:
            if feature.test_cases and feature.test_cases.strip():
                test_scenarios_parts.extend([
                    f"### {feature.task_title}",
                    ""
                ])
                
                # Split test cases by lines and format them
                test_lines = feature.test_cases.strip().split('\n')
                for line in test_lines:
                    line = line.strip()
                    if line:
                        # Add bullet point if not already present
                        if not line.startswith('•') and not line.startswith('-') and not line.startswith('*'):
                            line = f"• {line}"
                        test_scenarios_parts.append(line)
                
                test_scenarios_parts.append("")  # Add space between features

        return "\n".join(test_scenarios_parts)

    def _format_release_message(self, release: ReleaseNoteEntity) -> str:
        """Format release note for Telegram message.

        Args:
            release: Release note entity

        Returns:
            Formatted Telegram message
        """
        message_parts = [
            "🚀 **نسخه جدید منتشر شد!**",
            "",
            f"📋 **نسخه:** {release.release_version}",
            f"🔧 **اجزای ریلیز:** {release.release_components}",
            "",
            "📝 **شرح:**",
            release.description,
        ]

        if release.goals:
            message_parts.extend(
                [
                    "",
                    "🎯 **اهداف:**",
                    release.goals,
                ],
            )

        if release.delivery_process:
            message_parts.extend(
                [
                    "",
                    "📦 **فرایند تحویل:**",
                    release.delivery_process,
                ],
            )

        if release.test_process:
            message_parts.extend(
                [
                    "",
                    "🧪 **فرایند تست:**",
                    release.test_process,
                ],
            )

        release_hashtag = (
            f"#{release.release_version.replace(' ', '_').replace('.', '_')}"
        )
        message_parts.extend(
            [
                "",
                f"🏷️ {release_hashtag} #Release",
            ],
        )

        return "\n".join(message_parts)

    async def _should_update_release(self, release: ReleaseNoteEntity) -> bool:
        """Check if release note should be updated in Telegram.

        Args:
            release: Release note entity

        Returns:
            True if should update, False otherwise
        """
        # For now, assume we should update if last_updated is None
        # In the future, you could compare with sheet modification time
        return release.last_updated is None

    def _should_post_to_telegram(self, feature: SynthPMFeatureEntity) -> bool:
        """Determine if a feature update should be posted to Telegram.

        Args:
            feature: feature entity

        Returns:
            True if should post, False otherwise
        """
        project_config = self.repository.project_config
        if feature.status == project_config.sync_settings.status_trigger_value:
            return True

        important_statuses = ["۶", "۷", "۸"]
        if feature.status in important_statuses:
            return True

        # Post if deadline is set or changed (this would need tracking of previous state)
        # For now, we'll rely on status changes

        return False

    async def _post_to_telegram(self, feature: SynthPMFeatureEntity):
        """Post feature update to Telegram channel.

        Args:
            feature: feature entity
        """
        try:
            message = self._format_telegram_message(feature)

            # Get project-specific Telegram configuration
            project_config = self.repository.project_config
            channel_id = self.settings.telegram_channel_id

            # Post to channel using dedicated bot
            await self.notification_gateway.send_message_async(
                chat_id=int(channel_id),
                text=message,
                parse_mode="Markdown",
            )

            # Also post to group if different from channel
            if (
                self.settings.telegram_group_id
                and self.settings.telegram_group_id != self.settings.telegram_channel_id
            ):
                await self.notification_gateway.send_message_async(
                    chat_id=int(self.settings.telegram_group_id),
                    text=message,
                    parse_mode="Markdown",
                )

            LOGGER.info(f"Posted to Telegram: {feature.task_title}")

        except Exception as e:
            LOGGER.error(f"Error posting to Telegram: {e}")

    def _format_telegram_message(self, feature: SynthPMFeatureEntity) -> str:
        """Format feature information for Telegram message.

        Args:
            feature: feature entity

        Returns:
            Formatted Telegram message
        """
        hashtags = []
        if feature.epic:
            # Convert epic name to hashtag format
            epic_hashtag = f"#{feature.epic.replace(' ', '_').replace('-', '_')}"
            hashtags.append(epic_hashtag)

        message_parts = [
            "🚀 *Feature Update*",
            "",
            f"📝 *Task:* {feature.task_title}",
        ]

        if feature.epic:
            message_parts.append(f"📊 *Epic:* {feature.epic}")

        if feature.priority:
            priority_icon = self._get_priority_icon(feature.priority)
            message_parts.append(f"{priority_icon} *Priority:* {feature.priority}")

        if feature.status:
            status_icon = self._get_status_icon(feature.status)
            status_text = self._get_status_description(feature.status)
            message_parts.append(f"{status_icon} *Status:* {status_text}")

        if feature.eta_hours:
            message_parts.append(f"⏱️ *ETA:* {feature.eta_hours} hours")

        if feature.deadline:
            deadline_str = feature.deadline.strftime("%Y-%m-%d")
            message_parts.append(f"📅 *Deadline:* {deadline_str}")

        if feature.involved_people:
            message_parts.append(f"👥 *Team:* {feature.involved_people}")

        components = []
        if feature.ai:
            components.append(f"🤖 AI: {feature.ai}")
        if feature.backend:
            components.append(f"⚙️ Backend: {feature.backend}")
        if feature.frontend:
            components.append(f"🎨 Frontend: {feature.frontend}")
        if feature.devops:
            components.append(f"🔧 DevOps: {feature.devops}")
        if feature.ui_ux:
            components.append(f"🎯 UI/UX: {feature.ui_ux}")

        if components:
            message_parts.extend(["", "*Components:*"] + components)

        if feature.departments:
            message_parts.append(f"🏢 *Departments:* {feature.departments}")

        if feature.jira_issue_key:
            message_parts.append(f"🔗 *Jira:* {feature.jira_issue_key}")

        if feature.description:
            message_parts.extend(
                [
                    "",
                    "📄 *Description:*",
                    feature.description,
                ],
            )

        # Add hashtags at the end
        if hashtags:
            message_parts.extend(["", " ".join(hashtags)])

        return "\n".join(message_parts)

    def _get_priority_icon(self, priority: str) -> str:
        """Get icon for priority level."""
        priority_icons = {
            "Highest": "🔴",
            "High": "🟠",
            "Medium": "🟡",
            "Low": "🟢",
            "بالاترین": "🔴",
            "بالا": "🟠",
            "متوسط": "🟡",
            "پایین": "🟢",
        }
        return priority_icons.get(priority, "⚡")

    def _get_status_icon(self, status: str) -> str:
        """Get icon for status."""
        status_icons = {
            "۵": "📋",  # آماده پیاده سازی فنی
            "۶": "⚡",  # در حال پیاده سازی
            "۴": "🎨",  # در مرحله طراحی (UI/UX)
            "۷": "🔍",  # در مرحله تست فنی
            "۸": "✅",  # آماده تحویل
            # Legacy
            "۱": "📝",
            "۲": "⚡",
            "۳": "✅",
        }
        return status_icons.get(status, "📈")

    def _get_status_description(self, status: str) -> str:
        """Get human readable status description."""
        status_descriptions = {
            "۵": "آماده پیاده سازی فنی",
            "۶": "در حال پیاده سازی",
            "۴": "در مرحله طراحی",
            "۷": "در مرحله تست فنی",
            "۸": "آماده تحویل",
            # Legacy
            "۱": "To Do",
            "۲": "In Progress",
            "۳": "Done",
        }
        return status_descriptions.get(status, status)

    async def handle_jira_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, str]:
        """Handle Jira webhook events for features.

        Args:
            webhook_data: Jira webhook data

        Returns:
            Processing result
        """
        try:
            issue_key = webhook_data.get("issue", {}).get("key")
            if not issue_key:
                return {"status": "ignored", "reason": "No issue key found"}

            # Check if this is a feature issue
            if not issue_key.startswith(self.settings.jira_project_key):
                return {"status": "ignored", "reason": "Not a project issue"}

            # Get the feature from sheet
            features = await self.repository.get_developer_board_features()
            feature = next(
                (f for f in features if f.jira_issue_key == issue_key),
                None,
            )

            if not feature:
                return {"status": "ignored", "reason": "Feature not found in sheet"}

            # Handle different event types
            event_type = webhook_data.get("issue_event_type_name")

            if event_type == "issue_updated":
                await self._handle_jira_issue_updated(feature, webhook_data)
                return {"status": "success", "message": "Feature updated from Jira"}

            return {
                "status": "ignored",
                "reason": f"Unhandled event type: {event_type}",
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
        """Handle Jira issue update events.

        Args:
            feature: feature entity
            webhook_data: Jira webhook data
        """
        try:
            issue_data = webhook_data.get("issue", {})
            fields = issue_data.get("fields", {})

            # Prepare updates for the sheet
            updates = {}

            # Update status if changed
            status = fields.get("status", {}).get("name")
            if status:
                # Map Jira status to sheet status using reverse mapping
                reverse_status_mapping = self.repository.get_reverse_status_mapping()

                sheet_status = reverse_status_mapping.get(status)
                if sheet_status and sheet_status != feature.status:
                    updates["status"] = sheet_status

            # Update summary if changed
            summary = fields.get("summary")
            if summary and summary != feature.task_title:
                updates["task_title"] = summary

            # Update description if changed
            description = fields.get("description")
            if description and description != feature.description:
                updates["description"] = description

            # Update due date if changed
            due_date = fields.get("duedate")
            if due_date:
                try:
                    due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")
                    if due_date_obj != feature.deadline:
                        updates["deadline"] = due_date
                except ValueError:
                    pass

            # Apply updates to sheet
            if updates:
                success = await self.repository.update_developer_board_feature(
                    feature.row_number,
                    updates,
                )

                if success:
                    LOGGER.info(
                        f"Updated sheet for Jira issue {feature.jira_issue_key}",
                    )

                    # Create updated feature for checking if we should post
                    updated_feature = feature.copy(update=updates)

                    # Post to Telegram if status/deadline changed and meets criteria
                    if self._should_post_to_telegram(updated_feature):
                        await self._post_to_telegram(updated_feature)

        except Exception as e:
            LOGGER.error(
                f"Error handling Jira issue update for {feature.jira_issue_key}: {e}",
            )

    async def handle_sheet_update(
        self,
        row_number: int,
        updates: Dict[str, Any],
    ) -> Dict[str, str]:
        """Handle manual updates to Google Sheets.

        Args:
            row_number: Row number that was updated
            updates: Dictionary of updated fields

        Returns:
            Processing result
        """
        try:
            # Get the updated feature
            features = await self.repository.get_developer_board_features()
            feature = next(
                (f for f in features if f.row_number == row_number),
                None,
            )

            if not feature:
                return {"status": "error", "message": "Feature not found"}

            # Initialize sync results to track what happens
            sync_results = {
                "created_jira_tasks": 0,
                "updated_jira_tasks": 0,
                "created_developer_board_tasks": 0,
                "updated_developer_board_tasks": 0,
                "deleted_tasks": 0,
                "errors": [],
            }

            # Use the comprehensive _process_feature logic
            await self._process_feature(feature, sync_results)

            # Generate and update documentation for the feature
            doc_update_result = await self.update_feature_with_documentation(feature)
            if doc_update_result["status"] == "success":
                actions_taken.append("Generated and updated documentation")
            elif doc_update_result["status"] == "error":
                sync_results["errors"].append(f"Documentation generation failed: {doc_update_result.get('message', 'Unknown error')}")

            # Check if status change triggers Telegram post
            if self._should_post_to_telegram(feature):
                await self._post_to_telegram(feature)

            # Build response message based on what was processed
            actions_taken = []
            if sync_results["created_jira_tasks"] > 0:
                actions_taken.append(f"Created {sync_results['created_jira_tasks']} Jira task(s)")
            if sync_results["updated_jira_tasks"] > 0:
                actions_taken.append(f"Updated {sync_results['updated_jira_tasks']} Jira task(s)")
            if sync_results["created_developer_board_tasks"] > 0:
                actions_taken.append(f"Created {sync_results['created_developer_board_tasks']} Developer Board task(s)")
            if sync_results["updated_developer_board_tasks"] > 0:
                actions_taken.append(f"Updated {sync_results['updated_developer_board_tasks']} Developer Board task(s)")

            if sync_results["errors"]:
                return {
                    "status": "partial_success",
                    "message": f"Sheet update completed with errors: {'; '.join(sync_results['errors'])}",
                    "actions_taken": actions_taken,
                }

            message = "Sheet update processed successfully"
            if actions_taken:
                message += f". Actions: {'; '.join(actions_taken)}"

            return {
                "status": "success",
                "message": message,
                "actions_taken": actions_taken,
            }

        except Exception as e:
            error_msg = f"Error handling sheet update: {e}"
            LOGGER.error(error_msg)
            return {"status": "error", "message": error_msg}

    async def generate_feature_documentation(
        self,
        feature: SynthPMFeatureEntity,
        project_info: Dict[str, Any],
    ) -> Dict[str, str]:
        """Generate user story, acceptance criteria, and test scenarios for a feature.

        Only generates documentation if the feature has at least one of:
        - description
        - acceptance_criteria 
        - test_cases

        Args:
            feature: SynthPM feature entity
            project_info: Project information from projects_info.json

        Returns:
            Dictionary containing generated documentation
        """
        try:
            LOGGER.info(f"Generating documentation for feature: {feature.task_title}")

            # Check if feature has any content that warrants documentation generation
            has_description = bool(feature.description and feature.description.strip())
            has_acceptance_criteria = bool(feature.acceptance_criteria and feature.acceptance_criteria.strip())
            has_test_cases = bool(feature.test_cases and feature.test_cases.strip())

            if not (has_description or has_acceptance_criteria or has_test_cases):
                LOGGER.info(f"Skipping documentation generation for {feature.task_title} - no description, acceptance criteria, or test cases found")
                return {
                    "status": "skipped",
                    "message": "No content available for documentation generation",
                }

            # Prepare project context
            project_context = ""
            if project_info:
                project_context = f"توضیحات پروژه: {project_info.get('description', '')}\n"
                project_context += f"کلید واژه‌ها: {', '.join(project_info.get('keywords', []))}"

            # Generate acceptance criteria first
            acceptance_input = GenerateAcceptanceCriteriaInput(
                task_title=feature.task_title,
                task_description=f"توضیحات اولیه:\n{feature.description}\nمعیار پذیرش:\n{feature.acceptance_criteria}\nسناریوهای تست:\n{feature.test_cases}",
                epic_name=feature.epic,
                related_departments=feature.departments.split(",") if feature.departments else [],
                project_info=project_context,
                special_requirements=None,
            )

            acceptance_result = await self.generate_acceptance_criteria_use_case.execute(
                input_data=acceptance_input,
                robot_id="synth_pm_system",
            )

            # Generate test scenarios using the acceptance criteria
            test_input = GenerateTestScenariosInput(
                task_title=feature.task_title,
                task_description=f"توضیحات اولیه:\n{feature.description}\nمعیار پذیرش:\n{feature.acceptance_criteria}\nسناریوهای تست:\n{feature.test_cases}",
                user_story=acceptance_result.user_story,
                acceptance_criteria=acceptance_result.acceptance_criteria,
                epic_name=feature.epic,
                related_departments=feature.departments.split(",") if feature.departments else [],
                project_info=project_context,
            )

            test_result = await self.generate_test_scenarios_use_case.execute(
                input_data=test_input,
                robot_id="synth_pm_system",
            )

            # Format the complete documentation
            documentation = self._format_feature_documentation(
                acceptance_result,
                test_result,
            )

            LOGGER.info(f"Successfully generated documentation for: {feature.developer_board_issue_key}:{feature.task_title}")
            return {
                "status": "success",
                "documentation": documentation,
                "user_story": acceptance_result.user_story,
                "acceptance_criteria": acceptance_result.acceptance_criteria,
                "delivery_process": acceptance_result.delivery_process,
                "test_scenarios": [scenario.dict() for scenario in test_result.test_scenarios],
            }

        except Exception as e:
            error_msg = f"Error generating documentation for {feature.task_title}: {e}"
            LOGGER.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
            }

    def _format_feature_documentation(
        self,
        acceptance_result,
        test_result,
    ) -> str:
        """Format the generated documentation with proper Jira markup following comprehensive structure.

        Args:
            acceptance_result: Generated acceptance criteria result
            test_result: Generated test scenarios result

        Returns:
            Formatted documentation text with Jira markup
        """
        documentation_parts = []

        # Short Description section
        documentation_parts.append("h2. توضیح کوتاه")
        documentation_parts.append("")
        documentation_parts.append(acceptance_result.user_story)
        documentation_parts.append("----")

        # Scope and Domain section  
        documentation_parts.append("h2. دامنه و محدوده")
        documentation_parts.append("")
        # Add basic scope points - these could be enhanced based on acceptance criteria
        documentation_parts.extend([
            " * *ورودی کاربر:* اطلاعات مطابق نیازمندی‌های سیستم",
            " * *منبع داده:* منابع تعریف شده در سیستم",
            " * *خروجی به کاربر:* نتیجه عملیات مطابق انتظارات",
            "",
            "----"
        ])

        # Assumptions and Dependencies
        documentation_parts.append("h2. مفروضات و وابستگی‌ها")
        documentation_parts.append("")
        documentation_parts.extend([
            " * وجود دسترسی‌های لازم به سیستم‌های مرتبط",
            " * رعایت معماری و استانداردهای تعریف شده",
            " * وجود زیرساخت‌های مورد نیاز",
            "",
            "----"
        ])

        # Acceptance Criteria section
        documentation_parts.append("h2. معیارهای پذیرش (Acceptance Criteria)")
        documentation_parts.append("")
        
        # Group acceptance criteria by scenarios
        for i, criteria in enumerate(acceptance_result.acceptance_criteria, 1):
            documentation_parts.append(f"h3. سناریو {i}")
            documentation_parts.append(f" * {criteria}")
            documentation_parts.append("")
        
        documentation_parts.append("----")

        # Delivery Process section
        documentation_parts.append("h2. فرایند تحویل (Delivery Process)")
        
        for i, step in enumerate(acceptance_result.delivery_process, 1):
            documentation_parts.append(f" # *مرحله {i}*")
            documentation_parts.append("")
            documentation_parts.append(f" * {step}")
            documentation_parts.append("")
        
        documentation_parts.append("----")

        # Non-functional Requirements
        documentation_parts.append("h2. معیارهای غیرعملکردی")
        documentation_parts.extend([
            " * *کارایی:* پاسخ سیستم در زمان مناسب",
            " * *پایداری:* عملکرد مطمئن و قابل اعتماد",
            " * *امنیت:* رعایت اصول امنیتی و حریم خصوصی",
            " * *قابلیت ردیابی:* امکان پیگیری و نظارت",
            "",
            "----"
        ])

        # Definition of Done
        documentation_parts.append("h2. تعریف Done")
        documentation_parts.extend([
            " * کد نوشته شده و بررسی شده",
            " * تست‌های واحد و یکپارچگی انجام شده",
            " * مستندات به‌روزرسانی شده",
            " * بررسی کیفیت کد انجام شده",
            " * تست‌های پذیرش تأیید شده",
            "",
            "----"
        ])

        # Test Scenarios section
        documentation_parts.append("h2. روش تست (Test Scenarios)")
        documentation_parts.append("")
        documentation_parts.append("||شماره تست||توضیح روش تست||وضعیت||مسئول||")

        for scenario in test_result.test_scenarios:
            documentation_parts.append(
                f"|{scenario.test_number}|{scenario.description}|⬜|{scenario.responsible}|"
            )

        return "\n".join(documentation_parts)

    async def update_feature_with_documentation(
        self,
        feature: SynthPMFeatureEntity,
        update_description_field: bool = True,
    ) -> Dict[str, Any]:
        """Update a feature with generated documentation in Jira and Google Sheets.

        Args:
            feature: SynthPM feature entity
            update_description_field: Whether to update description field or add new fields

        Returns:
            Update result summary
        """
        try:
            LOGGER.info(f"Updating feature documentation for: {feature.task_title}")

            # Get project info for context
            project_info = await self.repository.get_project_info(
                self.settings.pm_project_key
            )

            # Generate documentation
            doc_result = await self.generate_feature_documentation(feature, project_info)
            
            if doc_result["status"] != "success":
                return doc_result

            documentation = doc_result["documentation"]

            # Update in Jira if task exists
            if feature.developer_board_issue_key:
                if update_description_field:
                    # Update description field with complete documentation
                    await self.repository.update_jira_task_description(
                        feature.developer_board_issue_key,
                        documentation,
                    )
                else:
                    # Add as separate custom fields (if supported)
                    await self.repository.update_jira_task_custom_fields(
                        feature.developer_board_issue_key,
                        {
                            "user_story": doc_result["user_story"],
                            "acceptance_criteria": "\n".join(doc_result["acceptance_criteria"]),
                            "test_scenarios": self._format_test_scenarios_for_jira(
                                doc_result["test_scenarios"]
                            ),
                        },
                    )
            # TODO: no need to update description field in google sheet. 
            # TODO: later on, update a google doc for these info. 
            # Update in Google Sheets (add new columns)
            # sheet_updates = {
            #     "توضیحات": documentation,
            #     "معیارهای پذیرش": "\n".join(doc_result["acceptance_criteria"]),
            #     "تست ها": self._format_test_scenarios_for_sheets(
            #         doc_result["test_scenarios"]
            #     ),
            # }

            # await self.repository.update_developer_board_feature(
            #     feature.row_number,
            #     sheet_updates,
            # )

            LOGGER.info(f"Successfully updated documentation for: {feature.task_title}")
            return {
                "status": "success",
                "message": f"Documentation updated for {feature.task_title}",
                "updated_fields": list("description"),
            }

        except Exception as e:
            error_msg = f"Error updating documentation for {feature.task_title}: {e}"
            LOGGER.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
            }

    async def _generate_and_update_documentation(self, feature: SynthPMFeatureEntity) -> bool:
        """Generate and update documentation for a single feature.

        Only generates documentation if feature has content (description, acceptance_criteria, or test_cases).
        Updates only Jira task, not Google Sheets.

        Args:
            feature: The feature to generate documentation for

        Returns:
            True if successful or skipped, False if failed
        """
        try:
            LOGGER.info(f"Generating documentation for feature: {feature.task_title}")

            # Get project info for context
            project_info = await self.repository.get_project_info(
                self.settings.developer_board_project_key
            )

            # Generate the documentation
            doc_result = await self.generate_feature_documentation(feature, project_info)
            
            if doc_result["status"] == "skipped":
                LOGGER.info(f"Documentation generation skipped for feature: {feature.task_title}")
                return True  # Skipped is considered successful for change tracking
            
            if doc_result["status"] != "success":
                LOGGER.warning(f"Failed to generate documentation for feature: {feature.task_title}")
                return False

            # Update only Jira task with the new documentation (not Google Sheets)
            if feature.developer_board_issue_key:
                try:
                    documentation = doc_result["documentation"]  # Already formatted by generate_feature_documentation
                    
                    await self.repository.update_jira_task_description(
                        feature.developer_board_issue_key,
                        documentation,
                    )
                    
                    LOGGER.info(f"Successfully updated Jira task {feature.developer_board_issue_key} with documentation")
                    
                except Exception as e:
                    LOGGER.error(f"Error updating Jira task {feature.developer_board_issue_key}: {e}")
                    return False
            else:
                LOGGER.warning(f"No Jira issue key found for feature: {feature.task_title}")

            return True

        except Exception as e:
            LOGGER.error(f"Error generating documentation for feature {feature.task_title}: {e}")
            return False

    async def force_documentation_regeneration(self, sheet_row_numbers: List[int]) -> bool:
        """Force documentation regeneration for specific sheet rows.

        Args:
            sheet_row_numbers: List of sheet row numbers to regenerate docs for

        Returns:
            True if successful, False otherwise
        """
        try:
            LOGGER.info(f"Forcing documentation regeneration for rows: {sheet_row_numbers}")

            # Update change tracker to force regeneration
            success = await self.repository.force_documentation_regeneration(sheet_row_numbers)
            if success:
                LOGGER.info("Documentation regeneration flags set successfully")
            else:
                LOGGER.error("Failed to set documentation regeneration flags")

            return success

        except Exception as e:
            LOGGER.error(f"Error forcing documentation regeneration: {e}")
            return False

    def _format_test_scenarios_for_jira(self, test_scenarios: List[Dict]) -> str:
        """Format test scenarios for Jira custom field."""
        lines = []
        for scenario in test_scenarios:
            lines.append(
                f"{scenario['test_number']}: {scenario['description']} "
                f"[{scenario['responsible']}]"
            )
        return "\n".join(lines)

    def _format_test_scenarios_for_sheets(self, test_scenarios: List[Dict]) -> str:
        """Format test scenarios for Google Sheets cell."""
        lines = []
        for scenario in test_scenarios:
            lines.append(
                f"• {scenario['test_number']}: {scenario['description']} ({scenario['responsible']})"
            )
        return "\n".join(lines)
