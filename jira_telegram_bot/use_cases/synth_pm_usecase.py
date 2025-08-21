"""SynthPM use case for managing bidirectional synchronization."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.release_notes import SprintInfo
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMSheetSyncStatus
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


class SynthPMUseCase:
    """Use case for managing SynthPM feature synchronization."""

    def __init__(
        self,
        repository: SynthPMRepositoryInterface,
        settings: SynthPMSettings,
        user_config: UserConfigInterface,
        notification_gateway: NotificationGatewayInterface,
    ):
        """Initialize the use case.

        Args:
            repository: SynthPM repository interface
            settings: SynthPM settings
            user_config: User configuration interface
            notification_gateway: Notification gateway interface
        """
        self.repository = repository
        self.settings = settings
        self.user_config = user_config
        self.notification_gateway = notification_gateway

    async def sync_developer_board_features(self) -> Dict[str, Any]:
        """Synchronize features between Google Sheets, Jira, and Telegram.

        Returns:
            Sync result summary
        """
        try:
            LOGGER.info("Starting SynthPM synchronization")

            # Get current features from sheet
            # FIXME: departments must be list of string.
            # FIXME: names must not be mapped in here. it should be from a db or something
            features = await self.repository.get_developer_board_features()
            if not features:
                return {"status": "success", "message": "No features found to sync"}

            # Get previous sync status
            # previous_sync = await self.repository.get_sync_status()

            sync_results = {
                "created_jira_tasks": 0,
                "updated_jira_tasks": 0,
                "created_developer_board_tasks": 0,
                "updated_developer_board_tasks": 0,
                "deleted_tasks": 0,
                "errors": [],
            }

            # Handle task cleanup - check for tasks that no longer exist in sheet
            await self._cleanup_deleted_tasks(
                features,
                sync_results,
            )  # TODO: check this one later

            for idx, feature in enumerate(features):
                LOGGER.info(
                    f"Processing feature {idx + 1}/{len(features)}: {feature.task_title}",
                )
                try:
                    await self._process_feature(feature, sync_results)
                except Exception as e:
                    error_msg = f"Error processing feature {feature.task_title}: {e}"
                    LOGGER.error(error_msg)
                    sync_results["errors"].append(error_msg)

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

        # Get all user configurations
        all_user_configs = self.user_config.get_all_user_configs()

        # Create mapping from google_sheet_name to jira_username
        google_sheet_to_jira = {}
        for _, user_cfg in all_user_configs.items():
            if (
                hasattr(user_cfg, "google_sheet_name")
                and hasattr(user_cfg, "jira_username")
                and user_cfg.google_sheet_name
                and user_cfg.jira_username
            ):
                google_sheet_to_jira[
                    user_cfg.google_sheet_name.lower()
                ] = user_cfg.jira_username

        # Get all feature attributes that might contain people assignments
        # This will dynamically check all attributes of the feature
        feature_dict = feature.dict() if hasattr(feature, "dict") else feature.__dict__

        # Check each feature attribute for assignment
        for attr_name, value in feature_dict.items():
            # Skip non-people fields
            if attr_name in [
                "task_title",
                "description",
                "epic",
                "priority",
                "status",
                "deadline",
                "eta_hours",
                "departments",
                "involved_people",
                "jira_issue_key",
                "developer_board_issue_key",
                "row_number",
                "sprint",
            ]:
                continue

            if value and str(value).strip() and str(value).strip() != "Select":
                # If column has a value (hours or assignment), find corresponding user
                if (
                    str(value).strip().replace(".", "").isdigit()
                    or ":" in str(value)
                    or any(
                        keyword in str(value).lower()
                        for keyword in ["hour", "h", "ساعت"]
                    )
                ):
                    # This attribute has hour assignment, try to find matching user
                    # Look for google_sheet_name that might match this attribute
                    for (
                        google_sheet_name,
                        jira_username,
                    ) in google_sheet_to_jira.items():
                        # Check if the google_sheet_name might correspond to this attribute
                        # This is a fuzzy match to handle variations
                        sheet_name_clean = google_sheet_name.replace(" ", "").lower()
                        attr_name_clean = attr_name.replace("_", "").lower()

                        # Try various matching strategies
                        if (
                            sheet_name_clean in attr_name_clean
                            or attr_name_clean in sheet_name_clean
                            or self._names_are_similar(
                                attr_name_clean,
                                sheet_name_clean,
                            )
                        ):
                            assignees.append(jira_username)
                            LOGGER.info(
                                f"Matched attribute '{attr_name}' with user '{google_sheet_name}' -> '{jira_username}'",
                            )
                            break

        # Fallback: use involved_people field if no specific people are assigned
        if not assignees and feature.involved_people:
            # Parse involved_people field for names
            involved = feature.involved_people.split(",")
            for person in involved:
                person = person.strip()
                # Try to find matching google_sheet_name
                for google_sheet_name, jira_username in google_sheet_to_jira.items():
                    if (
                        person.lower() in google_sheet_name.lower()
                        or google_sheet_name.lower() in person.lower()
                    ):
                        assignees.append(jira_username)
                        break

        LOGGER.info(
            f"Extracted assignees for feature '{feature.task_title}': {assignees}",
        )
        return list(set(assignees))  # Remove duplicates

    def _names_are_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar (basic fuzzy matching).

        Args:
            name1: First name to compare
            name2: Second name to compare

        Returns:
            True if names are considered similar
        """
        # Remove common variations and check for similarity
        name1_variants = [name1, name1.replace("dr_", ""), name1.replace("_", "")]
        name2_variants = [name2, name2.replace("dr_", ""), name2.replace("_", "")]

        for n1 in name1_variants:
            for n2 in name2_variants:
                if n1 == n2 or n1 in n2 or n2 in n1:
                    return True

        return False

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
            # Always create PM Board task if needed
            if not (feature.jira_issue_key and feature.task_title is not None):  # 
                if feature.last_sprint is None:
                    return
                issue_key = await self.repository.create_jira_task_from_feature(feature)
                if issue_key:
                    sync_results["created_jira_tasks"] += 1
                    feature = feature.copy(update={"jira_issue_key": issue_key})

                    sprint_info = SprintInfo.parse_sprint_string(feature.last_sprint)
                    if sprint_info and sprint_info.is_valid():
                        assignees = self._extract_assignees_from_feature(feature)

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

            # Check if existing Jira task needs updating
            elif feature.jira_issue_key:
                success = await self.repository.update_jira_task_from_feature(feature)
                if success:
                    sync_results["updated_jira_tasks"] += 1
                else:
                    sync_results["errors"].append(
                        f"Failed to update Jira task: {feature.jira_issue_key}",
                    )

                if feature.developer_board_issue_key:
                    # Update assignees based on current feature data
                    assignees = self._extract_assignees_from_feature(feature)
                    developer_board_success = (
                        await self.repository.update_developer_board_task_from_feature(
                            feature,
                            assignees=assignees,
                        )
                    )
                    if developer_board_success:
                        sync_results["updated_developer_board_tasks"] = (
                            sync_results.get("updated_developer_board_tasks", 0) + 1
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

            # Get release notes from the Release Notes sheet
            release_notes = await self.repository.get_release_notes()
            if not release_notes:
                return {"status": "success", "message": "No release notes found"}

            sync_results = {
                "posted_releases": 0,
                "updated_releases": 0,
                "errors": [],
            }

            for release in release_notes:
                try:
                    # Check if this release needs to be posted or updated
                    if not release.telegram_message_id:
                        # New release - post to Telegram
                        message_id = await self._post_release_to_telegram(release)
                        if message_id:
                            # Update the sheet with message ID for tracking
                            await self.repository.update_release_note(
                                release.row_number,
                                {
                                    "telegram_message_id": message_id,
                                    "last_updated": datetime.now(),
                                },
                            )
                            sync_results["posted_releases"] += 1
                    else:
                        # Existing release - check if needs updating
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
                parse_mode="Markdown",
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
                # Update last_updated timestamp
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

        # Add release hashtag
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
        # Post on status change to trigger value
        if feature.status == self.settings.status_trigger_value:
            return True

        # Post on specific status changes that indicate progress
        important_statuses = ["۶", "۷", "۸"]  # در حال پیاده سازی, تست فنی, آماده تحویل
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
        # Start with epic hashtag if available
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

        # Show component assignments
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

            # If feature has Jira issue, update it
            if feature.jira_issue_key:
                success = await self.repository.update_jira_task_from_feature(feature)
                if not success:
                    return {"status": "error", "message": "Failed to update Jira task"}

            # Check if status change triggers Telegram post
            if self._should_post_to_telegram(feature):
                await self._post_to_telegram(feature)

            return {
                "status": "success",
                "message": "Sheet update processed successfully",
            }

        except Exception as e:
            error_msg = f"Error handling sheet update: {e}"
            LOGGER.error(error_msg)
            return {"status": "error", "message": error_msg}
