import unittest
from unittest.mock import MagicMock
from io import BytesIO

from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport, CurrentStoryItem
from jira_telegram_bot.adapters.services.current_stories_service import CurrentStoriesService


class TestCurrentStoriesService(unittest.TestCase):
    """Test suite for CurrentStoriesService."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        self.service = CurrentStoriesService()
    
    async def test_generate_stories_xlsx_success(self):
        """Test successful XLSX generation."""
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
        
        # Act
        result = await self.service.generate_stories_xlsx(report)
        
        # Assert
        self.assertIsInstance(result, BytesIO)
        self.assertGreater(result.getvalue().__len__(), 0)
    
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
        assignee_name = "m_mousavi_developer"
        
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
