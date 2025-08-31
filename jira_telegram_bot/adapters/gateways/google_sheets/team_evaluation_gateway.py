"""Team evaluation Google Sheets gateway implementation."""

import asyncio
from typing import List, Tuple, Dict, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.entities.team_evaluation import TeamEvaluationRow
from jira_telegram_bot.use_cases.interfaces.google_sheet_gateway_interface import GoogleSheetGatewayInterface
from jira_telegram_bot.utils.exceptions import SpreadsheetError


class TeamEvaluationGoogleSheetGateway(GoogleSheetGatewayInterface):
    """Google Sheets gateway implementation for team evaluation."""

    def __init__(self, google_sheet_client: GoogleSheetClient):
        """Initialize the gateway.
        
        Args:
            google_sheet_client: Google Sheets client for API operations
        """
        self.client = google_sheet_client

    async def upsert_rows(
        self,
        sheet_id: str,
        tab_name: str,
        rows: List[TeamEvaluationRow],
        upsert_keys: Tuple[str, str, str]
    ) -> None:
        """Upsert team evaluation rows in a Google Sheet.
        
        Args:
            sheet_id: Google Sheet ID
            tab_name: Target tab name
            rows: List of team evaluation rows to upsert
            upsert_keys: Tuple of column names to use as unique keys
            
        Raises:
            SpreadsheetError: If operation fails
        """
        try:
            LOGGER.info(f"Upserting {len(rows)} rows to sheet {sheet_id}, tab '{tab_name}'")
            LOGGER.debug(f"Upsert keys: {upsert_keys}")
            
            # Ensure headers exist
            await self.ensure_headers(sheet_id, tab_name)
            
            # Get existing data to find rows to update
            existing_data = await self._get_existing_data(sheet_id, tab_name)
            
            # Build lookup for existing rows
            existing_lookup = self._build_row_lookup(existing_data, upsert_keys)
            
            # Separate updates and inserts
            updates = []
            inserts = []
            
            for row in rows:
                row_data = row.to_sheet_row()
                key = self._extract_row_key(row, upsert_keys)
                
                if key in existing_lookup:
                    # Update existing row
                    row_index = existing_lookup[key]
                    updates.append((row_index + 2, row_data))  # +2 for 1-based + header
                else:
                    # Insert new row
                    inserts.append(row_data)
            
            # Perform updates
            if updates:
                await self._batch_update_rows(sheet_id, tab_name, updates)
                LOGGER.info(f"Updated {len(updates)} existing rows")
            
            # Perform inserts
            if inserts:
                LOGGER.info(f"Appending {len(inserts)} new rows to tab '{tab_name}'")
                for i, row_data in enumerate(inserts[:3]):  # Log first 3 rows for debugging
                    LOGGER.debug(f"Row {i+1}: {row_data}")
                await self._append_rows(sheet_id, tab_name, inserts)
                LOGGER.info(f"Inserted {len(inserts)} new rows")
            else:
                LOGGER.info("No new rows to insert")
                
        except Exception as e:
            LOGGER.error(f"Error upserting rows to sheet {sheet_id}: {e}")
            raise SpreadsheetError(f"Failed to upsert rows: {e}")

    async def ensure_headers(self, sheet_id: str, tab_name: str) -> None:
        """Ensure the sheet has the correct headers for team evaluation.
        
        Args:
            sheet_id: Google Sheet ID
            tab_name: Target tab name
            
        Raises:
            SpreadsheetError: If operation fails
        """
        try:
            headers = TeamEvaluationRow.get_sheet_headers()
            range_name = f"{tab_name}!A1:{chr(ord('A') + len(headers) - 1)}1"
            
            # Check if headers already exist
            try:
                existing_data = await self.client.get_values(sheet_id, range_name)
                if existing_data and set(existing_data[0]) == set(headers):
                    LOGGER.debug("Headers already exist and are correct")
                    return
            except Exception:
                # If can't read, assume headers don't exist
                pass
            
            # Set headers
            await self.client.update_cells(
                spreadsheet_id=sheet_id,
                range_name=range_name,
                values=[headers]
            )
            LOGGER.info(f"Set headers for sheet {sheet_id}, tab {tab_name}")
            
        except Exception as e:
            LOGGER.error(f"Error ensuring headers for sheet {sheet_id}: {e}")
            raise SpreadsheetError(f"Failed to ensure headers: {e}")

    async def _get_existing_data(self, sheet_id: str, tab_name: str) -> List[List[str]]:
        """Get all existing data from the sheet.
        
        Args:
            sheet_id: Google Sheet ID
            tab_name: Target tab name
            
        Returns:
            List of rows (excluding header)
        """
        try:
            # Get all data starting from row 2 (skip headers)
            range_name = f"{tab_name}!A2:Z"
            data = await self.client.get_values(sheet_id, range_name)
            return data or []
        except Exception as e:
            LOGGER.warning(f"Could not read existing data from sheet: {e}")
            return []

    def _build_row_lookup(self, data: List[List[str]], upsert_keys: Tuple[str, str, str]) -> Dict[Tuple[str, str, str], int]:
        """Build lookup dictionary for existing rows.
        
        Args:
            data: Existing sheet data
            upsert_keys: Column names to use as keys
            
        Returns:
            Dictionary mapping key tuples to row indices
        """
        lookup = {}
        headers = TeamEvaluationRow.get_sheet_headers()
        
        # Find column indices for upsert keys
        key_indices = []
        for key in upsert_keys:
            try:
                key_indices.append(headers.index(key))
            except ValueError:
                LOGGER.error(f"Upsert key '{key}' not found in headers")
                return {}
        
        # Build lookup
        for i, row in enumerate(data):
            if len(row) > max(key_indices):
                key_values = tuple(row[idx] for idx in key_indices)
                lookup[key_values] = i
        
        return lookup

    def _extract_row_key(self, row: TeamEvaluationRow, upsert_keys: Tuple[str, str, str]) -> Tuple[str, str, str]:
        """Extract key tuple from a team evaluation row.
        
        Args:
            row: Team evaluation row
            upsert_keys: Column names to use as keys
            
        Returns:
            Tuple of key values
        """
        # Map header names to row attributes
        attr_map = {
            "توسعه دهنده": row.developer_name,
            "پروژه": row.project,
            "اسپرینت": row.sprint
        }
        
        return tuple(attr_map.get(key, "") for key in upsert_keys)

    async def _batch_update_rows(self, sheet_id: str, tab_name: str, updates: List[Tuple[int, List[str]]]) -> None:
        """Batch update multiple rows.
        
        Args:
            sheet_id: Google Sheet ID
            tab_name: Target tab name
            updates: List of (row_number, row_data) tuples
        """
        # Group updates in batches of 100 to avoid API limits
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            
            # Process batch
            for row_num, row_data in batch:
                range_name = f"{tab_name}!A{row_num}:{chr(ord('A') + len(row_data) - 1)}{row_num}"
                await self.client.update_cells(
                    spreadsheet_id=sheet_id,
                    range_name=range_name,
                    values=[row_data]
                )
            
            # Add small delay between batches to respect rate limits
            if i + batch_size < len(updates):
                await asyncio.sleep(0.1)

    async def _append_rows(self, sheet_id: str, tab_name: str, rows: List[List[str]]) -> None:
        """Append new rows to the sheet within the table structure.
        
        Args:
            sheet_id: Google Sheet ID
            tab_name: Target tab name
            rows: List of row data to append
        """
        # Batch appends in groups of 500
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            
            # Find the next available row within the table structure
            await self._insert_rows_in_table(sheet_id, tab_name, batch)
            
            # Add small delay between batches
            if i + batch_size < len(rows):
                await asyncio.sleep(0.1)

    async def _insert_rows_in_table(self, sheet_id: str, tab_name: str, rows: List[List[str]]) -> None:
        """Insert rows within the existing table structure.
        
        Args:
            sheet_id: Google Sheet ID
            tab_name: Target tab name
            rows: List of row data to insert
        """
        try:
            # Get all existing data to find the table range
            existing_data = await self._get_existing_data(sheet_id, tab_name)
            
            # Find the next row to insert (right after existing data)
            next_row = len(existing_data) + 2  # +1 for header, +1 for next row
            
            # Insert each row at the calculated position
            for i, row_data in enumerate(rows):
                row_num = next_row + i
                range_name = f"{tab_name}!A{row_num}:{chr(ord('A') + len(row_data) - 1)}{row_num}"
                
                await self.client.update_cells(
                    spreadsheet_id=sheet_id,
                    range_name=range_name,
                    values=[row_data]
                )
                
                LOGGER.debug(f"Inserted row at {range_name}: {row_data}")
            
            LOGGER.info(f"Successfully inserted {len(rows)} rows within table structure")
            
        except Exception as e:
            LOGGER.error(f"Error inserting rows in table: {e}")
            # Fallback to simple append
            range_name = f"{tab_name}!A:Z"
            await self.client.append_rows(
                spreadsheet_id=sheet_id,
                range_name=range_name,
                values=rows
            )
