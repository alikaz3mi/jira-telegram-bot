"""Tests for SynthPM helper methods and utilities."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from datetime import datetime

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


def create_test_feature(**overrides) -> SynthPMFeatureEntity:
    """Factory function to create test feature with defaults."""
    defaults = {
        "row_number": 1,
        "sheet_row_number": 2,
        "task_title": "Test Feature",
        "status": "۵. آماده پیاده سازی فنی",
        "involved_people": "User1",
        "sprint_list": ["45: 1403/09/01 - 1403/09/14"],
        "ai": "✓",
        "implementation_start_date": "2024-01-01",
        "story_name": "Version 2.5.0",
    }
    defaults.update(overrides)
    return SynthPMFeatureEntity(**defaults)


class TestSynthPMHelperMethods(unittest.IsolatedAsyncioTestCase):
    """Test helper methods in SynthPM use case."""

    def setUp(self):
        """Set up test fixtures."""
        self.repository = MagicMock()
        self.settings = MagicMock()
        self.user_config = MagicMock()
        self.notification_gateway = MagicMock()
        self.generate_acceptance_criteria_use_case = MagicMock()
        self.generate_test_scenarios_use_case = MagicMock()
        
        self.project_config = MagicMock()
        self.project_config.sync_settings.minimum_status_for_task_creation = "۵. آماده پیاده سازی فنی"
        self.repository.project_config = self.project_config
        
        self.use_case = SynthPMUseCase(
            repository=self.repository,
            settings=self.settings,
            user_config=self.user_config,
            notification_gateway=self.notification_gateway,
            generate_acceptance_criteria_use_case=self.generate_acceptance_criteria_use_case,
            generate_test_scenarios_use_case=self.generate_test_scenarios_use_case,
        )

    def test_group_features_by_release_empty_list(self):
        """Test grouping with empty feature list."""
        features = []
        groups = self.use_case._group_features_by_release(features)
        self.assertEqual(len(groups), 0)

    def test_group_features_by_release_all_same(self):
        """Test grouping when all features have same story_name."""
        features = [
            create_test_feature(row_number=i, story_name="Version 1.0")
            for i in range(1, 6)
        ]
        groups = self.use_case._group_features_by_release(features)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups["Version 1.0"]), 5)

    def test_group_features_by_release_multiple_releases(self):
        """Test grouping with multiple story names."""
        features = [
            create_test_feature(row_number=1, story_name="Version 1.0"),
            create_test_feature(row_number=2, story_name="Version 1.0"),
            create_test_feature(row_number=3, story_name="Version 2.0"),
            create_test_feature(row_number=4, story_name="Version 2.0"),
            create_test_feature(row_number=5, story_name="Version 3.0"),
        ]
        groups = self.use_case._group_features_by_release(features)
        self.assertEqual(len(groups), 3)
        self.assertEqual(len(groups["Version 1.0"]), 2)
        self.assertEqual(len(groups["Version 2.0"]), 2)
        self.assertEqual(len(groups["Version 3.0"]), 1)

    def test_group_features_by_release_no_release(self):
        """Test grouping with features without story_name."""
        features = [
            create_test_feature(row_number=1, story_name=""),
            create_test_feature(row_number=2, story_name=None),
            create_test_feature(row_number=3, story_name="  "),
        ]
        groups = self.use_case._group_features_by_release(features)
        self.assertEqual(len(groups), 1)
        self.assertIn("No Release", groups)
        self.assertEqual(len(groups["No Release"]), 3)

    def test_group_features_by_release_mixed(self):
        """Test grouping with mixed story names and no story names."""
        features = [
            create_test_feature(row_number=1, story_name="Version 1.0"),
            create_test_feature(row_number=2, story_name=""),
            create_test_feature(row_number=3, story_name="Version 1.0"),
            create_test_feature(row_number=4, story_name=None),
        ]
        groups = self.use_case._group_features_by_release(features)
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups["Version 1.0"]), 2)
        self.assertEqual(len(groups["No Release"]), 2)

    async def test_create_regular_tasks_for_features_empty(self):
        """Test creating regular tasks with empty list."""
        sync_results = {
            "created_developer_board_tasks": 0,
            "errors": [],
        }
        await self.use_case._create_regular_tasks_for_features([], sync_results)
        self.assertEqual(sync_results["created_developer_board_tasks"], 0)

    async def test_create_regular_tasks_for_features_no_release(self):
        """Test creating regular tasks for features without release."""
        features = [
            create_test_feature(row_number=1, jira_issue_key="PM-101", story_name=""),
            create_test_feature(row_number=2, jira_issue_key="PM-102", story_name=""),
        ]
        sync_results = {
            "created_developer_board_tasks": 0,
            "created_jira_tasks": 0,
            "errors": [],
        }
        
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        self.repository.create_developer_board_task_from_feature = AsyncMock(
            side_effect=["DEV-101", "DEV-102"]
        )
        self.user_config.get_all_user_configs.return_value = {}
        
        await self.use_case._create_regular_tasks_for_features(features, sync_results)
        
        self.assertEqual(sync_results["created_developer_board_tasks"], 2)

    async def test_create_regular_tasks_skips_existing(self):
        """Test that existing regular tasks are updated."""
        features = [
            create_test_feature(
                row_number=1,
                jira_issue_key="PM-101",
                developer_board_issue_key="DEV-101",
                story_name="",
            ),
        ]
        sync_results = {
            "updated_developer_board_tasks": 0,
            "created_developer_board_tasks": 0,
            "errors": [],
        }
        
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        self.repository.update_developer_board_task_from_feature = AsyncMock(return_value=True)
        self.user_config.get_all_user_configs.return_value = {}
        
        await self.use_case._create_regular_tasks_for_features(features, sync_results)
        
        self.assertEqual(sync_results["updated_developer_board_tasks"], 1)
        self.assertEqual(sync_results["created_developer_board_tasks"], 0)



    async def test_cleanup_deleted_tasks_no_previous_sync(self):
        """Test cleanup when no previous sync exists."""
        features = [create_test_feature()]
        sync_results = {"deleted_tasks": 0, "errors": []}
        
        self.repository.get_sync_status = AsyncMock(return_value=None)
        
        await self.use_case._cleanup_deleted_tasks(features, sync_results)
        
        # Should return early
        self.assertEqual(len(sync_results["errors"]), 0)

    async def test_cleanup_deleted_tasks_with_previous_sync(self):
        """Test cleanup logs current task counts."""
        features = [
            create_test_feature(
                row_number=1,
                jira_issue_key="PM-101",
                developer_board_issue_key="DEV-101",
            ),
        ]
        sync_results = {"deleted_tasks": 0, "errors": []}
        
        self.repository.get_sync_status = AsyncMock(return_value={"last_sync": "2024-01-01"})
        
        await self.use_case._cleanup_deleted_tasks(features, sync_results)
        
        # Should log counts
        self.assertEqual(len(sync_results["errors"]), 0)

    def test_get_priority_icon_high(self):
        """Test getting icon for high priority."""
        result = self.use_case._get_priority_icon("High")
        self.assertEqual(result, "🟠")

    def test_get_priority_icon_medium(self):
        """Test getting icon for medium priority."""
        result = self.use_case._get_priority_icon("Medium")
        self.assertEqual(result, "🟡")

    def test_get_priority_icon_low(self):
        """Test getting icon for low priority."""
        result = self.use_case._get_priority_icon("Low")
        self.assertEqual(result, "🟢")

    def test_get_priority_icon_unknown(self):
        """Test getting icon for unknown priority."""
        result = self.use_case._get_priority_icon("Unknown")
        self.assertEqual(result, "⚡")

    def test_get_status_icon_ready(self):
        """Test getting icon for ready status."""
        result = self.use_case._get_status_icon("۵. آماده پیاده سازی فنی")
        self.assertIsNotNone(result)

    def test_get_status_icon_in_progress(self):
        """Test getting icon for in progress status."""
        result = self.use_case._get_status_icon("۶. در حال پیاده سازی")
        self.assertIsNotNone(result)

    def test_get_status_icon_done(self):
        """Test getting icon for done status."""
        result = self.use_case._get_status_icon("۹. تکمیل شده")
        self.assertIsNotNone(result)

    def test_get_status_icon_unknown(self):
        """Test getting icon for unknown status."""
        result = self.use_case._get_status_icon("Unknown Status")
        self.assertEqual(result, "📈")

    def test_get_status_description_ready(self):
        """Test getting description for ready status."""
        result = self.use_case._get_status_description("۵")
        self.assertEqual(result, "آماده پیاده سازی فنی")

    def test_get_status_description_in_progress(self):
        """Test getting description for in progress status - legacy."""
        result = self.use_case._get_status_description("۲")
        self.assertEqual(result, "In Progress")

    def test_get_status_description_unknown(self):
        """Test getting description for unknown status."""
        result = self.use_case._get_status_description("Unknown Status")
        self.assertEqual(result, "Unknown Status")


if __name__ == "__main__":
    unittest.main()
