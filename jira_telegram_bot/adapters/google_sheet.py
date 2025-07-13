from __future__ import annotations

import asyncio
import unittest
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraServerRepository,
)
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings.google_sheets_settings import GoogleSheetsConnectionSettings
from jira_telegram_bot.use_cases.interfaces.google_sheet_client_interface import GoogleSheetClientInterface


class ISheetClient(ABC):
    """Interface for Google Sheets client implementations."""

    @abstractmethod
    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        """
        Return the worksheet object given a sheet id and an optional worksheet index.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_index: Index of the worksheet (default: 0)

        Returns:
            Worksheet object
        """
        pass

    @abstractmethod
    def get_worksheet_by_name(self, sheet_id: str, worksheet_name: str):
        """
        Return the worksheet object given a sheet id and worksheet name.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_name: Name of the worksheet

        Returns:
            Worksheet object
        """
        pass


class GoogleSheetClient(ISheetClient, GoogleSheetClientInterface):
    """Implementation of Google Sheets client using gspread."""

    def __init__(self, settings: GoogleSheetsConnectionSettings):
        """
        Initialize the Google Sheets client with authentication.

        Args:
            settings: Google Sheets connection settings
        """
        # Define the default scope if not provided.
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive",
        ]
        # Authenticate using the service account JSON token.
        try:
            self.settings = settings
            LOGGER.info(f"settings = {self.settings}")
            self.credentials = ServiceAccountCredentials.from_json_keyfile_name(
                settings.token_path,
                scope,
            )
            self.client = gspread.authorize(self.credentials)
            LOGGER.debug("Successfully authenticated with Google Sheets API")
        except Exception as e:
            LOGGER.error(f"Failed to authenticate with Google Sheets API: {e}")
            raise

    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        """
        Get worksheet by index.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_index: Index of the worksheet (default: 0)

        Returns:
            Worksheet object
        """
        try:
            # Open the spreadsheet by its ID.
            spreadsheet = self.client.open_by_key(sheet_id)
            return spreadsheet.get_worksheet(worksheet_index)
        except Exception as e:
            LOGGER.error(f"Error getting worksheet by index {worksheet_index}: {e}")
            raise

    def get_worksheet_by_name(self, sheet_id: str, worksheet_name: str):
        """
        Get worksheet by name.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_name: Name of the worksheet

        Returns:
            Worksheet object
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            return spreadsheet.worksheet(worksheet_name)
        except Exception as e:
            LOGGER.error(f"Error getting worksheet by name '{worksheet_name}': {e}")
            raise

    async def write_to_worksheet(
        self,
        worksheet_name: str,
        headers: List[str],
        data: List[List[Any]],
        clear_existing: bool = True,
        sheet_id: Optional[str] = None,
    ):
        """Write data to a worksheet with the given name.

        Args:
            worksheet_name: Name of the worksheet
            headers: List of header names
            data: List of rows, where each row is a list of values
            clear_existing: Whether to clear existing data first
            sheet_id: Optional sheet ID override
        """
        try:
            # Use provided sheet_id (must be provided since no settings are available here)
            if not sheet_id:
                raise ValueError("sheet_id must be provided")
            spreadsheet = self.client.open_by_key(sheet_id)

            # Try to get existing worksheet, or create new one
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
                if clear_existing:
                    worksheet.clear()
            except Exception:
                # Worksheet doesn't exist, create it
                worksheet = spreadsheet.add_worksheet(
                    title=worksheet_name, rows=1000, cols=20
                )

            # Write headers
            if headers:
                worksheet.append_row(headers)

            # Write data rows
            for row in data:
                worksheet.append_row(row)

            LOGGER.info(
                f"Successfully wrote {len(data)} rows to worksheet '{worksheet_name}'",
            )

        except Exception as e:
            LOGGER.error(f"Error writing to worksheet '{worksheet_name}': {e}")
            raise

    async def add_sheet_enhancements(
        self, 
        sheet_id: str,
        worksheet_name: str, 
        data_rows: int
    ):
        """Add enhancements like filters, conditional formatting, and freeze panes.
        
        Args:
            sheet_id: The Google Sheet ID
            worksheet_name: Name of the worksheet
            data_rows: Number of data rows
        """
        try:
            # Get the worksheet
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # Prepare batch requests
            requests = []
            
            # 1. Freeze header row
            requests.append({
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {
                            "frozenRowCount": 1
                        }
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            })
            
            # 2. Add auto filter
            requests.append({
                "setBasicFilter": {
                    "filter": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 0,
                            "endRowIndex": data_rows + 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 13
                        }
                    }
                }
            })
            
            # 3. Add conditional formatting for Story Status
            self._add_status_conditional_formatting(requests, worksheet.id, data_rows)
            
            # 4. Add conditional formatting for Priority
            self._add_priority_conditional_formatting(requests, worksheet.id, data_rows)
            
            # 5. Create filter views for common groupings
            self._create_filter_views(requests, worksheet.id, data_rows)
            
            # Execute all requests
            if requests:
                spreadsheet.batch_update({"requests": requests})
                LOGGER.info(f"Added enhancements to worksheet: {worksheet_name}")
                
        except Exception as e:
            LOGGER.warning(f"Failed to add sheet enhancements: {e}")

    def _add_status_conditional_formatting(self, requests: list, sheet_id: int, data_rows: int):
        """Add conditional formatting for Story Status column.
        
        Args:
            requests: List to append requests to
            sheet_id: ID of the worksheet
            data_rows: Number of data rows
        """
        status_colors = {
            "Done": {"red": 0.8, "green": 1, "blue": 0.8},       # Light green
            "In Progress": {"red": 1, "green": 1, "blue": 0.8},  # Light yellow
            "To Do": {"red": 1, "green": 0.8, "blue": 0.8},      # Light red
            "Blocked": {"red": 1, "green": 0.6, "blue": 0.6}     # Red
        }
        
        for i, (status, color) in enumerate(status_colors.items()):
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": data_rows + 1,
                            "startColumnIndex": 2,  # Story Status column
                            "endColumnIndex": 3
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": status}]
                            },
                            "format": {
                                "backgroundColor": color
                            }
                        }
                    },
                    "index": i
                }
            })

    def _add_priority_conditional_formatting(self, requests: list, sheet_id: int, data_rows: int):
        """Add conditional formatting for Priority column.
        
        Args:
            requests: List to append requests to
            sheet_id: ID of the worksheet
            data_rows: Number of data rows
        """
        priority_colors = {
            "Highest": {"red": 0.9, "green": 0.2, "blue": 0.2},  # Dark red
            "High": {"red": 1, "green": 0.5, "blue": 0.5},       # Light red
            "Medium": {"red": 1, "green": 1, "blue": 0.5},       # Yellow
            "Low": {"red": 0.8, "green": 1, "blue": 0.8},        # Light green
            "Lowest": {"red": 0.6, "green": 1, "blue": 0.6}      # Green
        }
        
        status_color_count = 4  # Number of status colors to offset priority colors
        
        for i, (priority, color) in enumerate(priority_colors.items()):
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": data_rows + 1,
                            "startColumnIndex": 4,  # Priority column
                            "endColumnIndex": 5
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": priority}]
                            },
                            "format": {
                                "backgroundColor": color
                            }
                        }
                    },
                    "index": i + status_color_count
                }
            })

    def _create_filter_views(self, requests: list, sheet_id: int, data_rows: int):
        """Create predefined filter views for common use cases.
        
        Args:
            requests: List to append filter view requests to
            sheet_id: ID of the worksheet
            data_rows: Number of data rows
        """
        # Filter view 1: In Progress stories
        requests.append({
            "addFilterView": {
                "filter": {
                    "title": "📋 In Progress Stories",
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": data_rows + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 13
                    },
                    "criteria": {
                        2: {  # Story Status column
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": "In Progress"}]
                            }
                        }
                    }
                }
            }
        })
        
        # Filter view 2: High Priority stories
        requests.append({
            "addFilterView": {
                "filter": {
                    "title": "🔥 High Priority Stories",
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": data_rows + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 13
                    },
                    "criteria": {
                        4: {  # Priority column
                            "condition": {
                                "type": "ONE_OF_LIST",
                                "values": [
                                    {"userEnteredValue": "Highest"},
                                    {"userEnteredValue": "High"}
                                ]
                            }
                        }
                    }
                }
            }
        })
        
        # Filter view 3: Stories with remaining work
        requests.append({
            "addFilterView": {
                "filter": {
                    "title": "⏱️ Stories with Remaining Work",
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": data_rows + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 13
                    },
                    "criteria": {
                        3: {  # Remaining hours column
                            "condition": {
                                "type": "NUMBER_GREATER",
                                "values": [{"userEnteredValue": "0"}]
                            }
                        }
                    }
                }
            }
        })
        
        # Filter view 4: Recently created stories (less than 2 weeks)
        requests.append({
            "addFilterView": {
                "filter": {
                    "title": "🆕 Recently Created Stories",
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": data_rows + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 13
                    },
                    "criteria": {
                        12: {  # Weeks passed column
                            "condition": {
                                "type": "NUMBER_LESS_THAN_EQ",
                                "values": [{"userEnteredValue": "2"}]
                            }
                        }
                    }
                }
            }
        })

    def write_hyperlink_formula(self, worksheet, row: int, col: int, url: str, text: str):
        """Write a hyperlink formula to a specific cell.
        
        Args:
            worksheet: The worksheet object
            row: Row number (1-indexed)
            col: Column number (1-indexed)
            url: The URL to link to
            text: The display text for the link
        """
        try:
            # Use the proper hyperlink formula without quotes to avoid text interpretation
            formula = f'=HYPERLINK("{url}","{text}")'
            worksheet.update_cell(row, col, formula)
        except Exception as e:
            LOGGER.error(f"Failed to write hyperlink formula: {e}")
            # Fallback to plain text if formula fails
            worksheet.update_cell(row, col, text)
