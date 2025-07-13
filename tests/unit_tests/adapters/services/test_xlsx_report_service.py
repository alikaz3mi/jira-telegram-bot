import unittest
from io import BytesIO

from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport, CurrentStoryItem
from jira_telegram_bot.adapters.services.xlsx_report_service import XlsxReportService


class TestXlsxReportService(unittest.TestCase):
    """Test suite for XlsxReportService."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        self.service = XlsxReportService()
    
    async def test_generate_current_stories_xlsx_success(self):
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
        result = await self.service.generate_current_stories_xlsx(report)
        
        # Assert
        self.assertIsInstance(result, BytesIO)
        self.assertGreater(result.getvalue().__len__(), 0)
    
    async def test_generate_current_stories_xlsx_empty_stories(self):
        """Test XLSX generation with empty stories list."""
        # Arrange
        report = CurrentStoriesReport(
            project_key="TEST",
            sprint_name="Sprint 1",
            stories=[]
        )
        
        # Act
        result = await self.service.generate_current_stories_xlsx(report)
        
        # Assert
        self.assertIsInstance(result, BytesIO)
        self.assertGreater(result.getvalue().__len__(), 0)


if __name__ == '__main__':
    unittest.main()
