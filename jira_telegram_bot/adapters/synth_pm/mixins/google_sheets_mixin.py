"""Mixin for Google Sheets operations in SynthPM."""
from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.entities.synth_pm.services import SynthPMColumnMappingService
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings


class GoogleSheetsMixin:
    """Mixin for Google Sheets operations."""

    google_sheet_client: GoogleSheetClient
    settings: SynthPMSettings

    async def get_sheet_values(self, range_name: str) -> List[List[str]]:
        """Get values from Google Sheet.

        Args:
            range_name: Range to retrieve (e.g., "A:Z")

        Returns:
            List of rows from the sheet
        """
        try:
            values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                range_name,
            )
            return values or []
        except Exception as e:
            LOGGER.error(f"Error retrieving sheet values from {range_name}: {e}")
            return []

    async def update_sheet_cell(
        self,
        worksheet_name: str,
        row_number: int,
        field_name: str,
        value: Any,
        headers: List[str],
    ) -> bool:
        """Update a single cell in Google Sheet.

        Args:
            worksheet_name: Name of the worksheet
            row_number: Row number to update
            field_name: Field name to update
            value: New value
            headers: Sheet headers for column mapping

        Returns:
            True if successful, False otherwise
        """
        try:
            column_mapping = SynthPMColumnMappingService.create_column_mapping(headers)

            if field_name not in column_mapping:
                LOGGER.warning(f"Field {field_name} not found in column mapping")
                return False

            col_idx = column_mapping[field_name]
            col_letter = SynthPMColumnMappingService.number_to_column_letter(
                col_idx + 1,
            )
            range_name = f"{worksheet_name}!{col_letter}{row_number}"

            success = await self.google_sheet_client.update_cells(
                self.settings.google_sheets_id,
                range_name,
                [[str(value) if value is not None else ""]],
            )

            if not success:
                LOGGER.error(f"Failed to update field {field_name} in row {row_number}")
                return False

            return True

        except Exception as e:
            LOGGER.error(
                f"Error updating sheet cell {field_name} in row {row_number}: {e}",
            )
            return False

    async def update_multiple_sheet_cells(
        self,
        worksheet_name: str,
        row_number: int,
        updates: Dict[str, Any],
        headers: List[str],
    ) -> bool:
        """Update multiple cells in a row in Google Sheet.

        Args:
            worksheet_name: Name of the worksheet
            row_number: Row number to update
            updates: Dictionary of field updates
            headers: Sheet headers for column mapping

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get column mapping for field validation
            SynthPMColumnMappingService.create_column_mapping(headers)

            for field, value in updates.items():
                success = await self.update_sheet_cell(
                    worksheet_name,
                    row_number,
                    field,
                    value,
                    headers,
                )
                if not success:
                    return False

            LOGGER.info(
                f"Successfully updated row {row_number} with {len(updates)} fields",
            )
            return True

        except Exception as e:
            LOGGER.error(
                f"Error updating multiple sheet cells in row {row_number}: {e}",
            )
            return False
