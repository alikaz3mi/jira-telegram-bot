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
            self.assertIn('project = "DEV"', jql)
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
        
        # Mock story issue
        mock_issue = MagicMock()
        mock_issue.key = "DEV-123"
        
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
        
        # Mock create_issue to return a mock issue
        mock_issue = MagicMock()
        mock_issue.key = "DEV-456"
        self.jira_repository.create_issue = MagicMock(return_value=mock_issue)
        
        # Call the method
        result = await self.repository.create_release_story(release_name, features)
        
        # Verify create_issue was called
        self.jira_repository.create_issue.assert_called_once()
        call_args = self.jira_repository.create_issue.call_args
        
        # Verify the summary contains release name
        issue_dict = call_args[0][0]
        self.assertIn(release_name, issue_dict['summary'])
        
        # Verify result
        self.assertEqual(result, "DEV-456")

    async def test_create_subtask_for_release_calls_create_issue(self):
        """Test that create_subtask_for_release calls create_issue correctly."""
        story_key = "DEV-123"
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=2,
            task_title="Test Feature",
            description="Test Description",
            release="Version 2.5.0",
        )
        
        # Mock create_issue
        mock_issue = MagicMock()
        mock_issue.key = "DEV-124"
        self.jira_repository.create_issue = MagicMock(return_value=mock_issue)
        
        # Call the method
        result = await self.repository.create_subtask_for_release(story_key, feature)
        
        # Verify create_issue was called
        self.jira_repository.create_issue.assert_called_once()
        call_args = self.jira_repository.create_issue.call_args
        
        # Verify the issue dict has correct structure
        issue_dict = call_args[0][0]
        self.assertEqual(issue_dict['issuetype']['name'], 'Sub-task')
        self.assertIn(story_key, issue_dict['parent']['key'])
        self.assertIn(feature.task_title, issue_dict['summary'])
        
        # Verify result
        self.assertEqual(result, "DEV-124")

    async def test_get_developer_board_issue_calls_search_with_jql(self):
        """Test that get_developer_board_issue calls search_issues with JQL."""
        pm_issue_key = "PM-101"
        
        # Mock search_issues to return empty list
        self.jira_repository.search_issues = MagicMock(return_value=[])
        
        # Call the method
        result = await self.repository.get_developer_board_issue(pm_issue_key)
        
        # Verify search_issues was called
        self.jira_repository.search_issues.assert_called_once()
        call_args = self.jira_repository.search_issues.call_args
        
        # Verify JQL contains the PM issue key reference
        jql = call_args[0][0]
        self.assertIn(pm_issue_key, jql)
        
        # Verify result
        self.assertIsNone(result)

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

    async def test_get_all_features_calls_google_sheets(self):
        """Test that get_all_features calls Google Sheets client."""
        # Mock the Google Sheets client response
        self.google_sheet_client.get_all_values = MagicMock(
            return_value=[
                ["Task Title", "Epic", "Release"],  # Header row
                ["Feature 1", "Epic A", "v2.5.0"],
                ["Feature 2", "Epic B", "v2.5.0"],
            ]
        )
        
        # Mock project config columns
        self.project_config.columns.task_title = "A"
        self.project_config.columns.epic = "B"
        self.project_config.columns.release = "C"
        
        # Call the method
        features = await self.repository.get_all_features()
        
        # Verify Google Sheets was called
        self.google_sheet_client.get_all_values.assert_called()
        
        # Verify we got features back (at least the list is returned)
        self.assertIsInstance(features, list)


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
        
        # Mock create_issue to raise exception
        self.jira_repository.create_issue = MagicMock(
            side_effect=Exception("Jira API error")
        )
        
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
        )
        
        # Mock create_issue to raise exception
        self.jira_repository.create_issue = MagicMock(
            side_effect=Exception("Jira error")
        )
        
        # Call the method
        result = await self.repository.create_subtask_for_release(story_key, feature)
        
        # Verify result is None
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
