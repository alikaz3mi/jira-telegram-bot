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
                "deleted_tasks": 0,
                "generated_documentation": 0,
                "errors": [],
            }

            # Handle task cleanup - check for tasks that no longer exist in sheet
            await self._cleanup_deleted_tasks(features, sync_results)

            # Process features efficiently based on change detection
            processed_features = []
            doc_generated_rows = []

            # Process new and modified features
            for feature in new_features + modified_features:
                # Skip test rows
                # if feature.sheet_row_number not in [9, 10, 66, 67]:
                #     continue
                if feature.version != "04.06.14":
                    continue

                try:
                    await self._process_feature(feature, sync_results)
                    processed_features.append(feature)

                    # Generate documentation for new features
                    if feature in new_features and await self._generate_and_update_documentation(feature):
                        sync_results["generated_documentation"] += 1
                        doc_generated_rows.append(feature.sheet_row_number)

                except Exception as e:
                    error_msg = f"Error processing feature {feature.task_title}: {e}"
                    LOGGER.error(error_msg)
                    sync_results["errors"].append(error_msg)

            # Generate documentation for existing features that need it
            for feature in features_needing_docs:
                if feature not in new_features and feature.sheet_row_number not in [9, 10, 66, 67]:
                    try:
                        if await self._generate_and_update_documentation(feature):
                            sync_results["generated_documentation"] += 1
                            doc_generated_rows.append(feature.sheet_row_number)
                            processed_features.append(feature)
                    except Exception as e:
                        error_msg = f"Error generating docs for {feature.task_title}: {e}"
                        LOGGER.error(error_msg)
                        sync_results["errors"].append(error_msg)

            # Update change tracker
            await self.repository.update_change_tracker(
                processed_features=processed_features,
                generated_docs_for=doc_generated_rows,
            )

            # Update sync status
            sync_status = SynthPMSheetSyncStatus(
                sheet_id=self.settings.google_sheets_id,
                worksheet_name=self.settings.developer_board_worksheet_name,
                last_sync_time=datetime.now(),
                total_rows_synced=len(features),
                errors=sync_results["errors"],
            )

            await self.repository.update_sync_status(sync_status)

            LOGGER.info(f"SynthPM sync completed: {sync_results}")
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
        for user_config in all_user_configs.values():
            assignee = user_config.jira_username
            if user_config.google_sheet_name in feature.involved_people:
                assignees.append(assignee)

        return assignees

    async def _process_feature(
        self,
        feature: SynthPMFeatureEntity,
        sync_results: Dict[str, Any],
    ):
        """Process a single feature.

        Args:
            feature: feature entity
            sync_results: Dictionary to track sync results
        """  # TODO: creation of jira task in pm, in developer board conditional checking must become separated. 
        try:
            if not (
                feature.jira_issue_key
                and feature.task_title is not None
                and feature.developer_board_issue_key is not None
            ):  
                # if feature.last_sprint is None:
                #     return
                if feature.jira_issue_key is None:
                    issue_key = await self.repository.create_jira_task_from_feature(feature)
                else:
                    issue_key = feature.jira_issue_key
                if issue_key:
                    sync_results["created_jira_tasks"] += 1
                    feature = feature.copy(update={"jira_issue_key": issue_key})

                    sprint_info = SprintInfo.parse_sprint_string(feature.last_sprint)
                    if sprint_info and sprint_info.is_valid():
                        assignees = self._extract_assignees_from_feature(feature)
                        if feature.status in [StatusDescriptions.INITIATION_AND_PRIORITIZATION.value, StatusDescriptions.ANALYSIS_AND_RFP.value,
                                              StatusDescriptions.USER_STORY_PREPARATION.value, StatusDescriptions.COMPLETED.value]:
                            return # TODO: update sync_result status

                        developer_board_key = await self.repository.create_developer_board_task_from_feature(
                            feature,
                            sprint_info,
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
                    sync_results["errors"].append(
                        f"Failed to create Jira task for: {feature.task_title}",
                    )
                    return

            elif feature.jira_issue_key and feature.developer_board_issue_key:
                success = await self.repository.update_jira_task_from_feature(feature)
                if success:
                    sync_results["updated_jira_tasks"] += 1
                else:
                    sync_results["errors"].append(
                        f"Failed to update Jira task: {feature.jira_issue_key}",
                    )

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
                    enhanced_description = await self._enhance_release_with_test_scenarios(release)
                    if enhanced_description != release.description:
                        await self.repository.update_release_note(
                            release.row_number,
                            {"description": enhanced_description}
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

    async def _enhance_release_with_test_scenarios(self, release: ReleaseNoteEntity) -> str:
        """Enhance release note description with test scenarios from related developer board tasks.

        Args:
            release: Release note entity

        Returns:
            Enhanced description with test scenarios appended
        """
        try:
            LOGGER.info(f"Enhancing release {release.release_version} with test scenarios")

            # Get all features from developer board
            features = await self.repository.get_developer_board_features()
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
        if feature.status == self.settings.status_trigger_value:
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

            # Post to channel using dedicated bot
            await self.notification_gateway.send_message_async(
                chat_id=int(self.settings.telegram_channel_id),
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
