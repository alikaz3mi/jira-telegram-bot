from __future__ import annotations

from typing import Dict, List, Optional
from io import BytesIO

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport
from jira_telegram_bot.use_cases.interfaces.current_stories_service_interface import CurrentStoriesServiceInterface
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.settings.google_sheets_settings import GoogleSheetsConnectionSettings


class CurrentStoriesService(CurrentStoriesServiceInterface):
    """Implementation of the current stories service.
    
    This service handles current stories business logic and Google Sheets integration.
    """
    
    def __init__(self, google_sheets_settings: GoogleSheetsConnectionSettings):
        """Initialize the service.
        
        Args:
            google_sheets_settings: Google Sheets connection settings
        """
        self.google_sheets_settings = google_sheets_settings
        self._google_client = None
    
    
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
    
    async def save_to_google_sheets(
        self, 
        report: CurrentStoriesReport, 
        sprint_name: str,
        jira_base_url: str
    ) -> bool:
        """Save current stories report to Google Sheets.
        
        Args:
            report: The current stories report data
            sprint_name: Name of the sprint (used as sheet name)
            jira_base_url: Base URL for creating Jira issue links
            
        Returns:
            True if successful, False otherwise
        """
        try:
            google_client = await self._get_google_client()
            
            # Prepare data for Google Sheets
            headers = [
                "Issue Link",
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
            
            # Prepare rows data with hyperlinks
            rows_data = []
            for story in report.stories:
                issue_url = f"{jira_base_url}/browse/{story.issue_number}"
                remaining = story.remaining_hours if story.remaining_hours is not None else 0
                
                row = [
                    f'=HYPERLINK("{issue_url}","{story.issue_number}")',  # Hyperlink formula
                    story.issue_name or "",
                    story.story_status or "",
                    remaining,
                    story.priority or "",
                    ", ".join(story.assignees_abbr),
                    story.release or "",
                    story.label_feature or "",
                    story.epic_name or "",
                    story.creation_date_jalali or "",
                    story.real_start_date_jalali or "",
                    story.complete_date_jalali or "",
                    story.weeks_passed or ""
                ]
                rows_data.append(row)
            
            # Write to Google Sheets
            await google_client.write_to_worksheet(
                worksheet_name=sprint_name,
                headers=headers,
                data=rows_data,
                clear_existing=True,
                sheet_id=self.google_sheets_settings.sheet_id
            )
            
            LOGGER.info(f"Successfully saved current stories report to Google Sheets: {sprint_name}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to save to Google Sheets: {e}")
            return False
    
    async def _get_google_client(self) -> GoogleSheetClient:
        """Get or create Google Sheets client.
        
        Returns:
            GoogleSheetClient instance
        """
        if self._google_client is None:
            self._google_client = GoogleSheetClient(self.google_sheets_settings.token_path)
        return self._google_client
