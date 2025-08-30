"""Google Sheet gateway interface for team evaluation."""

from abc import ABC, abstractmethod
from typing import List, Tuple

from jira_telegram_bot.entities.team_evaluation import TeamEvaluationRow


class GoogleSheetGatewayInterface(ABC):
    """Interface for Google Sheets operations specific to team evaluation."""

    @abstractmethod
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
        pass

    @abstractmethod
    async def ensure_headers(self, sheet_id: str, tab_name: str) -> None:
        """Ensure the sheet has the correct headers for team evaluation.
        
        Args:
            sheet_id: Google Sheet ID
            tab_name: Target tab name
            
        Raises:
            SpreadsheetError: If operation fails
        """
        pass
