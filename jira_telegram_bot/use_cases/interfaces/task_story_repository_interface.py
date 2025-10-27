"""Interface for task/story Google Sheets repository operations."""
from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity


class TaskStoryRepositoryInterface(ABC):
    """Interface for task/story Google Sheets repository operations."""

    @abstractmethod
    async def get_sheet_features(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        data_range: str,
    ) -> List[SynthPMFeatureEntity]:
        """Get all feature rows from Google Sheets.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID.
            sheet_name: Name of the sheet to read from.
            data_range: Column range to read (e.g., 'A:AW').

        Returns:
            List of SynthPMFeatureEntity entities.
        """
        pass

    @abstractmethod
    async def update_sheet_feature(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        updates: Dict[str, any],
    ) -> bool:
        """Update a specific feature row in Google Sheets.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID.
            sheet_name: Name of the sheet.
            row_number: Row number to update.
            updates: Dictionary of field updates.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def extract_issue_keys_from_features(
        self,
        features: List[SynthPMFeatureEntity],
    ) -> List[str]:
        """Extract developer board issue keys from feature entities.

        Args:
            features: List of SynthPMFeatureEntity entities.

        Returns:
            List of developer board issue keys.
        """
        pass
