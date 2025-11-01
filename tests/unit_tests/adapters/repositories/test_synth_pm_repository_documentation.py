"""Unit tests for SynthPMRepository new documentation methods."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
    SynthPMRepository,
)
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import (
    SynthPMFeatureEntity,
)


class TestSynthPMRepositoryDocumentationMethods(unittest.IsolatedAsyncioTestCase):
    """Test cases for SynthPMRepository documentation methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.google_sheet_client = MagicMock()
        self.jira_repository = MagicMock()
        self.settings = MagicMock()
        self.user_config = MagicMock()
        
        self.settings.developer_board_project_key = "DEV"
        self.settings.pm_project_key = "PM"
        self.settings.developer_project_key = "DEV"
        
        self.jira_repository.get_board_id.return_value = 123
        
        self.repository = SynthPMRepository(
            google_sheet_client=self.google_sheet_client,
            jira_repository=self.jira_repository,
            settings=self.settings,
            user_config=self.user_config,
        )
        
        self.feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            description="Test Description",
            frontend="8",
            backend="16",
            jira_issue_key="FEAT-1",
        )


class TestCreateDocumentationSubtask(TestSynthPMRepositoryDocumentationMethods):
    """Test creating documentation subtasks."""
    
    async def test_create_documentation_subtask_success(self):
        """Test successfully creating a documentation subtask."""
        mock_issue = MagicMock()
        mock_issue.key = "SUB-1"
        self.jira_repository.create_issue.return_value = mock_issue
        
        user_config = MagicMock()
        user_config.email = "john@example.com"
        self.user_config.get_all_user_configs.return_value = {
            "john_doe": user_config,
        }
        
        result = await self.repository._create_documentation_subtask(
            parent_issue_key="FEAT-1",
            department="Frontend",
            assignee_email="john@example.com",
            feature=self.feature,
        )
        
        self.assertEqual(result, "SUB-1")
        self.jira_repository.create_issue.assert_called_once()
        
        call_args = self.jira_repository.create_issue.call_args
        fields = call_args.kwargs["fields"]
        
        self.assertEqual(fields["project"]["key"], "DEV")
        self.assertEqual(fields["parent"]["key"], "FEAT-1")
        self.assertEqual(fields["issuetype"]["name"], "Sub-task")
        self.assertIn("مستندسازی Frontend", fields["summary"])
        self.assertEqual(fields["assignee"]["name"], "john_doe")
        self.assertEqual(fields["timetracking"]["originalEstimate"], "2h")
    
    async def test_create_documentation_subtask_without_assignee(self):
        """Test creating subtask when assignee not found."""
        mock_issue = MagicMock()
        mock_issue.key = "SUB-1"
        self.jira_repository.create_issue.return_value = mock_issue
        
        self.user_config.get_all_user_configs.return_value = {}
        
        result = await self.repository._create_documentation_subtask(
            parent_issue_key="FEAT-1",
            department="Frontend",
            assignee_email="unknown@example.com",
            feature=self.feature,
        )
        
        self.assertEqual(result, "SUB-1")
        
        call_args = self.jira_repository.create_issue.call_args
        fields = call_args.kwargs["fields"]
        
        self.assertNotIn("assignee", fields)
    
    async def test_create_documentation_subtask_failure(self):
        """Test handling failure when creating subtask."""
        self.jira_repository.create_issue.return_value = None
        
        result = await self.repository._create_documentation_subtask(
            parent_issue_key="FEAT-1",
            department="Frontend",
            assignee_email="john@example.com",
            feature=self.feature,
        )
        
        self.assertIsNone(result)
    
    async def test_create_documentation_subtask_exception(self):
        """Test handling exception when creating subtask."""
        self.jira_repository.create_issue.side_effect = Exception("API Error")
        
        result = await self.repository._create_documentation_subtask(
            parent_issue_key="FEAT-1",
            department="Frontend",
            assignee_email="john@example.com",
            feature=self.feature,
        )
        
        self.assertIsNone(result)


class TestGetJiraUsernameByEmail(TestSynthPMRepositoryDocumentationMethods):
    """Test getting Jira username by email."""
    
    def test_get_jira_username_by_email_found(self):
        """Test getting username when email is found."""
        user1_config = MagicMock()
        user1_config.email = "john@example.com"
        
        user2_config = MagicMock()
        user2_config.email = "jane@example.com"
        
        self.user_config.get_all_user_configs.return_value = {
            "john_doe": user1_config,
            "jane_smith": user2_config,
        }
        
        username = self.repository._get_jira_username_by_email("jane@example.com")
        
        self.assertEqual(username, "jane_smith")
    
    def test_get_jira_username_by_email_not_found(self):
        """Test getting username when email is not found."""
        user_config = MagicMock()
        user_config.email = "john@example.com"
        
        self.user_config.get_all_user_configs.return_value = {
            "john_doe": user_config,
        }
        
        username = self.repository._get_jira_username_by_email("unknown@example.com")
        
        self.assertIsNone(username)
    
    def test_get_jira_username_by_email_no_email_attribute(self):
        """Test getting username when config has no email attribute."""
        user_config = MagicMock(spec=[])
        
        self.user_config.get_all_user_configs.return_value = {
            "john_doe": user_config,
        }
        
        username = self.repository._get_jira_username_by_email("john@example.com")
        
        self.assertIsNone(username)


class TestCreateReleaseInPMBoard(TestSynthPMRepositoryDocumentationMethods):
    """Test creating releases in PM board."""
    
    async def test_create_release_in_pm_board_new_release(self):
        """Test creating a new release."""
        release_note = ReleaseNoteEntity(
            row_number=1,
            release_version="v1.0.0",
            release_components="Component A, Component B",
            description="Test Release",
            start_date="2025-11-01",
            beta_delivery="2025-11-15",
        )
        
        existing_version = MagicMock()
        existing_version.name = "v0.9.0"
        
        self.jira_repository.get_project_versions.return_value = [existing_version]
        
        new_version = MagicMock()
        new_version.id = "10001"
        self.jira_repository.create_version.return_value = new_version
        
        result = await self.repository.create_release_in_pm_board(release_note)
        
        self.assertEqual(result, "10001")
        
        self.jira_repository.create_version.assert_called_once()
        call_args = self.jira_repository.create_version.call_args
        
        self.assertEqual(call_args.kwargs["name"], "v1.0.0")
        self.assertEqual(call_args.kwargs["project"], "PM")
        self.assertEqual(call_args.kwargs["description"], "Test Release")
        self.assertEqual(call_args.kwargs["startDate"], "2025-11-01")
        self.assertEqual(call_args.kwargs["releaseDate"], "2025-11-15")
        self.assertFalse(call_args.kwargs["archived"])
        self.assertFalse(call_args.kwargs["released"])
    
    async def test_create_release_in_pm_board_existing_release(self):
        """Test creating release when it already exists."""
        release_note = ReleaseNoteEntity(
            row_number=1,
            release_version="v1.0.0",
            release_components="Component A",
            description="Test Release",
        )
        
        existing_version = MagicMock()
        existing_version.name = "v1.0.0"
        existing_version.id = "10001"
        
        self.jira_repository.get_project_versions.return_value = [existing_version]
        
        result = await self.repository.create_release_in_pm_board(release_note)
        
        self.assertEqual(result, "10001")
        self.jira_repository.create_version.assert_not_called()
    
    async def test_create_release_in_pm_board_without_dates(self):
        """Test creating release without dates."""
        release_note = ReleaseNoteEntity(
            row_number=1,
            release_version="v1.0.0",
            release_components="Component A",
            description="Test Release",
            start_date=None,
            beta_delivery=None,
        )
        
        self.jira_repository.get_project_versions.return_value = []
        
        new_version = MagicMock()
        new_version.id = "10001"
        self.jira_repository.create_version.return_value = new_version
        
        result = await self.repository.create_release_in_pm_board(release_note)
        
        self.assertEqual(result, "10001")
        
        call_args = self.jira_repository.create_version.call_args
        # When dates are None, they are still passed but with None value
        self.assertIsNone(call_args.kwargs.get("startDate"))
        self.assertIsNone(call_args.kwargs.get("releaseDate"))
    
    async def test_create_release_in_pm_board_failure(self):
        """Test handling failure when creating release."""
        release_note = ReleaseNoteEntity(
            row_number=1,
            release_version="v1.0.0",
            release_components="Component A",
            description="Test Release",
        )
        
        self.jira_repository.get_project_versions.return_value = []
        self.jira_repository.create_version.return_value = None
        
        result = await self.repository.create_release_in_pm_board(release_note)
        
        self.assertIsNone(result)
    
    async def test_create_release_in_pm_board_exception(self):
        """Test handling exception when creating release."""
        release_note = ReleaseNoteEntity(
            row_number=1,
            release_version="v1.0.0",
            release_components="Component A",
            description="Test Release",
        )
        
        self.jira_repository.get_project_versions.side_effect = Exception(
            "API Error",
        )
        
        result = await self.repository.create_release_in_pm_board(release_note)
        
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
