"""Unit tests for _sync_jira_statuses_to_sheet use case helper."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


def create_test_feature(**overrides) -> SynthPMFeatureEntity:
    """Factory function to create a test feature with defaults.

    Args:
        **overrides: Field overrides for the feature.

    Returns:
        A SynthPMFeatureEntity instance.
    """
    defaults = {
        "row_number": 1,
        "sheet_row_number": 2,
        "task_title": "Test Feature",
        "status": "۵. آماده پیاده سازی فنی",
        "involved_people": "User1",
        "sprint_list": ["45: 11-15: 11-28"],
        "ai": "✓",
        "release": "Version 1.0",
        "developer_board_issue_key": "DEV-100",
    }
    defaults.update(overrides)
    return SynthPMFeatureEntity(**defaults)


def _build_use_case() -> tuple:
    """Build a SynthPMUseCase with mocked dependencies.

    Returns:
        Tuple of (use_case, repository_mock).
    """
    repository = MagicMock()
    settings = MagicMock()
    user_config = MagicMock()
    notification_gateway = MagicMock()
    generate_acceptance_criteria_use_case = MagicMock()
    generate_test_scenarios_use_case = MagicMock()

    project_config = MagicMock()
    project_config.sync_settings.minimum_status_for_task_creation = "۵. آماده پیاده سازی فنی"
    repository.project_config = project_config

    use_case = SynthPMUseCase(
        repository=repository,
        settings=settings,
        user_config=user_config,
        notification_gateway=notification_gateway,
        generate_acceptance_criteria_use_case=generate_acceptance_criteria_use_case,
        generate_test_scenarios_use_case=generate_test_scenarios_use_case,
    )
    return use_case, repository


class TestSyncJiraStatusesToSheet(unittest.IsolatedAsyncioTestCase):
    """Tests for _sync_jira_statuses_to_sheet use case helper."""

    def setUp(self):
        """Set up test fixtures."""
        self.use_case, self.repository = _build_use_case()

    async def test_syncs_statuses_for_features_with_issue_key(self):
        """Call repository for each feature that has a developer_board_issue_key."""
        features = [
            create_test_feature(row_number=1, developer_board_issue_key="DEV-1"),
            create_test_feature(row_number=2, developer_board_issue_key="DEV-2"),
        ]
        self.repository.sync_jira_status_to_sheet = AsyncMock(return_value=True)
        sync_results = {"synced_statuses": 0}

        await self.use_case._sync_jira_statuses_to_sheet(features, sync_results)

        self.assertEqual(self.repository.sync_jira_status_to_sheet.await_count, 2)
        self.assertEqual(sync_results["synced_statuses"], 2)

    async def test_skips_features_without_issue_key(self):
        """Do not call repository when feature has no developer_board_issue_key."""
        features = [
            create_test_feature(row_number=1, developer_board_issue_key=None),
            create_test_feature(row_number=2, developer_board_issue_key="DEV-2"),
        ]
        self.repository.sync_jira_status_to_sheet = AsyncMock(return_value=True)
        sync_results = {"synced_statuses": 0}

        await self.use_case._sync_jira_statuses_to_sheet(features, sync_results)

        self.assertEqual(self.repository.sync_jira_status_to_sheet.await_count, 1)
        self.assertEqual(sync_results["synced_statuses"], 1)

    async def test_counts_only_actual_updates(self):
        """Only count features that were actually updated."""
        features = [
            create_test_feature(row_number=1, developer_board_issue_key="DEV-1"),
            create_test_feature(row_number=2, developer_board_issue_key="DEV-2"),
            create_test_feature(row_number=3, developer_board_issue_key="DEV-3"),
        ]
        self.repository.sync_jira_status_to_sheet = AsyncMock(
            side_effect=[True, False, True],
        )
        sync_results = {"synced_statuses": 0}

        await self.use_case._sync_jira_statuses_to_sheet(features, sync_results)

        self.assertEqual(sync_results["synced_statuses"], 2)

    async def test_handles_exception_per_feature(self):
        """Continue processing remaining features when one raises an exception."""
        features = [
            create_test_feature(row_number=1, developer_board_issue_key="DEV-1"),
            create_test_feature(row_number=2, developer_board_issue_key="DEV-2"),
        ]
        self.repository.sync_jira_status_to_sheet = AsyncMock(
            side_effect=[Exception("API error"), True],
        )
        sync_results = {"synced_statuses": 0}

        await self.use_case._sync_jira_statuses_to_sheet(features, sync_results)

        self.assertEqual(sync_results["synced_statuses"], 1)

    async def test_empty_feature_list(self):
        """Handle empty feature list without errors."""
        self.repository.sync_jira_status_to_sheet = AsyncMock()
        sync_results = {"synced_statuses": 0}

        await self.use_case._sync_jira_statuses_to_sheet([], sync_results)

        self.repository.sync_jira_status_to_sheet.assert_not_awaited()
        self.assertEqual(sync_results["synced_statuses"], 0)


if __name__ == "__main__":
    unittest.main()
