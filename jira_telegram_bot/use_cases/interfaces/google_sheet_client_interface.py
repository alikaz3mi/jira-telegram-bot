from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class GoogleSheetClientInterface(ABC):
    """Interface for Google Sheets client operations."""
    
    @abstractmethod
    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        """Get worksheet by index.
        
        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_index: Index of the worksheet (default: 0)
            
        Returns:
            Worksheet object
        """
        pass
    
    @abstractmethod
    def get_worksheet_by_name(self, sheet_id: str, worksheet_name: str):
        """Get worksheet by name.
        
        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_name: Name of the worksheet
            
        Returns:
            Worksheet object
        """
        pass
    
    @abstractmethod
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
        pass
