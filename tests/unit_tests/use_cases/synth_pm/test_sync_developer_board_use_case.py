"""Tests for SyncDeveloperBoardUseCase."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.synth_pm.sync_developer_board_use_case import (
    SyncDeveloperBoardUseCase,
)


class TestSyncDeveloperBoardUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for SyncDeveloperBoardUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.google_sheets_adapter = MagicMock()
        self.jira_adapter = MagicMock()
        self.user_config = MagicMock()

        self.use_case = SyncDeveloperBoardUseCase(
            self.google_sheets_adapter,
            self.jira_adapter,
            self.user_config,
        )

    def test_extract_assignees_from_feature(self):
        """Test extracting assignees from feature."""
        # Mock user config
        user_config_mock = MagicMock()
        user_config_mock.jira_username = "john.doe"
        user_config_mock.google_sheet_name = "John Doe"

        self.user_config.get_all_user_configs.return_value = {
            "john": user_config_mock,
        }

        # Create feature with times
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Task",
            times={"John Doe": 8},
        )

        assignees = self.use_case._extract_assignees_from_feature(feature)

        self.assertEqual(len(assignees), 1)
        self.assertEqual(assignees[0], "john.doe")

    def test_should_create_developer_task(self):
        """Test determining if developer task should be created."""
        # Feature ready for implementation
        feature_ready = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Task",
            status="۵",  # Ready for technical implementation
        )

        self.assertTrue(self.use_case._should_create_developer_task(feature_ready))

        # Feature not ready for implementation
        feature_not_ready = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Task",
            status="۱",  # Initial status
        )

        self.assertFalse(self.use_case._should_create_developer_task(feature_not_ready))

    async def test_sync_features_success(self):
        """Test successful feature synchronization."""
        # Mock data
        features = [
            SynthPMFeatureEntity(
                row_number=1,
                sheet_row_number=2,
                task_title="Test Task 1",
                status="۵",
                times={"John Doe": 8},
            ),
            SynthPMFeatureEntity(
                row_number=2,
                sheet_row_number=3,
                task_title="Test Task 2",
                jira_issue_key="TEST-123",
                status="۶",
            ),
        ]

        # Mock adapter methods
        self.google_sheets_adapter.get_developer_board_features = AsyncMock(
            return_value=features,
        )
        self.jira_adapter.create_pm_board_task = AsyncMock(return_value="TEST-124")
        self.jira_adapter.update_pm_board_task = AsyncMock(return_value=True)
        self.google_sheets_adapter.update_developer_board_feature = AsyncMock(
            return_value=True,
        )

        # Mock user config
        user_config_mock = MagicMock()
        user_config_mock.jira_username = "john.doe"
        user_config_mock.google_sheet_name = "John Doe"
        self.user_config.get_all_user_configs.return_value = {"john": user_config_mock}

        # Execute
        result = await self.use_case.sync_features()

        # Verify
        self.assertEqual(result["total_features"], 2)
        self.assertEqual(result["created_pm_tasks"], 1)
        self.assertEqual(result["updated_pm_tasks"], 1)
        self.assertEqual(len(result["errors"]), 0)

    async def test_sync_features_with_errors(self):
        """Test feature synchronization with errors."""
        # Mock data
        features = [
            SynthPMFeatureEntity(
                row_number=1,
                sheet_row_number=2,
                task_title="Test Task 1",
            ),
        ]

        # Mock adapter methods to raise exception
        self.google_sheets_adapter.get_developer_board_features = AsyncMock(
            return_value=features,
        )
        self.jira_adapter.create_pm_board_task = AsyncMock(
            side_effect=Exception("Test error"),
        )

        # Execute
        result = await self.use_case.sync_features()

        # Verify
        self.assertEqual(result["total_features"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("Test error", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
