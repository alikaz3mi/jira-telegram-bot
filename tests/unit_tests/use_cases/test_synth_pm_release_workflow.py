"""Unit tests for release-based workflow in SynthPM."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

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


class TestReleaseBasedWorkflow(unittest.IsolatedAsyncioTestCase):
    """Test release-based workflow functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mocks
        self.repository = MagicMock()
        self.settings = MagicMock()
        self.user_config = MagicMock()
        self.notification_gateway = MagicMock()
        self.generate_acceptance_criteria_use_case = MagicMock()
        self.generate_test_scenarios_use_case = MagicMock()
        
        # Setup project config
        self.project_config = MagicMock()
        self.project_config.sync_settings.minimum_status_for_task_creation = (
            "۵. آماده پیاده سازی فنی"
        )
        self.repository.project_config = self.project_config
        
        # Default async mocks for repository methods used across tests
        self.repository.convert_existing_task_to_subtask = AsyncMock(return_value="DEV-KEY")
        self.repository.update_story_from_subtasks = AsyncMock(return_value=True)
        self.repository.update_release_note = AsyncMock(return_value=True)
        self.repository.link_story_dependencies = AsyncMock(return_value=None)
        self.repository.validate_feature_for_update = MagicMock(return_value=(True, None))
        self.repository.jira_repository = MagicMock()
        self.repository.jira_repository.get_issue = MagicMock(return_value=None)
        
        # Create use case
        self.use_case = SynthPMUseCase(
            repository=self.repository,
            settings=self.settings,
            user_config=self.user_config,
            notification_gateway=self.notification_gateway,
            generate_acceptance_criteria_use_case=self.generate_acceptance_criteria_use_case,
            generate_test_scenarios_use_case=self.generate_test_scenarios_use_case,
        )

    def test_group_features_by_release(self):
        """Test grouping features by story_name column."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                story_name="04.12.01",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                story_name="04.12.01",
            ),
            create_test_feature(
                row_number=3,
                task_title="Feature C",
                story_name="04.12.02",
            ),
            create_test_feature(
                row_number=4,
                task_title="Feature D",
                story_name=None,
            ),
        ]
        
        release_groups = self.use_case._group_features_by_release(features)
        
        # Check groups
        self.assertEqual(len(release_groups), 3)
        self.assertIn("04.12.01", release_groups)
        self.assertIn("04.12.02", release_groups)
        self.assertIn("No Release", release_groups)
        
        # Check group contents
        self.assertEqual(len(release_groups["04.12.01"]), 2)
        self.assertEqual(len(release_groups["04.12.02"]), 1)
        self.assertEqual(len(release_groups["No Release"]), 1)
        
        # Check feature titles
        self.assertEqual(release_groups["04.12.01"][0].task_title, "Feature A")
        self.assertEqual(release_groups["04.12.01"][1].task_title, "Feature B")
        self.assertEqual(release_groups["04.12.02"][0].task_title, "Feature C")
        self.assertEqual(release_groups["No Release"][0].task_title, "Feature D")

    def test_group_features_by_release_all_same(self):
        """Test grouping when all features have same story_name."""
        features = [
            create_test_feature(row_number=i, story_name="04.12.01")
            for i in range(5)
        ]
        
        release_groups = self.use_case._group_features_by_release(features)
        
        self.assertEqual(len(release_groups), 1)
        self.assertIn("04.12.01", release_groups)
        self.assertEqual(len(release_groups["04.12.01"]), 5)

    def test_group_features_by_release_empty_list(self):
        """Test grouping with empty feature list."""
        release_groups = self.use_case._group_features_by_release([])
        
        self.assertEqual(len(release_groups), 0)
        self.assertIsInstance(release_groups, dict)

    async def test_create_release_story_with_subtasks_success(self):
        """Test successful creation of release story with subtasks."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                story_name="Version 2.5.0",
                jira_issue_key="PM-101",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                story_name="Version 2.5.0",
                jira_issue_key="PM-102",
            ),
        ]
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock story creation
        self.repository.get_story_by_release_name = AsyncMock(return_value=None)
        self.repository.create_release_story = AsyncMock(return_value="DEV-100")
        
        # Mock subtask creation
        self.repository.create_subtask_for_release = AsyncMock(
            side_effect=["DEV-101", "DEV-102"]
        )
        
        # Mock user config for assignees
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Verify story created
        self.assertEqual(story_key, "DEV-100")
        self.repository.create_release_story.assert_awaited_once()
        
        # Verify subtasks created
        self.assertEqual(self.repository.create_subtask_for_release.await_count, 2)
        
        # Check sync results
        self.assertEqual(sync_results["created_developer_board_tasks"], 3)  # 1 story + 2 subtasks
        self.assertEqual(len(sync_results["errors"]), 0)

    async def test_create_release_story_with_subtasks_reuses_existing_story(self):
        """Test that existing stories are reused."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                jira_issue_key="PM-101",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                jira_issue_key="PM-102",
            ),
        ]
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock existing story
        self.repository.get_story_by_release_name = AsyncMock(return_value="DEV-100")
        self.repository.create_release_story = AsyncMock()
        self.repository.create_subtask_for_release = AsyncMock(return_value="DEV-101")
        self.repository.create_jira_task_from_feature = AsyncMock(return_value="PM-101")
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Verify existing story used
        self.assertEqual(story_key, "DEV-100")
        self.repository.create_release_story.assert_not_awaited()
        
        # Verify subtasks created for both features
        self.assertEqual(self.repository.create_subtask_for_release.await_count, 2)

    async def test_create_release_story_with_subtasks_skips_invalid_features(self):
        """Test that invalid features are skipped."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Valid Feature 1",
                jira_issue_key="PM-101",
            ),
            create_test_feature(
                row_number=2,
                task_title="Invalid Feature",
                status="۲. تحلیل مسئله و RFP",  # Below minimum
            ),
            create_test_feature(
                row_number=3,
                task_title="Valid Feature 2",
                jira_issue_key="PM-102",
            ),
        ]
        
        # Mock validation
        def validate_side_effect(feature, minimum_status):
            if feature.row_number in [1, 3]:
                return (True, None)
            return (False, "Row 2: Status below minimum")
        
        self.repository.validate_feature_for_task_creation.side_effect = validate_side_effect
        
        # Mock story/subtask creation
        self.repository.get_story_by_release_name = AsyncMock(return_value=None)
        self.repository.create_release_story = AsyncMock(return_value="DEV-100")
        self.repository.create_subtask_for_release = AsyncMock(return_value="DEV-101")
        self.repository.create_jira_task_from_feature = AsyncMock(return_value="PM-101")
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Verify story created
        self.assertEqual(story_key, "DEV-100")
        
        # Verify only two subtasks created (for valid features)
        self.assertEqual(self.repository.create_subtask_for_release.await_count, 2)
        
        # Check skipped
        self.assertEqual(len(sync_results["skipped"]), 1)
        self.assertIn("below minimum", sync_results["skipped"][0])

    async def test_create_release_story_with_subtasks_no_valid_features(self):
        """Test handling when no features are valid."""
        features = [
            create_test_feature(
                row_number=1,
                status="۲. تحلیل مسئله و RFP",
            ),
        ]
        
        # Mock validation fails
        self.repository.validate_feature_for_task_creation.return_value = (
            False,
            "Row 1: Status below minimum",
        )
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Should return None
        self.assertIsNone(story_key)
        self.assertEqual(len(sync_results["skipped"]), 1)

    async def test_create_release_story_with_subtasks_creates_pm_tasks_first(self):
        """Test that PM Board tasks are created before developer board subtasks."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                jira_issue_key=None,  # No PM task yet
                story_name="Version 2.5.0",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                jira_issue_key="PM-102",  # Already has PM task
                story_name="Version 2.5.0",
            ),
        ]
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock story creation
        self.repository.get_story_by_release_name = AsyncMock(return_value=None)
        self.repository.create_release_story = AsyncMock(return_value="DEV-100")
        
        # Mock PM task creation
        self.repository.create_jira_task_from_feature = AsyncMock(return_value="PM-101")
        
        # Mock subtask creation
        self.repository.create_subtask_for_release = AsyncMock(
            side_effect=["DEV-101", "DEV-102"]
        )
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Verify PM task created first for Feature A
        self.repository.create_jira_task_from_feature.assert_awaited_once()
        self.assertEqual(sync_results["created_jira_tasks"], 1)
        
        # Verify subtasks created for both features
        self.assertEqual(self.repository.create_subtask_for_release.await_count, 2)
        
        # Check story key
        self.assertEqual(story_key, "DEV-100")

    async def test_create_release_story_with_subtasks_handles_errors(self):
        """Test error handling in release story creation."""
        features = [
            create_test_feature(row_number=1, jira_issue_key="PM-101"),
            create_test_feature(row_number=2, jira_issue_key="PM-102"),
        ]
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock story creation fails
        self.repository.get_story_by_release_name = AsyncMock(return_value=None)
        self.repository.create_release_story = AsyncMock(return_value=None)
        self.repository.create_jira_task_from_feature = AsyncMock(return_value="PM-101")
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Should return None
        self.assertIsNone(story_key)
        
        # Should have error
        self.assertEqual(len(sync_results["errors"]), 1)
        self.assertIn("Failed to create story", sync_results["errors"][0])

    async def test_create_release_story_with_subtasks_skips_certain_statuses(self):
        """Test that certain statuses are skipped for developer board tasks."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                status="۱. ثبت و اولویت بندی",
                jira_issue_key="PM-101",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                status="۱۰. تکمیل شده",
                jira_issue_key="PM-102",
            ),
        ]
        
        # Mock validation passes (for PM task creation)
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock story creation
        self.repository.get_story_by_release_name = AsyncMock(return_value=None)
        self.repository.create_release_story = AsyncMock(return_value="DEV-100")
        
        # Mock subtask creation (should not be called)
        self.repository.create_subtask_for_release = AsyncMock()
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Story should be created
        self.assertEqual(story_key, "DEV-100")
        
        # But no subtasks (skipped due to status)
        self.repository.create_subtask_for_release.assert_not_awaited()

    async def test_create_release_story_with_subtasks_deletes_orphaned_subtasks(self):
        """Test that orphaned subtasks (in Jira but not in Google Sheet) are deleted."""
        # Create features - only 2 valid features in Google Sheet
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                developer_board_issue_key="DEV-101",  # Existing subtask
                jira_issue_key="PM-101",
                story_name="Version 2.5.0",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                developer_board_issue_key="DEV-102",  # Existing subtask
                jira_issue_key="PM-102",
                story_name="Version 2.5.0",
            ),
        ]
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock existing story with 4 subtasks (2 are orphaned)
        mock_story = MagicMock()
        mock_subtasks = [
            MagicMock(key="DEV-101"),  # Valid - exists in sheet
            MagicMock(key="DEV-102"),  # Valid - exists in sheet
            MagicMock(key="DEV-103"),  # Orphaned - deleted from sheet
            MagicMock(key="DEV-104"),  # Orphaned - deleted from sheet
        ]
        mock_story.fields.subtasks = mock_subtasks
        
        self.repository.jira_repository.get_issue.return_value = mock_story
        self.repository.get_story_by_release_name = AsyncMock(return_value="DEV-100")
        self.repository.update_jira_task_description = AsyncMock()
        self.repository.jira_repository.delete_issue = MagicMock()
        
        # Conversion returns same key (no recreation)
        self.repository.convert_existing_task_to_subtask = AsyncMock(
            side_effect=lambda issue_key, parent_story_key: issue_key
        )
        
        # Mock update methods
        self.repository.update_developer_board_task_from_feature = AsyncMock(return_value=True)
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_jira_tasks": 0,
            "updated_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "updated_developer_board_tasks": 0,
            "deleted_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Verify story key returned
        self.assertEqual(story_key, "DEV-100")
        
        # Verify both valid subtasks were updated (not deleted)
        self.assertEqual(self.repository.update_developer_board_task_from_feature.await_count, 2)
        
        # Verify orphaned subtasks were deleted
        self.assertEqual(self.repository.jira_repository.delete_issue.call_count, 2)
        
        # Verify the correct orphaned keys were deleted
        deleted_keys = [
            call[0][0] for call in self.repository.jira_repository.delete_issue.call_args_list
        ]
        self.assertIn("DEV-103", deleted_keys)
        self.assertIn("DEV-104", deleted_keys)
        
        # Verify sync results updated
        self.assertEqual(sync_results["deleted_developer_board_tasks"], 2)
        self.assertEqual(sync_results["updated_developer_board_tasks"], 2)

    async def test_create_release_story_with_subtasks_no_orphaned_subtasks(self):
        """Test that no deletion occurs when all subtasks are valid."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                developer_board_issue_key="DEV-101",
                jira_issue_key="PM-101",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                developer_board_issue_key="DEV-102",
                jira_issue_key="PM-102",
            ),
        ]
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock existing story with matching subtasks (no orphans)
        mock_story = MagicMock()
        mock_subtasks = [
            MagicMock(key="DEV-101"),
            MagicMock(key="DEV-102"),
        ]
        mock_story.fields.subtasks = mock_subtasks
        
        self.repository.jira_repository.get_issue.return_value = mock_story
        self.repository.get_story_by_release_name = AsyncMock(return_value="DEV-100")
        self.repository.update_jira_task_description = AsyncMock()
        self.repository.jira_repository.delete_issue = MagicMock()
        self.repository.update_developer_board_task_from_feature = AsyncMock(return_value=True)
        
        # Conversion returns same key (no recreation)
        self.repository.convert_existing_task_to_subtask = AsyncMock(
            side_effect=lambda issue_key, parent_story_key: issue_key
        )
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "updated_developer_board_tasks": 0,
            "deleted_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Verify no deletions occurred
        self.repository.jira_repository.delete_issue.assert_not_called()
        self.assertEqual(sync_results["deleted_developer_board_tasks"], 0)

    async def test_create_release_story_with_subtasks_handles_deletion_errors(self):
        """Test error handling when orphaned subtask deletion fails."""
        # Need at least 2 features to create a story (not a regular task)
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                developer_board_issue_key="DEV-101",
                jira_issue_key="PM-101",
                story_name="Version 2.5.0",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                developer_board_issue_key="DEV-102",
                jira_issue_key="PM-102",
                story_name="Version 2.5.0",
            ),
        ]
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock story with orphaned subtask
        mock_story = MagicMock()
        mock_subtasks = [
            MagicMock(key="DEV-101"),  # Valid
            MagicMock(key="DEV-102"),  # Valid
            MagicMock(key="DEV-999"),  # Orphaned
        ]
        mock_story.fields.subtasks = mock_subtasks
        
        self.repository.jira_repository.get_issue.return_value = mock_story
        self.repository.get_story_by_release_name = AsyncMock(return_value="DEV-100")
        self.repository.update_jira_task_description = AsyncMock()
        self.repository.update_developer_board_task_from_feature = AsyncMock(return_value=True)
        
        # Conversion returns same key (no recreation)
        self.repository.convert_existing_task_to_subtask = AsyncMock(
            side_effect=lambda issue_key, parent_story_key: issue_key
        )
        
        # Mock deletion failure
        self.repository.jira_repository.delete_issue = MagicMock(
            side_effect=Exception("Permission denied")
        )
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_jira_tasks": 0,
            "created_developer_board_tasks": 0,
            "updated_developer_board_tasks": 0,
            "deleted_developer_board_tasks": 0,
            "skipped": [],
            "errors": [],
        }
        
        story_key = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            features,
            sync_results,
        )
        
        # Should still return story key
        self.assertEqual(story_key, "DEV-100")
        
        # Verify error was logged
        self.assertEqual(len(sync_results["errors"]), 1)
        self.assertIn("DEV-999", sync_results["errors"][0])
        
        # Verify no successful deletions
        self.assertEqual(sync_results["deleted_developer_board_tasks"], 0)


class TestReleaseWorkflowIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for release-based workflow in sync operation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mocks
        self.repository = MagicMock()
        self.settings = MagicMock()
        self.user_config = MagicMock()
        self.notification_gateway = MagicMock()
        self.generate_acceptance_criteria_use_case = MagicMock()
        self.generate_test_scenarios_use_case = MagicMock()
        
        # Setup project config
        self.project_config = MagicMock()
        self.project_config.spreadsheet_id = "test123"
        self.project_config.boards.developer_board.sheet_name = "Test Sheet"
        self.project_config.sync_settings.minimum_status_for_task_creation = (
            "۵. آماده پیاده سازی فنی"
        )
        self.repository.project_config = self.project_config
        
        # Default async mocks for repository methods used across tests
        self.repository.convert_existing_task_to_subtask = AsyncMock(return_value="DEV-KEY")
        self.repository.update_story_from_subtasks = AsyncMock(return_value=True)
        self.repository.update_release_note = AsyncMock(return_value=True)
        self.repository.link_story_dependencies = AsyncMock(return_value=None)
        self.repository.validate_feature_for_update = MagicMock(return_value=(True, None))
        self.repository.jira_repository = MagicMock()
        self.repository.jira_repository.get_issue = MagicMock(return_value=None)
        
        # Create use case
        self.use_case = SynthPMUseCase(
            repository=self.repository,
            settings=self.settings,
            user_config=self.user_config,
            notification_gateway=self.notification_gateway,
            generate_acceptance_criteria_use_case=self.generate_acceptance_criteria_use_case,
            generate_test_scenarios_use_case=self.generate_test_scenarios_use_case,
        )

    async def test_sync_groups_and_processes_by_release(self):
        """Test that sync groups features by release and processes them."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                story_name="Version 2.5.0",
                jira_issue_key="PM-101",
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                story_name="Version 2.5.0",
                jira_issue_key="PM-102",
            ),
            create_test_feature(
                row_number=3,
                task_title="Feature C",
                story_name="Version 2.6.0",
                jira_issue_key="PM-103",
            ),
            create_test_feature(
                row_number=4,
                task_title="Feature D",
                story_name="Version 2.6.0",
                jira_issue_key="PM-104",
            ),
        ]
        
        # Mock repository methods
        self.repository.get_developer_board_features = AsyncMock(return_value=features)
        self.repository.detect_feature_changes = AsyncMock(return_value={
            "new": features,
            "modified": [],
            "unchanged": [],
            "needs_docs": [],
        })
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        self.repository.get_story_by_release_name = AsyncMock(return_value=None)
        self.repository.create_release_story = AsyncMock(
            side_effect=["DEV-100", "DEV-103"]
        )
        self.repository.create_subtask_for_release = AsyncMock(
            side_effect=["DEV-101", "DEV-102", "DEV-104", "DEV-105"]
        )
        self.repository.update_change_tracker = AsyncMock(return_value=True)
        self.repository.update_sync_status = AsyncMock()
        self.repository.get_sync_status = AsyncMock(return_value=None)
        self.repository.create_jira_task_from_feature = AsyncMock(return_value="PM-101")
        self.repository.get_release_notes = AsyncMock(return_value=[])
        self.repository.sync_remaining_hours_to_sheet = AsyncMock(return_value=False)
        self.repository.sync_jira_status_to_sheet = AsyncMock(return_value=False)
        self.repository.update_story_from_subtasks = AsyncMock(return_value=True)
        self.repository.update_release_note = AsyncMock(return_value=True)
        self.repository.link_story_dependencies = AsyncMock(return_value=None)
        self.repository.jira_repository = MagicMock()
        self.repository.jira_repository.get_issue = MagicMock(return_value=None)
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        # Run sync
        result = await self.use_case.sync_developer_board_features()
        
        # Verify success
        self.assertEqual(result["status"], "success")
        
        # Verify stories created (2 releases)
        self.assertEqual(self.repository.create_release_story.await_count, 2)
        
        # Verify subtasks created (4 features)
        self.assertEqual(self.repository.create_subtask_for_release.await_count, 4)

    async def test_update_existing_subtasks(self):
        """Test that existing subtasks are updated and converted, not recreated."""
        feature_a = create_test_feature(
            row_number=1,
            task_title="Existing Feature A",
            story_name="Version 2.5.0",
            jira_issue_key="PM-101",
            developer_board_issue_key="DEV-101",
        )
        feature_b = create_test_feature(
            row_number=2,
            task_title="Existing Feature B",
            story_name="Version 2.5.0",
            jira_issue_key="PM-102",
            developer_board_issue_key="DEV-102",
        )
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock story exists
        self.repository.get_story_by_release_name = AsyncMock(return_value="DEV-100")
        
        # Mock update succeeds
        self.repository.update_developer_board_task_from_feature = AsyncMock(return_value=True)
        
        # User config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "updated_developer_board_tasks": 0,
            "created_developer_board_tasks": 0,
            "converted_to_subtasks": 0,
            "errors": [],
            "skipped": [],
        }
        
        # Execute
        await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            [feature_a, feature_b],
            sync_results,
        )
        
        # Verify update was called instead of create
        self.assertEqual(
            self.repository.update_developer_board_task_from_feature.await_count, 2,
        )
        self.assertEqual(sync_results["updated_developer_board_tasks"], 2)
        self.assertEqual(sync_results["created_developer_board_tasks"], 0)
        
        # Verify conversion to subtask was attempted (preserves time & comments)
        self.assertEqual(
            self.repository.convert_existing_task_to_subtask.await_count, 2,
        )
        self.assertEqual(sync_results["converted_to_subtasks"], 2)

    async def test_existing_task_converted_to_subtask_preserves_data(self):
        """Test that standalone Task is converted to Sub-task under Story.

        Conversion via issue type update preserves worklogs, comments,
        and attachments — no data is lost.
        """
        feature_a = create_test_feature(
            row_number=1,
            task_title="Feature A",
            story_name="اتصال به راست چین",
            jira_issue_key="PM-101",
            developer_board_issue_key="DEV-101",
        )
        feature_b = create_test_feature(
            row_number=2,
            task_title="Feature B",
            story_name="اتصال به راست چین",
            jira_issue_key="PM-102",
            developer_board_issue_key="DEV-102",
        )

        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        self.repository.get_story_by_release_name = AsyncMock(return_value="DEV-100")
        self.repository.update_developer_board_task_from_feature = AsyncMock(return_value=True)
        self.repository.convert_existing_task_to_subtask = AsyncMock(return_value="DEV-101")
        self.user_config.get_all_user_configs.return_value = {}

        sync_results = {
            "updated_developer_board_tasks": 0,
            "created_developer_board_tasks": 0,
            "converted_to_subtasks": 0,
            "errors": [],
            "skipped": [],
        }

        await self.use_case._create_release_story_with_subtasks(
            "اتصال به راست چین",
            [feature_a, feature_b],
            sync_results,
        )

        self.assertEqual(
            self.repository.convert_existing_task_to_subtask.await_count, 2,
        )
        self.repository.convert_existing_task_to_subtask.assert_any_await(
            issue_key="DEV-101", parent_story_key="DEV-100",
        )
        self.repository.convert_existing_task_to_subtask.assert_any_await(
            issue_key="DEV-102", parent_story_key="DEV-100",
        )
        self.assertEqual(sync_results["converted_to_subtasks"], 2)
        self.assertEqual(sync_results["updated_developer_board_tasks"], 2)

    async def test_conversion_failure_still_updates_task(self):
        """Test that even if conversion fails, the task is still updated."""
        feature = create_test_feature(
            row_number=1,
            task_title="Feature",
            story_name="Version 2.5.0",
            jira_issue_key="PM-101",
            developer_board_issue_key="DEV-101",
        )
        dummy = create_test_feature(
            row_number=2,
            task_title="Dummy",
            story_name="Version 2.5.0",
            jira_issue_key="PM-102",
        )

        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        self.repository.get_story_by_release_name = AsyncMock(return_value="DEV-100")
        self.repository.update_developer_board_task_from_feature = AsyncMock(return_value=True)
        self.repository.convert_existing_task_to_subtask = AsyncMock(return_value=None)
        self.repository.create_subtask_for_release = AsyncMock(return_value="DEV-201")
        self.user_config.get_all_user_configs.return_value = {}

        sync_results = {
            "updated_developer_board_tasks": 0,
            "created_developer_board_tasks": 0,
            "converted_to_subtasks": 0,
            "errors": [],
            "skipped": [],
        }

        await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            [feature, dummy],
            sync_results,
        )

        self.repository.convert_existing_task_to_subtask.assert_awaited_once()
        self.repository.update_developer_board_task_from_feature.assert_awaited_once()
        self.assertEqual(sync_results["converted_to_subtasks"], 0)
        self.assertEqual(sync_results["updated_developer_board_tasks"], 1)

    async def test_update_regular_task_existing(self):
        """Test updating regular task when it already exists."""
        feature = create_test_feature(
            row_number=1,
            task_title="Regular Task",
            story_name="",  # No story name
            jira_issue_key="PM-101",
            developer_board_issue_key="DEV-101",  # Already exists
        )
        
        # Mock update succeeds
        self.repository.update_developer_board_task_from_feature = AsyncMock(return_value=True)
        
        # User config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "updated_developer_board_tasks": 0,
            "errors": [],
        }
        
        # Execute
        await self.use_case._create_regular_tasks_for_features([feature], sync_results)
        
        # Verify update was called
        self.repository.update_developer_board_task_from_feature.assert_awaited_once()
        self.assertEqual(sync_results["updated_developer_board_tasks"], 1)

    async def test_singular_release_creates_regular_task(self):
        """Test that a release with only 1 feature creates a regular task."""
        feature = create_test_feature(
            row_number=1,
            task_title="Single Feature",
            story_name="Version 2.5.0",
            jira_issue_key="PM-101",
        )
        
        # Mock validation
        self.repository.validate_feature_for_task_creation.return_value = (True, None)
        
        # Mock regular task creation
        self.repository.create_developer_board_task_from_feature = AsyncMock(
            return_value="DEV-101"
        )
        
        # User config
        self.user_config.get_all_user_configs.return_value = {}
        
        sync_results = {
            "created_developer_board_tasks": 0,
            "errors": [],
            "skipped": [],
        }
        
        # Execute
        result = await self.use_case._create_release_story_with_subtasks(
            "Version 2.5.0",
            [feature],
            sync_results,
        )
        
        # Verify no story created (returns None)
        self.assertIsNone(result)
        
        # Verify regular task was created
        self.repository.create_developer_board_task_from_feature.assert_awaited_once()
        self.assertEqual(sync_results["created_developer_board_tasks"], 1)


if __name__ == "__main__":
    unittest.main()
