"""Use case for synchronizing release notes."""
from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.synth_pm.google_sheets_adapter import (
    SynthPMGoogleSheetsAdapter,
)
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.interfaces.notification_gateway_interface import (
    NotificationGatewayInterface,
)


class SyncReleaseNotesUseCase:
    """Use case for synchronizing release notes."""

    def __init__(
        self,
        google_sheets_adapter: SynthPMGoogleSheetsAdapter,
        notification_gateway: NotificationGatewayInterface,
    ):
        """Initialize the use case.

        Args:
            google_sheets_adapter: Google Sheets adapter
            notification_gateway: Notification gateway interface
        """
        self.google_sheets_adapter = google_sheets_adapter
        self.notification_gateway = notification_gateway

    async def sync_release_notes(self) -> Dict[str, Any]:
        """Synchronize Release Notes and post to Telegram.

        Returns:
            Sync result summary
        """
        try:
            LOGGER.info("Starting release notes synchronization")

            release_notes = await self.google_sheets_adapter.get_release_notes()

            sync_results = {
                "total_releases": len(release_notes),
                "posted_to_telegram": 0,
                "updated_in_telegram": 0,
                "errors": [],
            }

            for release in release_notes:
                try:
                    await self._process_release_note(release, sync_results)
                except Exception as e:
                    error_msg = (
                        f"Error processing release {release.release_version}: {e}"
                    )
                    LOGGER.error(error_msg)
                    sync_results["errors"].append(error_msg)

            LOGGER.info(f"Release notes synchronization completed: {sync_results}")
            return sync_results

        except Exception as e:
            error_msg = f"Error during release notes synchronization: {e}"
            LOGGER.error(error_msg)
            return {"error": error_msg}

    async def _process_release_note(
        self,
        release: ReleaseNoteEntity,
        sync_results: Dict[str, Any],
    ):
        """Process a single release note.

        Args:
            release: Release note entity
            sync_results: Dictionary to track sync results
        """
        try:
            if not release.telegram_message_id:
                # Post new release to Telegram
                message_id = await self._post_release_to_telegram(release)
                if message_id:
                    # Update Google Sheet with message ID
                    await self.google_sheets_adapter.update_release_note(
                        release.row_number,
                        {"telegram_message_id": message_id},
                    )
                    sync_results["posted_to_telegram"] += 1
            else:
                # Check if release should be updated
                if await self._should_update_release(release):
                    success = await self._update_release_in_telegram(release)
                    if success:
                        sync_results["updated_in_telegram"] += 1

        except Exception as e:
            LOGGER.error(
                f"Error processing release note {release.release_version}: {e}",
            )
            raise

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
            # Get related features for test scenarios
            features = await self.google_sheets_adapter.get_developer_board_features()
            related_features = self._get_features_for_release(features, release)

            # Enhance release description with test scenarios
            enhanced_description = await self._enhance_release_with_test_scenarios(
                release,
                related_features,
            )

            # Format message for Telegram
            message = self._format_release_message(release, enhanced_description)

            # Post to Telegram
            response = await self.notification_gateway.send_message(message)

            if response and hasattr(response, "message_id"):
                LOGGER.info(f"Posted release {release.release_version} to Telegram")
                return str(response.message_id)

            return None

        except Exception as e:
            LOGGER.error(
                f"Error posting release {release.release_version} to Telegram: {e}",
            )
            return None

    async def _update_release_in_telegram(self, release: ReleaseNoteEntity) -> bool:
        """Update existing release message in Telegram.

        Args:
            release: Release note entity

        Returns:
            True if successful, False otherwise
        """
        try:
            if not release.telegram_message_id:
                return False

            # Get related features for updated test scenarios
            features = await self.google_sheets_adapter.get_developer_board_features()
            related_features = self._get_features_for_release(features, release)

            # Enhance release description with test scenarios
            enhanced_description = await self._enhance_release_with_test_scenarios(
                release,
                related_features,
            )

            # Format updated message
            message = self._format_release_message(release, enhanced_description)

            # Update message in Telegram
            success = await self.notification_gateway.edit_message(
                release.telegram_message_id,
                message,
            )

            if success:
                LOGGER.info(f"Updated release {release.release_version} in Telegram")

            return success

        except Exception as e:
            LOGGER.error(
                f"Error updating release {release.release_version} in Telegram: {e}",
            )
            return False

    async def _should_update_release(self, release: ReleaseNoteEntity) -> bool:
        """Check if release note should be updated in Telegram.

        Args:
            release: Release note entity

        Returns:
            True if should update, False otherwise
        """
        # For now, always return False to avoid unnecessary updates
        # This could be enhanced with change detection logic
        return False

    async def _enhance_release_with_test_scenarios(
        self,
        release: ReleaseNoteEntity,
        features: List[SynthPMFeatureEntity],
    ) -> str:
        """Enhance release note description with test scenarios.

        Args:
            release: Release note entity
            features: Related features

        Returns:
            Enhanced description
        """
        try:
            if not features:
                return release.description

            test_scenarios_section = self._format_release_test_scenarios(features)
            return f"{release.description}\n\n{test_scenarios_section}"

        except Exception as e:
            LOGGER.error(f"Error enhancing release with test scenarios: {e}")
            return release.description

    def _format_release_test_scenarios(
        self,
        features: List[SynthPMFeatureEntity],
    ) -> str:
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
            "",
        ]

        for feature in features:
            if feature.test_cases:
                test_scenarios_parts.extend(
                    [
                        f"### {feature.task_title}",
                        feature.test_cases,
                        "",
                    ],
                )

        return "\n".join(test_scenarios_parts)

    def _format_release_message(
        self,
        release: ReleaseNoteEntity,
        enhanced_description: str,
    ) -> str:
        """Format release note for Telegram message.

        Args:
            release: Release note entity
            enhanced_description: Enhanced description with test scenarios

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
            enhanced_description,
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
                    "📦 **فرآیند تحویل:**",
                    release.delivery_process,
                ],
            )

        if release.test_process:
            message_parts.extend(
                [
                    "",
                    "🧪 **فرآیند تست:**",
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

    def _get_features_for_release(
        self,
        features: List[SynthPMFeatureEntity],
        release: ReleaseNoteEntity,
    ) -> List[SynthPMFeatureEntity]:
        """Get features related to a specific release.

        Args:
            features: All features
            release: Release note entity

        Returns:
            Features related to the release
        """
        related_features = []

        for feature in features:
            if (
                feature.release == release.release_version
                or feature.version == release.release_version
            ):
                related_features.append(feature)

        return related_features
