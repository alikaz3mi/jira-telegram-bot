from __future__ import annotations

from abc import ABC, abstractmethod


class GoogleSheetClientInterface(ABC):
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