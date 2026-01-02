"""Unit tests for release-based repository methods in SynthPM."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
    SynthPMRepository,
)
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.project_config import (
    BoardConfig,
    ProjectBoardsConfig,
    ProjectConfig,
    SyncSettings,
    TelegramConfig,
)
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings


def create_test_feature(**overrides) -> SynthPMFeatureEntity:
    """Factory function to create test feature with defaults."""
    defaults = {
        "row_number": 1,
        "sheet_row_number": 2,
        "task_title": "Test Feature",
        "status": "۵. آماده پیاده سازی فنی",
        "involved_people": "User1",
        "sprint": "Sprint-45",  # Use simple sprint format for tests
        "ai": "✓",
        "implementation_start_date": "2024-01-01",
        "release": "Version 2.5.0",
        "total_hours": 40.0,
        "priority": "High",
        "epic": "Test Epic",
    }
    defaults.update(overrides)
    return SynthPMFeatureEntity(**defaults)


class TestReleaseRepositoryMethods(unittest.IsolatedAsyncioTestCase):
    """Test release-based repository methods."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.google_sheet_client = MagicMock()
        self.jira_repository = MagicMock()
        self.user_config = MagicMock()
        
        # Create test settings
        self.settings = Mock(spec=SynthPMSettings)
        self.settings.developer_board_project_key = "DEV"
        
        # Create test project config
        self.project_config = ProjectConfig(
            project_key="TEST",
            spreadsheet_id="test123",
            boards=ProjectBoardsConfig(
                developer_board=BoardConfig(
                    jira_board_key="DEV",
                    sheet_name="Test Sheet",
                    data_range="A2:AY",
                ),
            ),
            telegram=TelegramConfig(
                bot_token_env="TEST_BOT_TOKEN",
                channel_id_env="TEST_CHANNEL_ID",
                group_id_env="TEST_GROUP_ID",
            ),
            sync_settings=SyncSettings(
                minimum_status_for_task_creation="۵. آماده پیاده سازی فنی",
            ),
        )
        
        self.settings.get_project_config.return_value = self.project_config
        
        # Mock board IDs
        self.jira_repository.get_board_id.return_value = 123
        
        # Create repository
        self.repository = SynthPMRepository(
            google_sheet_client=self.google_sheet_client,
            jira_repository=self.jira_repository,
            settings=self.settings,
            user_config=self.user_config,
            project_key="TEST",
        )

    async def test_get_story_by_release_name_found(self):
        """Test finding existing story by release name."""
        # Mock Jira search
        mock_issue = MagicMock()
        mock_issue.key = "DEV-100"
        self.jira_repository.search_issues.return_value = [mock_issue]
        
        result = await self.repository.get_story_by_release_name("Version 2.5.0")
        
        self.assertEqual(result, "DEV-100")
        self.jira_repository.search_issues.assert_called_once()
        
        # Verify JQL query
        call_args = self.jira_repository.search_issues.call_args
        jql = call_args[0][0]
        self.assertIn("Version 2.5.0", jql)
        self.assertIn("issuetype = Story", jql)

    async def test_get_story_by_release_name_not_found(self):
        """Test when no story exists for release."""
        self.jira_repository.search_issues.return_value = []
        
        result = await self.repository.get_story_by_release_name("Version 2.5.0")
        
        self.assertIsNone(result)

    async def test_get_story_by_release_name_error_handling(self):
        """Test error handling in story search."""
        self.jira_repository.search_issues.side_effect = Exception("Jira error")
        
        result = await self.repository.get_story_by_release_name("Version 2.5.0")
        
        self.assertIsNone(result)

    async def test_create_release_story_success(self):
        """Test successful release story creation."""
        features = [
            create_test_feature(
                row_number=1,
                task_title="Feature A",
                total_hours=40,
            ),
            create_test_feature(
                row_number=2,
                task_title="Feature B",
                total_hours=30,
            ),
        ]
        
        # Mock user config
        mock_user = MagicMock()
        mock_user.jira_username = "john.doe"
        mock_user.google_sheet_name = "User1"
        self.user_config.get_all_user_configs.return_value = {"user1": mock_user}
        
        # Mock sprint
        mock_sprint = {"id": 45, "name": "DEV Sprint 45", "state": "active"}
        self.jira_repository.get_sprint_by_name.return_value = mock_sprint
        
        # Mock epic
        self.repository._create_epic_if_not_exists = MagicMock(
            return_value=(None, "DEV-50")
        )
        
        # Mock components
        self.repository._map_components = MagicMock(return_value=["Backend"])
        self.repository._map_priority = MagicMock(return_value="High")
        self.repository._create_release_not_exist = MagicMock()
        
        # Mock task creation
        mock_issue = MagicMock()
        mock_issue.key = "DEV-100"
        self.jira_repository.create_task.return_value = mock_issue
        self.jira_repository.get_issue_url_by_key.return_value = "http://jira/DEV-100"
        
        result = await self.repository.create_release_story(
            "Version 2.5.0",
            features,
        )
        
        self.assertEqual(result, "DEV-100")
        self.jira_repository.create_task.assert_called_once()
        
        # Verify task data
        call_args = self.jira_repository.create_task.call_args
        task_data = call_args[0][0]
        self.assertEqual(task_data.task_type, "Story")
        self.assertIn("Version 2.5.0", task_data.summary)
        self.assertIn("Feature A", task_data.description)
        self.assertIn("Feature B", task_data.description)
        self.assertIn("70.0h", task_data.description)  # Total hours

    async def test_create_release_story_empty_features(self):
        """Test creating story with empty features list."""
        result = await self.repository.create_release_story("Version 2.5.0", [])
        
        self.assertIsNone(result)

    async def test_create_release_story_sprint_creation(self):
        """Test that sprint is created if it doesn't exist."""
        features = [create_test_feature()]
        
        # Mock user config
        self.user_config.get_all_user_configs.return_value = {}
        
        # Mock sprint doesn't exist
        self.jira_repository.get_sprint_by_name.return_value = None
        
        # Mock sprint creation
        mock_sprint = {"id": 45, "name": "DEV Sprint 45", "state": "future"}
        self.repository._create_sprint = MagicMock(return_value=mock_sprint)
        
        # Mock other methods
        self.repository._create_epic_if_not_exists = MagicMock(return_value=(None, None))
        self.repository._map_components = MagicMock(return_value=[])
        self.repository._map_priority = MagicMock(return_value="Medium")
        self.repository._create_release_not_exist = MagicMock()
        
        # Mock task creation
        mock_issue = MagicMock()
        mock_issue.key = "DEV-100"
        self.jira_repository.create_task.return_value = mock_issue
        self.jira_repository.get_issue_url_by_key.return_value = "http://jira/DEV-100"
        
        result = await self.repository.create_release_story("Version 2.5.0", features)
        
        self.assertEqual(result, "DEV-100")
        # Sprint is not created when using simple sprint format (only with sprint_list)

    async def test_create_release_story_error_handling(self):
        """Test error handling in story creation."""
        features = [create_test_feature()]
        
        # Mock error
        self.user_config.get_all_user_configs.side_effect = Exception("Config error")
        
        result = await self.repository.create_release_story("Version 2.5.0", features)
        
        self.assertIsNone(result)

    async def test_create_subtask_for_release_single_assignee(self):
        """Test subtask creation with single assignee."""
        feature = create_test_feature(
            task_title="Implement auth",
            jira_issue_key="PM-101",
            total_hours=40,
        )
        assignees = ["john.doe"]
        
        # Mock methods
        self.repository.extract_dates_from_feature_in_str = MagicMock(
            return_value={
                "due_date": "2024-01-31",
                "target_start": "2024-01-01",
                "target_end": "2024-01-31",
            }
        )
        self.repository._map_components = MagicMock(return_value=["Backend"])
        self.repository._map_priority = MagicMock(return_value="High")
        
        # Mock task creation
        mock_issue = MagicMock()
        mock_issue.key = "DEV-101"
        self.jira_repository.create_task.return_value = mock_issue
        self.jira_repository.get_issue_url_by_key.return_value = "http://jira/DEV-101"
        
        # Mock link issues
        self.repository._link_issues = MagicMock()
        
        # Mock sheet update
        self.repository.update_developer_board_feature = AsyncMock(return_value=True)
        
        result = await self.repository.create_subtask_for_release(
            "DEV-100",
            feature,
            assignees,
        )
        
        self.assertEqual(result, "DEV-101")
        self.jira_repository.create_task.assert_called_once()
        
        # Verify task data
        call_args = self.jira_repository.create_task.call_args
        task_data = call_args[0][0]
        self.assertEqual(task_data.task_type, "Sub-task")
        self.assertEqual(task_data.parent_issue_key, "DEV-100")
        self.assertEqual(task_data.assignee, "john.doe")
        self.assertIsNotNone(task_data.story_points)
        
        # Verify linking
        self.repository._link_issues.assert_called_once_with("PM-101", "DEV-101")
        
        # Verify sheet update
        self.repository.update_developer_board_feature.assert_awaited_once()

    async def test_create_subtask_for_release_multiple_assignees(self):
        """Test subtask creation with multiple assignees."""
        feature = create_test_feature(
            task_title="Complex feature",
            jira_issue_key="PM-101",
            total_hours=80,
        )
        assignees = ["john.doe", "jane.smith"]
        
        # Mock methods
        self.repository.extract_dates_from_feature_in_str = MagicMock(
            return_value={}
        )
        self.repository._map_components = MagicMock(return_value=["Backend", "Frontend"])
        self.repository._map_priority = MagicMock(return_value="High")
        
        # Mock task creation
        mock_issue = MagicMock()
        mock_issue.key = "DEV-101"
        self.jira_repository.create_task.return_value = mock_issue
        self.jira_repository.get_issue_url_by_key.return_value = "http://jira/DEV-101"
        
        # Mock subtask creation for assignees
        self.repository._create_subtasks_for_assignees = AsyncMock(
            return_value=["DEV-102", "DEV-103"]
        )
        
        # Mock link and update
        self.repository._link_issues = MagicMock()
        self.repository.update_developer_board_feature = AsyncMock(return_value=True)
        
        result = await self.repository.create_subtask_for_release(
            "DEV-100",
            feature,
            assignees,
        )
        
        self.assertEqual(result, "DEV-101")
        
        # Verify nested subtasks created
        self.repository._create_subtasks_for_assignees.assert_awaited_once()
        
        # Verify no direct assignee on parent subtask
        call_args = self.jira_repository.create_task.call_args
        task_data = call_args[0][0]
        self.assertIsNone(task_data.assignee)
        self.assertIsNone(task_data.story_points)

    async def test_create_subtask_for_release_no_pm_task(self):
        """Test subtask creation when PM task doesn't exist yet."""
        feature = create_test_feature(
            task_title="Feature",
            jira_issue_key=None,  # No PM task
        )
        
        # Mock methods
        self.repository.extract_dates_from_feature_in_str = MagicMock(return_value={})
        self.repository._map_components = MagicMock(return_value=[])
        self.repository._map_priority = MagicMock(return_value="Medium")
        
        # Mock task creation
        mock_issue = MagicMock()
        mock_issue.key = "DEV-101"
        self.jira_repository.create_task.return_value = mock_issue
        self.jira_repository.get_issue_url_by_key.return_value = "http://jira/DEV-101"
        
        # Mock update
        self.repository.update_developer_board_feature = AsyncMock(return_value=True)
        
        result = await self.repository.create_subtask_for_release(
            "DEV-100",
            feature,
            ["john.doe"],
        )
        
        self.assertEqual(result, "DEV-101")
        
        # Verify link not called (no PM task to link)
        # _link_issues should not be in the call stack

    async def test_create_subtask_for_release_error_handling(self):
        """Test error handling in subtask creation."""
        feature = create_test_feature()
        
        # Mock error
        self.repository.extract_dates_from_feature_in_str = MagicMock(
            side_effect=Exception("Date parsing error")
        )
        
        result = await self.repository.create_subtask_for_release(
            "DEV-100",
            feature,
            ["john.doe"],
        )
        
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
