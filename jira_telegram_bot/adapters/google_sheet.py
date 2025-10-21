from __future__ import annotations

import asyncio
import time
import unittest
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import gspread
from gspread.exceptions import APIError
from oauth2client.service_account import ServiceAccountCredentials

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraServerRepository,
)
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings.google_sheets_settings import (
    GoogleSheetsConnectionSettings,
)
from jira_telegram_bot.use_cases.interfaces.google_sheet_client_interface import (
    GoogleSheetClientInterface,
)


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
            # Initialize cache for get_values method
            self._values_cache: Dict[str, Tuple[List[List[Any]], float]] = {}
            self._cache_ttl = 60  # 1 minute cache TTL
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
                    title=worksheet_name,
                    rows=1000,
                    cols=20,
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

    async def append_rows(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
    ) -> bool:
        """Append rows to a Google Sheet with rate limiting.

        Args:
            spreadsheet_id: The Google Sheet ID
            range_name: Range to append to (e.g., "Sheet1!A:Z")
            values: List of row data to append

        Returns:
            True if successful, False otherwise
        """
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            # Extract sheet name from range
            sheet_name = range_name.split("!")[0] if "!" in range_name else "Sheet1"
            worksheet = spreadsheet.worksheet(sheet_name)

            # Append rows one by one with rate limiting to avoid quota issues
            # Google Sheets API limit: 60 writes per minute
            # With 1.5 second delay: 40 writes per minute (safe margin)
            total_rows = len(values)
            
            for idx, row in enumerate(values, start=1):
                LOGGER.info(
                    f"Appending row {idx}/{total_rows} to {spreadsheet_id}"
                )
                
                worksheet.append_row(row, value_input_option='USER_ENTERED')
                
                # Rate limiting: wait 1.5 seconds between each append
                if idx < total_rows:
                    await asyncio.sleep(1.5)

            LOGGER.info(f"Successfully appended {total_rows} rows to {spreadsheet_id}")
            return True

        except Exception as e:
            LOGGER.error(f"Error appending rows to {spreadsheet_id}: {e}")
            return False

    async def update_cells(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
    ) -> bool:
        """Update specific cells in a Google Sheet.

        Args:
            spreadsheet_id: The Google Sheet ID
            range_name: Range to update (e.g., "Sheet1!A1:C3")
            values: 2D list of values to update

        Returns:
            True if successful, False otherwise
        """
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            # Extract sheet name from range
            sheet_name = range_name.split("!")[0] if "!" in range_name else "Sheet1"
            worksheet = spreadsheet.worksheet(sheet_name)

            # Update the range with USER_ENTERED to support formulas
            worksheet.update(range_name, values, value_input_option='USER_ENTERED')

            LOGGER.info(
                f"Successfully updated cells in {spreadsheet_id}, range {range_name}",
            )
            return True

        except APIError as e:
            # Handle APIError - retry with just the range part after the sheet name
            sheet_range = range_name.split("!")[1] if "!" in range_name else range_name
            LOGGER.warning(
                f"API error updating cells in {spreadsheet_id}, range {range_name} (retrying with: {sheet_range}): {e}",
            )
            worksheet.update(sheet_range, values, value_input_option='USER_ENTERED')
            return True

        except Exception as e:
            LOGGER.error(f"Error updating cells in {spreadsheet_id}: {e}")
            return False

    def _get_cache_key(self, spreadsheet_id: str, range_name: str) -> str:
        """Generate cache key for get_values method.

        Args:
            spreadsheet_id: The Google Sheet ID
            range_name: Range to read

        Returns:
            Cache key string
        """
        return f"{spreadsheet_id}:{range_name}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid.

        Args:
            cache_key: The cache key to check

        Returns:
            True if cache is valid, False otherwise
        """
        if cache_key not in self._values_cache:
            return False
        
        _, timestamp = self._values_cache[cache_key]
        return time.time() - timestamp < self._cache_ttl

    def _get_from_cache(self, cache_key: str) -> Optional[List[List[Any]]]:
        """Get values from cache if valid.

        Args:
            cache_key: The cache key

        Returns:
            Cached values if valid, None otherwise
        """
        if self._is_cache_valid(cache_key):
            values, _ = self._values_cache[cache_key]
            LOGGER.debug(f"Cache hit for key: {cache_key}")
            return values
        return None

    def _set_cache(self, cache_key: str, values: List[List[Any]]) -> None:
        """Set values in cache.

        Args:
            cache_key: The cache key
            values: Values to cache
        """
        self._values_cache[cache_key] = (values, time.time())
        LOGGER.debug(f"Cached values for key: {cache_key}")

    def _cleanup_expired_cache(self) -> None:
        """Remove expired entries from cache to prevent memory leaks."""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._values_cache.items()
            if current_time - timestamp >= self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._values_cache[key]
        
        if expired_keys:
            LOGGER.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def clear_cache(self) -> None:
        """Clear all cached values."""
        self._values_cache.clear()
        LOGGER.debug("Cleared all cached values")

    async def get_values(
        self,
        spreadsheet_id: str,
        range_name: str,
    ) -> List[List[Any]]:
        """Get values from a Google Sheet range.

        Args:
            spreadsheet_id: The Google Sheet ID
            range_name: Range to read (e.g., "Sheet1!A1:Z100")

        Returns:
            2D list of cell values
        """
        # Cleanup expired cache entries periodically
        self._cleanup_expired_cache()
        
        # Check cache first
        cache_key = self._get_cache_key(spreadsheet_id, range_name)
        cached_values = self._get_from_cache(cache_key)
        if cached_values is not None:
            return cached_values

        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            # Extract sheet name from range
            sheet_name = range_name.split("!")[0] if "!" in range_name else "Sheet1"
            worksheet = spreadsheet.worksheet(sheet_name)

            # Get all values from the range
            if "!" in range_name:
                cell_range = range_name.split("!")[1]
                values = worksheet.get(cell_range)
            else:
                values = worksheet.get_all_values()

            # Cache the results
            self._set_cache(cache_key, values)
            
            LOGGER.debug(f"Retrieved {len(values)} rows from {spreadsheet_id}")
            return values

        except Exception as e:
            LOGGER.error(f"Error getting values from {spreadsheet_id}: {e}")
            return []

    async def create_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
    ) -> bool:
        """Create a new sheet within a spreadsheet.

        Args:
            spreadsheet_id: The Google Sheet ID
            sheet_name: Name for the new sheet

        Returns:
            True if successful, False otherwise
        """
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            # Add new worksheet
            worksheet = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=1000,
                cols=26,
            )

            LOGGER.info(
                f"Successfully created sheet '{sheet_name}' in {spreadsheet_id}",
            )
            return True

        except Exception as e:
            LOGGER.error(
                f"Error creating sheet '{sheet_name}' in {spreadsheet_id}: {e}",
            )
            return False

    def write_hyperlink_formula(
        self,
        worksheet,
        row: int,
        col: int,
        url: str,
        text: str,
    ):
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
        conditions: Dict[str, Dict[str, float]],
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
                requests.append(
                    {
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [
                                    {
                                        "sheetId": worksheet.id,
                                        "startRowIndex": 1,
                                        "endRowIndex": 1000,
                                        "startColumnIndex": column_index,
                                        "endColumnIndex": column_index + 1,
                                    },
                                ],
                                "booleanRule": {
                                    "condition": {
                                        "type": "TEXT_EQ",
                                        "values": [{"userEnteredValue": value}],
                                    },
                                    "format": {
                                        "backgroundColor": color,
                                    },
                                },
                            },
                            "index": i,
                        },
                    },
                )

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
        filter_criteria: Dict[int, Dict],
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

            requests = [
                {
                    "addFilterView": {
                        "filter": {
                            "title": view_name,
                            "range": {
                                "sheetId": worksheet.id,
                                "startRowIndex": 0,
                                "endRowIndex": 1000,
                                "startColumnIndex": 0,
                                "endColumnIndex": 13,
                            },
                            "criteria": filter_criteria,
                        },
                    },
                },
            ]

            spreadsheet.batch_update({"requests": requests})
            LOGGER.info(f"Created filter view: {view_name}")

        except Exception as e:
            LOGGER.error(f"Failed to create filter view: {e}")

    def freeze_rows(
        self,
        sheet_id: str,
        worksheet_name: str,
        frozen_row_count: int = 1,
    ):
        """Freeze header rows.

        Args:
            sheet_id: The Google Sheet ID
            worksheet_name: Name of the worksheet
            frozen_row_count: Number of rows to freeze
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)

            requests = [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": worksheet.id,
                            "gridProperties": {
                                "frozenRowCount": frozen_row_count,
                            },
                        },
                        "fields": "gridProperties.frozenRowCount",
                    },
                },
            ]

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

            requests = [
                {
                    "setBasicFilter": {
                        "filter": {
                            "range": {
                                "sheetId": worksheet.id,
                                "startRowIndex": 0,
                                "endRowIndex": data_rows + 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": 13,
                            },
                        },
                    },
                },
            ]

            spreadsheet.batch_update({"requests": requests})
            LOGGER.info("Added auto filter")

        except Exception as e:
            LOGGER.error(f"Failed to add auto filter: {e}")
