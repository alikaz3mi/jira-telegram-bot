from __future__ import annotations

from typing import Dict, List, Optional
from io import BytesIO
import xlsxwriter

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport
from jira_telegram_bot.use_cases.interfaces.current_stories_service_interface import CurrentStoriesServiceInterface


class CurrentStoriesService(CurrentStoriesServiceInterface):
    """Implementation of the current stories service.
    
    This service handles current stories operations by implementing
    the CurrentStoriesServiceInterface.
    """
    
    def __init__(self):
        """Initialize the service."""
        pass
    
    async def generate_stories_xlsx(self, report: CurrentStoriesReport) -> BytesIO:
        """Generate XLSX file from current stories report.
        
        Args:
            report: The current stories report data
            
        Returns:
            BytesIO containing the XLSX file
        """
        output_stream = BytesIO()
        
        workbook = xlsxwriter.Workbook(output_stream, {"in_memory": True})
        worksheet = workbook.add_worksheet("Current Stories")
        
        self._setup_worksheet_formatting(workbook, worksheet)
        self._write_headers(worksheet)
        self._write_story_data(worksheet, report.stories)
        
        workbook.close()
        output_stream.seek(0)
        
        return output_stream
    
    def create_assignee_abbreviation(self, assignee_name: str) -> str:
        """Create abbreviation from assignee name.
        
        Args:
            assignee_name: Full assignee name (e.g., 'a_kazemi')
            
        Returns:
            Abbreviated name (e.g., 'AK')
        """
        if not assignee_name:
            return ""
        
        parts = assignee_name.split('_')
        if len(parts) >= 2:
            return ''.join([part[0].upper() for part in parts[:2]])
        else:
            return assignee_name[:2].upper()
    
    def _setup_worksheet_formatting(self, workbook, worksheet):
        """Setup worksheet formatting and column widths.
        
        Args:
            workbook: XlsxWriter workbook
            worksheet: XlsxWriter worksheet
        """
        worksheet.set_column('A:A', 15)  # Issue number column
        worksheet.set_column('B:B', 40)  # Issue name column
        worksheet.set_column('C:C', 15)  # Story status column
        worksheet.set_column('D:D', 12)  # Remaining hours column
        worksheet.set_column('E:E', 12)  # Priority column
        worksheet.set_column('F:F', 15)  # Assignee column
        worksheet.set_column('G:G', 15)  # Release column
        worksheet.set_column('H:H', 25)  # Label/Feature column
        worksheet.set_column('I:I', 20)  # Epic column
        worksheet.set_column('J:J', 15)  # Creation date column
        worksheet.set_column('K:K', 15)  # Real start date column
        worksheet.set_column('L:L', 15)  # Complete date column
        worksheet.set_column('M:M', 12)  # Weeks passed column
    
    def _write_headers(self, worksheet):
        """Write header row to worksheet.
        
        Args:
            worksheet: XlsxWriter worksheet
        """
        headers = [
            "Issue Number",
            "Issue Name",
            "Story Status",
            "Remaining",
            "Priority",
            "Assignee (abbr.)",
            "Release",
            "Label / Feature",
            "Epic",
            "Creation Date",
            "Real Start Date",
            "Complete Date",
            "Weeks Passed"
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
    
    def _write_story_data(self, worksheet, stories):
        """Write story data to worksheet.
        
        Args:
            worksheet: XlsxWriter worksheet
            stories: List of CurrentStoryItem objects
        """
        for row, story in enumerate(stories, 1):
            worksheet.write(row, 0, story.issue_number)
            worksheet.write(row, 1, story.issue_name)
            worksheet.write(row, 2, story.story_status or "")
            # Write remaining hours as number only (no 'h' suffix)
            remaining = story.remaining_hours if story.remaining_hours is not None else 0
            worksheet.write(row, 3, remaining)
            worksheet.write(row, 4, story.priority or "")
            worksheet.write(row, 5, ", ".join(story.assignees_abbr))
            worksheet.write(row, 6, story.release or "")
            worksheet.write(row, 7, story.label_feature or "")
            worksheet.write(row, 8, story.epic_name or "")
            worksheet.write(row, 9, story.creation_date_jalali or "")
            worksheet.write(row, 10, story.real_start_date_jalali or "")
            worksheet.write(row, 11, story.complete_date_jalali or "")
            worksheet.write(row, 12, story.weeks_passed or "")
