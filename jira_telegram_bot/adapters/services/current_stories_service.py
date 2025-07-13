from __future__ import annotations

from typing import Dict, List, Optional
from io import BytesIO

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport
from jira_telegram_bot.use_cases.interfaces.current_stories_service_interface import CurrentStoriesServiceInterface
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.adapters.services.current_stories_google_sheets_enhancer import CurrentStoriesGoogleSheetsEnhancer
from jira_telegram_bot.settings.google_sheets_settings import GoogleSheetsConnectionSettings


class CurrentStoriesService(CurrentStoriesServiceInterface):
    """Implementation of the current stories service.
    
    This service handles current stories business logic and Google Sheets integration.
    """
    
    def __init__(self, google_sheets_settings: GoogleSheetsConnectionSettings,
                 google_client: Optional[GoogleSheetClient] = None
                 ):
        """Initialize the service.
        
        Args:
            google_sheets_settings: Google Sheets connection settings
        """
        self.google_sheets_settings = google_sheets_settings
        self._google_client = None
        self._enhancer = None
    
    
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
        """Save current stories report to Google Sheets with enhanced views.
        
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
            
            # Prepare rows data - we'll add hyperlinks after writing the data
            rows_data = []
            for story in report.stories:
                remaining = story.remaining_hours if story.remaining_hours is not None else 0
                
                row = [
                    story.issue_number,  # Plain text first, we'll convert to hyperlink later
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
            
            # Write basic data to Google Sheets
            await google_client.write_to_worksheet(
                worksheet_name=sprint_name,
                headers=headers,
                data=rows_data,
                clear_existing=True,
                sheet_id=self.google_sheets_settings.sheet_id
            )
            
            # Add hyperlinks to the Issue Link column
            await self._add_issue_hyperlinks(
                google_client, 
                sprint_name, 
                report.stories, 
                jira_base_url
            )
            
            # Add sheet enhancements using the enhancer
            enhancer = await self._get_enhancer()
            await enhancer.enhance_current_stories_sheet(
                self.google_sheets_settings.sheet_id,
                sprint_name,
                report
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
            self._google_client = GoogleSheetClient(self.google_sheets_settings)
        return self._google_client
    
    async def _add_issue_hyperlinks(
        self, 
        google_client: GoogleSheetClient, 
        sprint_name: str, 
        stories: List, 
        jira_base_url: str
    ):
        """Add hyperlinks to the Issue Link column.
        
        Args:
            google_client: The Google Sheets client
            sprint_name: Name of the worksheet
            stories: List of story items
            jira_base_url: Base URL for Jira issues
        """
        try:
            # Get the worksheet
            spreadsheet = google_client.client.open_by_key(self.google_sheets_settings.sheet_id)
            worksheet = spreadsheet.worksheet(sprint_name)
            
            # Add hyperlinks for each story (starting from row 2, since row 1 is headers)
            for i, story in enumerate(stories, start=2):
                issue_url = f"{jira_base_url}/browse/{story.issue_number}"
                google_client.write_hyperlink_formula(
                    worksheet, 
                    row=i, 
                    col=1,  # First column (Issue Link)
                    url=issue_url, 
                    text=story.issue_number
                )
            
            LOGGER.info(f"Added hyperlinks for {len(stories)} stories in {sprint_name}")
            
        except Exception as e:
            LOGGER.warning(f"Failed to add hyperlinks: {e}")
    
    async def _get_enhancer(self):
        """Get or create the current stories Google Sheets enhancer.
        
        Returns:
            CurrentStoriesGoogleSheetsEnhancer instance
        """
        if not hasattr(self, '_enhancer') or self._enhancer is None:
            google_client = await self._get_google_client()
            self._enhancer = CurrentStoriesGoogleSheetsEnhancer(google_client)
        return self._enhancer
