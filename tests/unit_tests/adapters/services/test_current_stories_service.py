import unittest
from unittest.mock import MagicMock, AsyncMock
from io import BytesIO

from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport, CurrentStoryItem
from jira_telegram_bot.adapters.services.current_stories_service import CurrentStoriesService
from jira_telegram_bot.settings.google_sheets_settings import GoogleSheetsConnectionSettings


class TestCurrentStoriesService(unittest.TestCase):
    """Test suite for CurrentStoriesService."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        # Create mock settings
        self.mock_settings = MagicMock(spec=GoogleSheetsConnectionSettings)
        self.mock_settings.token_path = "/path/to/token.json"
        self.mock_settings.sheet_id = "test_sheet_id"
        self.mock_settings.worksheet_name = "test_worksheet"
        
        self.service = CurrentStoriesService(self.mock_settings)
    
    async def test_save_to_google_sheets_success(self):
        """Test successful Google Sheets saving."""
        # Arrange
        story_item = CurrentStoryItem(
            issue_number="TEST-1",
            issue_name="Test Story",
            story_status="In Progress",
            remaining_hours=8.5,
            priority="High",
            assignees_abbr=["AK", "MM"],
            release="v1.0",
            label_feature="feature",
            epic_name="Test Epic",
            creation_date_jalali="1403/04/15",
            real_start_date_jalali="1403/04/16",
            complete_date_jalali=None,
            weeks_passed=2.5
        )
        
        report = CurrentStoriesReport(
            project_key="TEST",
            sprint_name="Sprint 1",
            stories=[story_item]
        )
        
        # Mock the Google client
        mock_google_client = AsyncMock()
        mock_google_client.write_to_worksheet = AsyncMock()
        self.service._google_client = mock_google_client
        
        # Act
        result = await self.service.save_to_google_sheets(
            report, "Sprint 1", "https://jira.example.com"
        )
        
        # Assert
        self.assertTrue(result)
        mock_google_client.write_to_worksheet.assert_called_once()
    
    def test_create_assignee_abbreviation_underscore_format(self):
        """Test assignee abbreviation creation with underscore format."""
        # Arrange
        assignee_name = "a_kazemi"
        
        # Act
        result = self.service.create_assignee_abbreviation(assignee_name)
        
        # Assert
        self.assertEqual(result, "AK")
    
    def test_create_assignee_abbreviation_multiple_underscores(self):
        """Test assignee abbreviation creation with multiple underscores."""
        # Arrange
        assignee_name = "john_due_developer"
        
        # Act
        result = self.service.create_assignee_abbreviation(assignee_name)
        
        # Assert
        self.assertEqual(result, "MM")
    
    def test_create_assignee_abbreviation_no_underscore(self):
        """Test assignee abbreviation creation without underscore."""
        # Arrange
        assignee_name = "john"
        
        # Act
        result = self.service.create_assignee_abbreviation(assignee_name)
        
        # Assert
        self.assertEqual(result, "JO")
    
    def test_create_assignee_abbreviation_empty_string(self):
        """Test assignee abbreviation creation with empty string."""
        # Arrange
        assignee_name = ""
        
        # Act
        result = self.service.create_assignee_abbreviation(assignee_name)
        
        # Assert
        self.assertEqual(result, "")
    
    def test_create_assignee_abbreviation_none(self):
        """Test assignee abbreviation creation with None."""
        # Arrange
        assignee_name = None
        
        # Act
        result = self.service.create_assignee_abbreviation(assignee_name)
        
        # Assert
        self.assertEqual(result, "")
    
    def test_create_assignee_abbreviation_single_character(self):
        """Test assignee abbreviation creation with single character."""
        # Arrange
        assignee_name = "a"
        
        # Act
        result = self.service.create_assignee_abbreviation(assignee_name)
        
        # Assert
        self.assertEqual(result, "A")


if __name__ == '__main__':
    unittest.main()
