"""Google Sheets gateway implementation."""

from typing import List, Dict, Any

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.use_cases.interfaces.metrics.spreadsheet_gateway_interface import SpreadsheetGatewayInterface
from jira_telegram_bot.utils.exceptions import SpreadsheetError


class GoogleSheetsGateway(SpreadsheetGatewayInterface):
    """Implementation of SpreadsheetGatewayInterface using Google Sheets API."""
    
    def __init__(self, google_sheet_client: GoogleSheetClient):
        """Initialize the gateway.
        
        Args:
            google_sheet_client: Google Sheets client for API operations
        """
        self.client = google_sheet_client
    
    async def append_rows(self, sheet_id: str, range_name: str, rows: List[List[Any]]) -> bool:
        """Append rows to a Google Sheet.
        
        Args:
            sheet_id: Google Sheet ID
            range_name: Range to append to (e.g., "Sheet1!A:Z")
            rows: List of row data to append
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            SpreadsheetError: If operation fails
        """
        try:
            LOGGER.debug(f"Appending {len(rows)} rows to sheet {sheet_id}, range {range_name}")
            
            # Use the existing Google Sheet client
            result = await self.client.append_rows(
                spreadsheet_id=sheet_id,
                range_name=range_name,
                values=rows
            )
            
            if result:
                LOGGER.info(f"Successfully appended {len(rows)} rows to sheet {sheet_id}")
                return True
            else:
                LOGGER.error(f"Failed to append rows to sheet {sheet_id}")
                return False
                
        except Exception as e:
            LOGGER.error(f"Error appending rows to sheet {sheet_id}: {e}")
            raise SpreadsheetError(f"Failed to append rows: {e}")
    
    async def update_cells(self, sheet_id: str, range_name: str, values: List[List[Any]]) -> bool:
        """Update specific cells in a Google Sheet.
        
        Args:
            sheet_id: Google Sheet ID
            range_name: Range to update (e.g., "Sheet1!A1:C3")
            values: 2D list of values to update
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            SpreadsheetError: If operation fails
        """
        try:
            LOGGER.debug(f"Updating cells in sheet {sheet_id}, range {range_name}")
            
            # Use the existing Google Sheet client
            result = await self.client.update_cells(
                spreadsheet_id=sheet_id,
                range_name=range_name,
                values=values
            )
            
            if result:
                LOGGER.info(f"Successfully updated cells in sheet {sheet_id}, range {range_name}")
                return True
            else:
                LOGGER.error(f"Failed to update cells in sheet {sheet_id}")
                return False
                
        except Exception as e:
            LOGGER.error(f"Error updating cells in sheet {sheet_id}: {e}")
            raise SpreadsheetError(f"Failed to update cells: {e}")
    
    async def get_sheet_values(self, sheet_id: str, range_name: str) -> List[List[Any]]:
        """Get values from a Google Sheet range.
        
        Args:
            sheet_id: Google Sheet ID
            range_name: Range to read (e.g., "Sheet1!A1:Z100")
            
        Returns:
            2D list of cell values
            
        Raises:
            SpreadsheetError: If operation fails
        """
        try:
            LOGGER.debug(f"Getting values from sheet {sheet_id}, range {range_name}")
            
            # Use the existing Google Sheet client
            result = await self.client.get_values(
                spreadsheet_id=sheet_id,
                range_name=range_name
            )
            
            if result is not None:
                LOGGER.debug(f"Retrieved {len(result)} rows from sheet {sheet_id}")
                return result
            else:
                LOGGER.warning(f"No data found in sheet {sheet_id}, range {range_name}")
                return []
                
        except Exception as e:
            LOGGER.error(f"Error getting values from sheet {sheet_id}: {e}")
            raise SpreadsheetError(f"Failed to get sheet values: {e}")
    
    async def create_sheet(self, sheet_id: str, sheet_name: str) -> bool:
        """Create a new sheet within a spreadsheet.
        
        Args:
            sheet_id: Google Sheet ID
            sheet_name: Name for the new sheet
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            SpreadsheetError: If operation fails
        """
        try:
            LOGGER.debug(f"Creating new sheet '{sheet_name}' in spreadsheet {sheet_id}")
            
            # Use the existing Google Sheet client
            result = await self.client.create_sheet(
                spreadsheet_id=sheet_id,
                sheet_name=sheet_name
            )
            
            if result:
                LOGGER.info(f"Successfully created sheet '{sheet_name}' in spreadsheet {sheet_id}")
                return True
            else:
                LOGGER.error(f"Failed to create sheet '{sheet_name}' in spreadsheet {sheet_id}")
                return False
                
        except Exception as e:
            LOGGER.error(f"Error creating sheet '{sheet_name}' in spreadsheet {sheet_id}: {e}")
            raise SpreadsheetError(f"Failed to create sheet: {e}")
