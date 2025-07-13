from __future__ import annotations

from typing import Dict

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport


class CurrentStoriesGoogleSheetsEnhancer:
    """Service for enhancing current stories Google Sheets with business-specific features.
    
    This service implements business logic for formatting and enhancing
    Google Sheets specifically for current stories reports.
    """
    
    def __init__(self, google_client: GoogleSheetClient):
        """Initialize the enhancer.
        
        Args:
            google_client: Google Sheets client instance
        """
        self.google_client = google_client
    
    async def enhance_current_stories_sheet(
        self, 
        sheet_id: str, 
        worksheet_name: str, 
        report: CurrentStoriesReport
    ):
        """Apply current stories specific enhancements to the Google Sheet.
        
        Args:
            sheet_id: The Google Sheet ID
            worksheet_name: Name of the worksheet
            report: The current stories report
        """
        try:
            data_rows = len(report.stories)
            
            # 1. Freeze header row
            self.google_client.freeze_rows(sheet_id, worksheet_name, 1)
            
            # 2. Add auto filter
            self.google_client.add_auto_filter(sheet_id, worksheet_name, data_rows)
            
            # 3. Add conditional formatting for Story Status
            status_colors = {
                "Done": {"red": 0.8, "green": 1, "blue": 0.8},       # Light green
                "In Progress": {"red": 1, "green": 1, "blue": 0.8},  # Light yellow
                "To Do": {"red": 1, "green": 0.8, "blue": 0.8},      # Light red
                "Blocked": {"red": 1, "green": 0.6, "blue": 0.6}     # Red
            }
            self.google_client.add_conditional_formatting(
                sheet_id, worksheet_name, 2, status_colors  # Column 2 = Story Status
            )
            
            # 4. Add conditional formatting for Priority
            priority_colors = {
                "Highest": {"red": 0.9, "green": 0.2, "blue": 0.2},  # Dark red
                "High": {"red": 1, "green": 0.5, "blue": 0.5},       # Light red
                "Medium": {"red": 1, "green": 1, "blue": 0.5},       # Yellow
                "Low": {"red": 0.8, "green": 1, "blue": 0.8},        # Light green
                "Lowest": {"red": 0.6, "green": 1, "blue": 0.6}      # Green
            }
            self.google_client.add_conditional_formatting(
                sheet_id, worksheet_name, 4, priority_colors  # Column 4 = Priority
            )
            
            # 5. Create filter views for common use cases
            await self._create_current_stories_filter_views(sheet_id, worksheet_name)
            
            LOGGER.info(f"Enhanced current stories sheet: {worksheet_name}")
            
        except Exception as e:
            LOGGER.warning(f"Failed to enhance current stories sheet: {e}")
    
    async def _create_current_stories_filter_views(self, sheet_id: str, worksheet_name: str):
        """Create filter views specific to current stories.
        
        Args:
            sheet_id: The Google Sheet ID
            worksheet_name: Name of the worksheet
        """
        # Filter view 1: In Progress stories
        in_progress_criteria = {
            2: {  # Story Status column
                "condition": {
                    "type": "TEXT_EQ",
                    "values": [{"userEnteredValue": "In Progress"}]
                }
            }
        }
        self.google_client.create_filter_view(
            sheet_id, worksheet_name, "📋 In Progress Stories", in_progress_criteria
        )
        
        # Filter view 2: High Priority stories
        high_priority_criteria = {
            4: {  # Priority column
                "condition": {
                    "type": "TEXT_EQ",
                    "values": [{"userEnteredValue": "High"}]
                }
            }
        }
        self.google_client.create_filter_view(
            sheet_id, worksheet_name, "🔥 High Priority Stories", high_priority_criteria
        )
        
        # Filter view 3: Stories with remaining work
        remaining_work_criteria = {
            3: {  # Remaining hours column
                "condition": {
                    "type": "NUMBER_GREATER",
                    "values": [{"userEnteredValue": "0"}]
                }
            }
        }
        self.google_client.create_filter_view(
            sheet_id, worksheet_name, "⏱️ Stories with Remaining Work", remaining_work_criteria
        )
        
        # Filter view 4: Recently created stories (less than 2 weeks)
        recent_stories_criteria = {
            12: {  # Weeks passed column
                "condition": {
                    "type": "NUMBER_LESS_THAN_EQ",
                    "values": [{"userEnteredValue": "2"}]
                }
            }
        }
        self.google_client.create_filter_view(
            sheet_id, worksheet_name, "🆕 Recently Created Stories", recent_stories_criteria
        )
