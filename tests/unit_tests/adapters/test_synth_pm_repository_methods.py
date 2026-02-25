"""Unit tests for SynthPM Repository method signatures and basic operations."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.adapters.repositories.synth_pm_repository import SynthPMRepository
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity


class TestSynthPMRepositoryMethodSignatures(unittest.IsolatedAsyncioTestCase):
    """Test that repository methods call their dependencies with correct signatures."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock dependencies
        self.google_sheet_client = MagicMock()
        self.jira_repository = MagicMock()
        self.user_config = MagicMock()
        
        # Mock settings and project config
        self.settings = MagicMock()
        self.project_config = MagicMock()
        self.project_config.project_key = "test_project"
        self.project_config.boards.developer_board.jira_board_key = "DEV"
        self.project_config.boards.pm_board.jira_board_key = "PM"
        self.project_config.boards.pm_board.enabled = True
        
        self.settings.get_project_config = MagicMock(return_value=self.project_config)
        self.settings.get_project_metadata = MagicMock(return_value=MagicMock())
        
        # Mock get_board_id
        self.jira_repository.get_board_id = MagicMock(return_value=123)
        
        # Create repository instance
        self.repository = SynthPMRepository(
            google_sheet_client=self.google_sheet_client,
            jira_repository=self.jira_repository,
            settings=self.settings,
            user_config=self.user_config,
        )

    async def test_get_story_by_release_name_calls_search_issues_correctly(self):
        """Test that get_story_by_release_name calls search_issues with correct parameters.
        
        This test catches parameter name bugs like passing 'maxResults' instead of 'max_results'.
        """
        release_name = "Version 2.5.0"
        
        # Create a real mock that will enforce the method signature
        from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository
        
        # Create a spec'd mock that enforces the actual signature
        mock_search = MagicMock(spec=JiraServerRepository.search_issues)
        mock_search.return_value = []
        self.jira_repository.search_issues = mock_search
        
        # Call the method - this will FAIL if wrong parameter names are used
        try:
            result = await self.repository.get_story_by_release_name(release_name)
            
            # Verify search_issues was called
            self.jira_repository.search_issues.assert_called_once()
            call_args = self.jira_repository.search_issues.call_args
            
            # Check that JQL is correct
            jql = call_args[0][0]  # First positional arg
            self.assertIn('project = "test_project"', jql)
            self.assertIn('issuetype = Story', jql)
            self.assertIn(f'summary ~ "{release_name}"', jql)
            
            # Verify result
            self.assertIsNone(result)
            
        except TypeError as e:
            # If we get a TypeError about unexpected keyword argument,
            # that means we caught the bug!
            if "unexpected keyword argument" in str(e):
                self.fail(f"❌ BUG CAUGHT: {e}")
            raise

    async def test_get_story_by_release_name_returns_existing_story(self):
        """Test that get_story_by_release_name returns story key when found."""
        release_name = "Version 2.5.0"
        
        mock_issue = MagicMock()
        mock_issue.key = "DEV-123"
        mock_issue.fields.summary = "Version 2.5.0"
        
        self.jira_repository.search_issues = MagicMock(return_value=[mock_issue])
        
        # Call the method
        result = await self.repository.get_story_by_release_name(release_name)
        
        # Verify result
        self.assertEqual(result, "DEV-123")
        self.jira_repository.search_issues.assert_called_once()

    async def test_get_story_by_release_name_handles_error(self):
        """Test that get_story_by_release_name handles errors gracefully."""
        release_name = "Version 2.5.0"
        
        # Mock search_issues to raise an exception
        self.jira_repository.search_issues = MagicMock(
            side_effect=Exception("Search failed")
        )
        
        # Call the method
        result = await self.repository.get_story_by_release_name(release_name)
        
        # Verify result is None (error handled)
        self.assertIsNone(result)

    async def test_create_release_story_builds_correct_summary(self):
        """Test that create_release_story builds correct issue summary."""
        release_name = "Version 2.5.0"
        features = [
            SynthPMFeatureEntity(
                row_number=1,
                sheet_row_number=2,
                task_title="Feature 1",
                release=release_name,
            ),
            SynthPMFeatureEntity(
                row_number=2,
                sheet_row_number=3,
                task_title="Feature 2",
                release=release_name,
            ),
        ]
        
        # Mock create_task to return a mock issue
        mock_issue = MagicMock()
        mock_issue.key = "DEV-456"
        self.jira_repository.create_task = MagicMock(return_value=mock_issue)
        self.jira_repository.get_sprint_by_name = MagicMock(return_value=None)
        self.jira_repository.get_issue_url_by_key = MagicMock(return_value="http://jira/DEV-456")
        
        # Call the method
        result = await self.repository.create_release_story(release_name, features)
        
        # Verify create_task was called
        self.jira_repository.create_task.assert_called_once()
        call_args = self.jira_repository.create_task.call_args
        
        # Verify the summary contains release name
        task_data = call_args[0][0]
        self.assertIn(release_name, task_data.summary)
        
        # Verify result
        self.assertEqual(result, "DEV-456")

        """Test that get_developer_board_features calls Google Sheets client."""
        # Mock the Google Sheets client response
        self.google_sheet_client.get_values = AsyncMock(
            return_value=[
                ["Task Title", "Status", "Departments"],  # Header row
                ["Feature 1", "۵. آماده پیاده سازی فنی", "Backend"],
                ["Feature 2", "۵. آماده پیاده سازی فنی", "Frontend"],
            ]
        )
        
        # Call the method
        features = await self.repository.get_developer_board_features()
        
        # Verify Google Sheets was called
        self.google_sheet_client.get_values.assert_called()
        
        # Verify we got a list back
        self.assertIsInstance(features, list)

    async def test_validate_feature_for_task_creation_returns_validation_tuple(self):
        """Test that validate_feature_for_task_creation returns (bool, str) tuple."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Feature",
            status="۵. آماده پیاده سازی فنی",
            release="Version 2.5.0",
        )
        
        # Call the method
        is_valid, error_msg = self.repository.validate_feature_for_task_creation(feature)
        
        # Verify return type
        self.assertIsInstance(is_valid, bool)
        self.assertTrue(error_msg is None or isinstance(error_msg, str))

    async def test_repository_initialization_stores_dependencies(self):
        """Test that repository stores all dependencies correctly."""
        self.assertEqual(self.repository.google_sheet_client, self.google_sheet_client)
        self.assertEqual(self.repository.jira_repository, self.jira_repository)
        self.assertEqual(self.repository.settings, self.settings)
        self.assertEqual(self.repository.user_config, self.user_config)

    async def test_update_story_from_subtasks_handles_no_subtasks(self):
        """Test that update_story_from_subtasks clears data when no subtasks exist."""
        story_key = "DEV-123"
        
        # Create proper mock objects
        class MockComponent:
            name = "Backend"
        
        class MockVersion:
            name = "v1.0"
        
        class MockTimetracking:
            originalEstimateSeconds = 3600
            remainingEstimateSeconds = 1800
        
        class MockFields:
            subtasks = []
            components = [MockComponent()]
            fixVersions = [MockVersion()]
            duedate = "2026-01-15"
            timetracking = MockTimetracking()
        
        # Mock story
        mock_story = MagicMock()
        mock_story.key = story_key
        mock_story.fields = MockFields()
        mock_story.fields.__dict__['customfield_10015'] = "2026-01-01"
        mock_story.fields.__dict__['customfield_10016'] = "2026-01-15"
        mock_story.fields.__dict__['customfield_10020'] = [MagicMock(id=1)]
        mock_story.update = MagicMock()
        
        self.jira_repository.get_issue = MagicMock(return_value=mock_story)
        self.jira_repository.jira_target_start_id = 'customfield_10015'
        self.jira_repository.jira_target_end_id = 'customfield_10016'
        self.jira_repository.jira_sprint_id = 'customfield_10020'
        
        # Call the method
        result = await self.repository.update_story_from_subtasks(story_key)
        
        # Verify story.update was called (to clear data)
        mock_story.update.assert_called_once()
        
        # Verify result is True
        self.assertTrue(result)


class TestSynthPMRepositoryErrorHandling(unittest.IsolatedAsyncioTestCase):
    """Test error handling in repository methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.google_sheet_client = MagicMock()
        self.jira_repository = MagicMock()
        self.user_config = MagicMock()
        
        self.settings = MagicMock()
        self.project_config = MagicMock()
        self.project_config.project_key = "test_project"
        self.project_config.boards.developer_board.jira_board_key = "DEV"
        self.project_config.boards.pm_board.jira_board_key = "PM"
        self.project_config.boards.pm_board.enabled = True
        
        self.settings.get_project_config = MagicMock(return_value=self.project_config)
        self.settings.get_project_metadata = MagicMock(return_value=MagicMock())
        
        self.jira_repository.get_board_id = MagicMock(return_value=123)
        
        self.repository = SynthPMRepository(
            google_sheet_client=self.google_sheet_client,
            jira_repository=self.jira_repository,
            settings=self.settings,
            user_config=self.user_config,
        )

    async def test_create_release_story_handles_jira_error(self):
        """Test that create_release_story handles Jira errors."""
        release_name = "Version 2.5.0"
        features = [
            SynthPMFeatureEntity(
                row_number=1,
                sheet_row_number=2,
                task_title="Feature 1",
                release=release_name,
            ),
        ]
        
        # Mock create_task to raise exception
        self.jira_repository.create_task = MagicMock(
            side_effect=Exception("Jira API error")
        )
        self.jira_repository.get_sprint_by_name = MagicMock(return_value=None)
        
        # Call the method
        result = await self.repository.create_release_story(release_name, features)
        
        # Verify result is None (error handled gracefully)
        self.assertIsNone(result)

    async def test_create_subtask_for_release_handles_error(self):
        """Test that create_subtask_for_release handles errors."""
        story_key = "DEV-123"
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Feature",
            release="Version 2.5.0",
            total_hours=8.0,
        )
        
        # Mock create_task to raise exception
        self.jira_repository.create_task = MagicMock(
            side_effect=Exception("Jira error")
        )
        self.jira_repository.get_issue = MagicMock(return_value=None)
        
        # Call the method
        result = await self.repository.create_subtask_for_release(story_key, feature)
        
        # Verify result is None
        self.assertIsNone(result)

    async def test_convert_existing_task_to_subtask_success(self):
        """Test converting a standalone Task to Sub-task preserves data."""
        mock_issue = MagicMock()
        mock_issue.fields.issuetype.name = "Task"
        self.jira_repository.get_issue = MagicMock(return_value=mock_issue)
        self.jira_repository.convert_to_subtask = MagicMock(return_value="DEV-101")

        result = await self.repository.convert_existing_task_to_subtask(
            "DEV-101", "DEV-100",
        )

        self.assertEqual(result, "DEV-101")
        self.jira_repository.convert_to_subtask.assert_called_once_with(
            "DEV-101", "DEV-100",
        )

    async def test_convert_existing_task_already_subtask_of_correct_parent(self):
        """Test that no conversion happens if already a Sub-task of the right parent."""
        mock_issue = MagicMock()
        mock_issue.fields.issuetype.name = "Sub-task"
        mock_issue.fields.parent.key = "DEV-100"
        self.jira_repository.get_issue = MagicMock(return_value=mock_issue)

        result = await self.repository.convert_existing_task_to_subtask(
            "DEV-101", "DEV-100",
        )

        self.assertEqual(result, "DEV-101")
        self.jira_repository.convert_to_subtask.assert_not_called()

    async def test_convert_existing_task_subtask_of_different_parent(self):
        """Test that conversion is skipped if subtask of a different parent."""
        mock_issue = MagicMock()
        mock_issue.fields.issuetype.name = "Sub-task"
        mock_issue.fields.parent.key = "DEV-999"
        self.jira_repository.get_issue = MagicMock(return_value=mock_issue)

        result = await self.repository.convert_existing_task_to_subtask(
            "DEV-101", "DEV-100",
        )

        self.assertIsNone(result)
        self.jira_repository.convert_to_subtask.assert_not_called()

    async def test_convert_existing_task_issue_not_found(self):
        """Test that conversion handles missing issue gracefully."""
        self.jira_repository.get_issue = MagicMock(return_value=None)

        result = await self.repository.convert_existing_task_to_subtask(
            "DEV-MISSING", "DEV-100",
        )

        self.assertIsNone(result)

    async def test_convert_existing_task_jira_error(self):
        """Test that conversion handles Jira API errors gracefully."""
        mock_issue = MagicMock()
        mock_issue.fields.issuetype.name = "Task"
        self.jira_repository.get_issue = MagicMock(return_value=mock_issue)
        self.jira_repository.convert_to_subtask = MagicMock(
            side_effect=Exception("Jira error"),
        )

        result = await self.repository.convert_existing_task_to_subtask(
            "DEV-101", "DEV-100",
        )

        self.assertIsNone(result)

    async def test_convert_existing_task_key_changes_on_recreate(self):
        """Test that sheet is updated when conversion recreates with a new key."""
        mock_issue = MagicMock()
        mock_issue.fields.issuetype.name = "Task"
        self.jira_repository.get_issue = MagicMock(return_value=mock_issue)
        self.jira_repository.convert_to_subtask = MagicMock(return_value="DEV-201")

        mock_feature = MagicMock()
        mock_feature.developer_board_issue_key = "DEV-101"
        mock_feature.sheet_row_number = 5

        self.repository.get_developer_board_features = AsyncMock(return_value=[mock_feature])
        self.repository.update_developer_board_feature = AsyncMock(return_value=True)

        result = await self.repository.convert_existing_task_to_subtask(
            "DEV-101", "DEV-100",
        )

        self.assertEqual(result, "DEV-201")
        self.repository.update_developer_board_feature.assert_called_once_with(
            5, {"developer_board_issue_key": "DEV-201"},
        )


if __name__ == "__main__":
    unittest.main()
