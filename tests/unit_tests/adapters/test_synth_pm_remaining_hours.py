"""Unit tests for remaining hours sync from Jira worklogs to Google Sheet."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
    SynthPMRepository,
)
from jira_telegram_bot.entities.synth_pm.pm_board_features import (
    SynthPMFeatureEntity,
)


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
        "status": "۵. آماده پیاده\u200cسازی فنی",
        "involved_people": "User1",
        "sprint_list": ["45: 11-15: 11-28"],
        "ai": "✓",
        "release": "Version 1.0",
        "developer_board_issue_key": "DEV-100",
    }
    defaults.update(overrides)
    return SynthPMFeatureEntity(**defaults)


def _build_repository() -> tuple:
    """Build a SynthPMRepository with mocked dependencies.

    Returns:
        Tuple of (repository, jira_repository_mock).
    """
    google_sheet_client = MagicMock()
    jira_repository = MagicMock()
    user_config = MagicMock()
    settings = MagicMock()

    project_config = MagicMock()
    project_config.project_key = "TEST"
    project_config.boards.developer_board.jira_board_key = "DEV"
    project_config.boards.pm_board.jira_board_key = "PM"
    project_config.boards.pm_board.enabled = True

    settings.get_project_config = MagicMock(return_value=project_config)
    settings.get_project_metadata = MagicMock(return_value=MagicMock())
    jira_repository.get_board_id = MagicMock(return_value=123)

    repository = SynthPMRepository(
        google_sheet_client=google_sheet_client,
        jira_repository=jira_repository,
        settings=settings,
        user_config=user_config,
    )
    return repository, jira_repository


class TestCalculateRemainingSeconds(unittest.TestCase):
    """Tests for _calculate_remaining_seconds helper."""

    def setUp(self):
        """Set up test fixtures."""
        self.repository, self.jira_repo = _build_repository()

    def test_task_with_remaining_estimate(self):
        """Return remainingEstimateSeconds for a Task issue."""
        issue = MagicMock()
        issue.fields.issuetype.name = "Task"
        issue.fields.subtasks = []
        issue.fields.timetracking.remainingEstimateSeconds = 7200

        result = self.repository._calculate_remaining_seconds(issue)

        self.assertEqual(result, 7200)

    def test_task_with_no_timetracking(self):
        """Return 0 when timetracking is None."""
        issue = MagicMock()
        issue.fields.issuetype.name = "Task"
        issue.fields.subtasks = []
        issue.fields.timetracking = None

        result = self.repository._calculate_remaining_seconds(issue)

        self.assertEqual(result, 0)

    def test_story_sums_subtask_remaining(self):
        """Sum remainingEstimateSeconds across all subtasks for a Story."""
        subtask_a = MagicMock()
        subtask_a.key = "DEV-201"
        subtask_b = MagicMock()
        subtask_b.key = "DEV-202"

        issue = MagicMock()
        issue.fields.issuetype.name = "Story"
        issue.fields.subtasks = [subtask_a, subtask_b]

        subtask_issue_a = MagicMock()
        subtask_issue_a.fields.timetracking.remainingEstimateSeconds = 3600
        subtask_issue_b = MagicMock()
        subtask_issue_b.fields.timetracking.remainingEstimateSeconds = 1800

        self.jira_repo.get_issue = MagicMock(
            side_effect=lambda key: {
                "DEV-201": subtask_issue_a,
                "DEV-202": subtask_issue_b,
            }[key],
        )

        result = self.repository._calculate_remaining_seconds(issue)

        self.assertEqual(result, 5400)

    def test_story_with_no_subtasks(self):
        """Return 0 for a Story with no subtasks and no timetracking."""
        issue = MagicMock()
        issue.fields.issuetype.name = "Story"
        issue.fields.subtasks = []
        issue.fields.timetracking = None

        result = self.repository._calculate_remaining_seconds(issue)

        self.assertEqual(result, 0)

    def test_story_subtask_with_null_timetracking(self):
        """Treat subtask with null timetracking as 0 remaining."""
        subtask = MagicMock()
        subtask.key = "DEV-301"

        issue = MagicMock()
        issue.fields.issuetype.name = "Story"
        issue.fields.subtasks = [subtask]

        subtask_issue = MagicMock()
        subtask_issue.fields.timetracking = None

        self.jira_repo.get_issue = MagicMock(return_value=subtask_issue)

        result = self.repository._calculate_remaining_seconds(issue)

        self.assertEqual(result, 0)


class TestSyncRemainingHoursToSheet(unittest.IsolatedAsyncioTestCase):
    """Tests for sync_remaining_hours_to_sheet repository method."""

    def setUp(self):
        """Set up test fixtures."""
        self.repository, self.jira_repo = _build_repository()

    async def test_skips_feature_without_issue_key(self):
        """Return False when feature has no developer_board_issue_key."""
        feature = create_test_feature(developer_board_issue_key=None)

        result = await self.repository.sync_remaining_hours_to_sheet(feature)

        self.assertFalse(result)

    async def test_skips_when_no_worklogs(self):
        """Return False when issue has no logged work."""
        feature = create_test_feature()
        issue = MagicMock()
        issue.fields.issuetype.name = "Task"
        issue.fields.timetracking.remainingEstimateSeconds = 14400

        self.jira_repo.get_issue = MagicMock(return_value=issue)
        self.jira_repo.get_issue_spent_time_in_seconds = MagicMock(return_value=0)

        result = await self.repository.sync_remaining_hours_to_sheet(feature)

        self.assertFalse(result)

    async def test_updates_sheet_with_remaining_hours(self):
        """Write remaining hours to sheet when worklogs exist."""
        feature = create_test_feature(sheet_row_number=5)
        issue = MagicMock()
        issue.fields.issuetype.name = "Task"
        issue.fields.subtasks = []
        issue.fields.timetracking.remainingEstimateSeconds = 7200

        self.jira_repo.get_issue = MagicMock(return_value=issue)
        self.jira_repo.get_issue_spent_time_in_seconds = MagicMock(return_value=3600)

        with patch.object(
            self.repository,
            "update_developer_board_feature",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_update:
            result = await self.repository.sync_remaining_hours_to_sheet(feature)

        self.assertTrue(result)
        mock_update.assert_awaited_once_with(5, {"remaining_hours": 2.0})

    async def test_updates_sheet_for_story_with_subtasks(self):
        """Sum subtask remaining and write to sheet for Story issues."""
        feature = create_test_feature(sheet_row_number=8)

        subtask = MagicMock()
        subtask.key = "DEV-201"

        issue = MagicMock()
        issue.fields.issuetype.name = "Story"
        issue.fields.subtasks = [subtask]

        subtask_issue = MagicMock()
        subtask_issue.fields.timetracking.remainingEstimateSeconds = 10800

        self.jira_repo.get_issue = MagicMock(
            side_effect=lambda key: {
                "DEV-100": issue,
                "DEV-201": subtask_issue,
            }[key],
        )
        self.jira_repo.get_issue_spent_time_in_seconds = MagicMock(return_value=1800)

        with patch.object(
            self.repository,
            "update_developer_board_feature",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_update:
            result = await self.repository.sync_remaining_hours_to_sheet(feature)

        self.assertTrue(result)
        mock_update.assert_awaited_once_with(8, {"remaining_hours": 3.0})

    async def test_handles_jira_error_gracefully(self):
        """Return False and log error when Jira API fails."""
        feature = create_test_feature()

        self.jira_repo.get_issue = MagicMock(
            side_effect=Exception("Connection timeout"),
        )

        result = await self.repository.sync_remaining_hours_to_sheet(feature)

        self.assertFalse(result)

    async def test_returns_false_when_issue_not_found(self):
        """Return False when Jira issue is not found."""
        feature = create_test_feature()
        self.jira_repo.get_issue = MagicMock(return_value=None)

        result = await self.repository.sync_remaining_hours_to_sheet(feature)

        self.assertFalse(result)


class TestSyncRemainingHoursUseCase(unittest.IsolatedAsyncioTestCase):
    """Tests for _sync_remaining_hours in the use case."""

    def setUp(self):
        """Set up test fixtures."""
        from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase

        self.repository = MagicMock()
        self.repository.sync_remaining_hours_to_sheet = AsyncMock()

        self.use_case = SynthPMUseCase(
            repository=self.repository,
            settings=MagicMock(),
            user_config=MagicMock(),
            notification_gateway=MagicMock(),
            generate_acceptance_criteria_use_case=MagicMock(),
            generate_test_scenarios_use_case=MagicMock(),
        )

    async def test_syncs_features_with_issue_keys(self):
        """Call sync_remaining_hours_to_sheet for features with issue keys."""
        features = [
            create_test_feature(developer_board_issue_key="DEV-10"),
            create_test_feature(developer_board_issue_key=None),
            create_test_feature(developer_board_issue_key="DEV-20"),
        ]
        self.repository.sync_remaining_hours_to_sheet.return_value = True
        sync_results = {"errors": []}

        await self.use_case._sync_remaining_hours(features, sync_results)

        self.assertEqual(
            self.repository.sync_remaining_hours_to_sheet.await_count,
            2,
        )

    async def test_handles_individual_feature_error(self):
        """Continue syncing when one feature fails."""
        features = [
            create_test_feature(developer_board_issue_key="DEV-10"),
            create_test_feature(developer_board_issue_key="DEV-20"),
        ]
        self.repository.sync_remaining_hours_to_sheet.side_effect = [
            Exception("fail"),
            True,
        ]
        sync_results = {"errors": []}

        await self.use_case._sync_remaining_hours(features, sync_results)

        self.assertEqual(
            self.repository.sync_remaining_hours_to_sheet.await_count,
            2,
        )

    async def test_a_skips_all_when_no_issue_keys(self):
        """Do nothing when no features have issue keys."""
        features = [
            create_test_feature(developer_board_issue_key=None),
            create_test_feature(developer_board_issue_key=None),
        ]
        sync_results = {"errors": []}

        await self.use_case._sync_remaining_hours(features, sync_results)

        self.repository.sync_remaining_hours_to_sheet.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
