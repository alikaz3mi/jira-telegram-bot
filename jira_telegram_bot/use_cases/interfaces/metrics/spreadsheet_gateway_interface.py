"""Spreadsheet gateway interface for Google Sheets operations."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class SpreadsheetGatewayInterface(ABC):
    """Interface for spreadsheet operations with Google Sheets."""
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
