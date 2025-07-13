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
    
    def add_conditional_formatting(
        self, 
        sheet_id: str, 
        worksheet_name: str, 
        column_index: int, 
        conditions: Dict[str, Dict[str, float]]
    ):
        """Add conditional formatting to a column.
        
        Args:
            sheet_id: The Google Sheet ID
            worksheet_name: Name of the worksheet
            column_index: Column index (0-based)
            conditions: Dict mapping values to color RGB dicts
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            requests = []
            for i, (value, color) in enumerate(conditions.items()):
                requests.append({
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{
                                "sheetId": worksheet.id,
                                "startRowIndex": 1,
                                "endRowIndex": 1000,
                                "startColumnIndex": column_index,
                                "endColumnIndex": column_index + 1
                            }],
                            "booleanRule": {
                                "condition": {
                                    "type": "TEXT_EQ",
                                    "values": [{"userEnteredValue": value}]
                                },
                                "format": {
                                    "backgroundColor": color
                                }
                            }
                        },
                        "index": i
                    }
                })
            
            if requests:
                spreadsheet.batch_update({"requests": requests})
                LOGGER.info(f"Added conditional formatting to column {column_index}")
                
        except Exception as e:
            LOGGER.error(f"Failed to add conditional formatting: {e}")
    
    def create_filter_view(
        self, 
        sheet_id: str, 
        worksheet_name: str, 
        view_name: str, 
        filter_criteria: Dict[int, Dict]
    ):
        """Create a filter view with specific criteria.
        
        Args:
            sheet_id: The Google Sheet ID
            worksheet_name: Name of the worksheet
            view_name: Name for the filter view
            filter_criteria: Dict mapping column indices to filter conditions
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            requests = [{
                "addFilterView": {
                    "filter": {
                        "title": view_name,
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 0,
                            "endRowIndex": 1000,
                            "startColumnIndex": 0,
                            "endColumnIndex": 13
                        },
                        "criteria": filter_criteria
                    }
                }
            }]
            
            spreadsheet.batch_update({"requests": requests})
            LOGGER.info(f"Created filter view: {view_name}")
            
        except Exception as e:
            LOGGER.error(f"Failed to create filter view: {e}")
    
    def freeze_rows(self, sheet_id: str, worksheet_name: str, frozen_row_count: int = 1):
        """Freeze header rows.
        
        Args:
            sheet_id: The Google Sheet ID
            worksheet_name: Name of the worksheet
            frozen_row_count: Number of rows to freeze
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            requests = [{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {
                            "frozenRowCount": frozen_row_count
                        }
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            }]
            
            spreadsheet.batch_update({"requests": requests})
            LOGGER.info(f"Froze {frozen_row_count} rows")
            
        except Exception as e:
            LOGGER.error(f"Failed to freeze rows: {e}")
    
    def add_auto_filter(self, sheet_id: str, worksheet_name: str, data_rows: int):
        """Add auto filter to the worksheet.
        
        Args:
            sheet_id: The Google Sheet ID
            worksheet_name: Name of the worksheet
            data_rows: Number of data rows
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            requests = [{
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
            }]
            
            spreadsheet.batch_update({"requests": requests})
            LOGGER.info("Added auto filter")
            
        except Exception as e:
            LOGGER.error(f"Failed to add auto filter: {e}")
