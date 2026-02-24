"""Unit tests for Jira-to-Sheet status sync in SynthPMRepository."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

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
        "status": "۵. آماده پیاده سازی فنی",
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

    project_metadata = MagicMock()
    project_metadata.status_mapping.jira_to_google_sheet = {
        "BACKLOG": "۱. ثبت و اولویت بندی",
        "IN PROGRESS": "۶. در حال پیاده سازی",
        "REVIEW": "۷. تست فنی",
        "RESOLVED": "۸. آماده تحویل",
        "DONE": "۹. مستندسازی فنی",
        "CLOSED": "۱۰. تکمیل شده",
        "REOPENED": "۵. آماده پیاده سازی فنی",
    }

    settings.get_project_config = MagicMock(return_value=project_config)
    settings.get_project_metadata = MagicMock(return_value=project_metadata)
    jira_repository.get_board_id = MagicMock(return_value=123)

    repository = SynthPMRepository(
        google_sheet_client=google_sheet_client,
        jira_repository=jira_repository,
        settings=settings,
        user_config=user_config,
    )
    return repository, jira_repository


class TestSyncJiraStatusToSheet(unittest.IsolatedAsyncioTestCase):
    """Tests for sync_jira_status_to_sheet repository method."""

    def setUp(self):
        """Set up test fixtures."""
        self.repository, self.jira_repo = _build_repository()
        self.repository.update_developer_board_feature = AsyncMock(return_value=True)

    async def test_updates_sheet_when_status_differs(self):
        """Write mapped status to sheet when Jira status changed."""
        feature = create_test_feature(
            status="۵. آماده پیاده سازی فنی",
        )

        issue = MagicMock()
        issue.fields.status.name = "In Progress"
        self.jira_repo.get_issue = MagicMock(return_value=issue)

        result = await self.repository.sync_jira_status_to_sheet(feature)

        self.assertTrue(result)
        self.repository.update_developer_board_feature.assert_awaited_once_with(
            feature.sheet_row_number,
            {"status": "۶. در حال پیاده سازی"},
        )

    async def test_skips_when_status_matches(self):
        """Do not update sheet when mapped status is the same."""
        feature = create_test_feature(
            status="۶. در حال پیاده سازی",
        )

        issue = MagicMock()
        issue.fields.status.name = "In Progress"
        self.jira_repo.get_issue = MagicMock(return_value=issue)

        result = await self.repository.sync_jira_status_to_sheet(feature)

        self.assertFalse(result)
        self.repository.update_developer_board_feature.assert_not_awaited()

    async def test_skips_when_no_developer_board_issue_key(self):
        """Return False when feature has no developer board issue key."""
        feature = create_test_feature(developer_board_issue_key=None)

        result = await self.repository.sync_jira_status_to_sheet(feature)

        self.assertFalse(result)
        self.jira_repo.get_issue.assert_not_called()

    async def test_skips_when_jira_issue_not_found(self):
        """Return False when Jira issue cannot be retrieved."""
        feature = create_test_feature()
        self.jira_repo.get_issue = MagicMock(return_value=None)

        result = await self.repository.sync_jira_status_to_sheet(feature)

        self.assertFalse(result)
        self.repository.update_developer_board_feature.assert_not_awaited()

    async def test_skips_when_jira_status_has_no_mapping(self):
        """Return False when Jira status has no sheet mapping."""
        feature = create_test_feature()

        issue = MagicMock()
        issue.fields.status.name = "Unknown Custom Status"
        self.jira_repo.get_issue = MagicMock(return_value=issue)

        result = await self.repository.sync_jira_status_to_sheet(feature)

        self.assertFalse(result)
        self.repository.update_developer_board_feature.assert_not_awaited()

    async def test_skips_when_status_name_is_none(self):
        """Return False when issue status name attribute is None."""
        feature = create_test_feature()

        issue = MagicMock()
        issue.fields.status.name = None
        self.jira_repo.get_issue = MagicMock(return_value=issue)

        result = await self.repository.sync_jira_status_to_sheet(feature)

        self.assertFalse(result)

    async def test_handles_exception_gracefully(self):
        """Return False and log when an exception occurs."""
        feature = create_test_feature()
        self.jira_repo.get_issue = MagicMock(side_effect=Exception("API error"))

        result = await self.repository.sync_jira_status_to_sheet(feature)

        self.assertFalse(result)

    async def test_case_insensitive_mapping(self):
        """Map Jira status using upper-case normalisation."""
        feature = create_test_feature(
            status="۵. آماده پیاده سازی فنی",
        )

        issue = MagicMock()
        issue.fields.status.name = "Resolved"
        self.jira_repo.get_issue = MagicMock(return_value=issue)

        result = await self.repository.sync_jira_status_to_sheet(feature)

        self.assertTrue(result)
        self.repository.update_developer_board_feature.assert_awaited_once_with(
            feature.sheet_row_number,
            {"status": "۸. آماده تحویل"},
        )


if __name__ == "__main__":
    unittest.main()
