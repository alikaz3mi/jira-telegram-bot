"""Google Sheets adapter for SynthPM operations."""
from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.adapters.synth_pm.mixins.data_parsing_mixin import (
    DataParsingMixin,
)
from jira_telegram_bot.adapters.synth_pm.mixins.google_sheets_mixin import (
    GoogleSheetsMixin,
)
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class SynthPMGoogleSheetsAdapter(GoogleSheetsMixin, DataParsingMixin):
    """Adapter for SynthPM Google Sheets operations."""

    def __init__(
        self,
        google_sheet_client: GoogleSheetClient,
        settings: SynthPMSettings,
        user_config: UserConfigInterface,
    ):
        """Initialize the adapter.

        Args:
            google_sheet_client: Google Sheets client
            settings: SynthPM settings
            user_config: User configuration interface
        """
        self.google_sheet_client = google_sheet_client
        self.settings = settings
        self.user_config = user_config

    async def get_developer_board_features(self) -> List[SynthPMFeatureEntity]:
        """Get all features from Google Sheets.

        Returns:
            List of feature entities
        """
        try:
            range_name = f"{self.settings.developer_board_worksheet_name}!A:AT"
            values = await self.get_sheet_values(range_name)

            if not values or len(values) < 2:
                LOGGER.warning("No data found in Features sheet")
                return []

            headers = values[0]
            data_rows = values[1:]
            features = []

            for idx, row in enumerate(data_rows, start=2):
                if len(row) < 2:
                    continue

                feature = self.parse_row_to_feature(idx, row, headers)
                if feature:
                    features.append(feature)

            LOGGER.info(f"Retrieved {len(features)} features")
            return features

        except Exception as e:
            LOGGER.error(f"Error retrieving features: {e}")
            return []

    async def update_developer_board_feature(
        self,
        row_number: int,
        updates: Dict[str, Any],
    ) -> bool:
        """Update a specific feature in Google Sheets.

        Args:
            row_number: Row number to update
            updates: Dictionary of field updates

        Returns:
            True if successful, False otherwise
        """
        try:
            headers_range = f"{self.settings.developer_board_worksheet_name}!1:1"
            headers_values = await self.get_sheet_values(headers_range)

            if not headers_values:
                LOGGER.error("Could not retrieve headers for column mapping")
                return False

            headers = headers_values[0]
            return await self.update_multiple_sheet_cells(
                self.settings.developer_board_worksheet_name,
                row_number,
                updates,
                headers,
            )

        except Exception as e:
            LOGGER.error(f"Error updating feature row {row_number}: {e}")
            return False

    async def get_release_notes(self) -> List[ReleaseNoteEntity]:
        """Get all release notes from Google Sheets.

        Returns:
            List of release note entities
        """
        try:
            range_name = f"{self.settings.release_notes_worksheet_name}!A:AG"
            values = await self.get_sheet_values(range_name)

            if not values or len(values) < 2:
                LOGGER.warning("No data found in Release Notes sheet")
                return []

            headers = values[0]
            data_rows = values[1:]
            release_notes = []

            for idx, row in enumerate(data_rows, start=2):
                if len(row) < 2:
                    continue

                release_note = self._parse_row_to_release_note(idx, row, headers)
                if release_note:
                    release_notes.append(release_note)

            LOGGER.info(f"Retrieved {len(release_notes)} release notes")
            return release_notes

        except Exception as e:
            LOGGER.error(f"Error retrieving release notes: {e}")
            return []

    async def update_release_note(
        self,
        row_number: int,
        updates: Dict[str, Any],
    ) -> bool:
        """Update a specific release note in Google Sheets.

        Args:
            row_number: Row number to update
            updates: Dictionary of field updates

        Returns:
            True if successful, False otherwise
        """
        try:
            headers_range = f"{self.settings.release_notes_worksheet_name}!1:1"
            headers_values = await self.get_sheet_values(headers_range)

            if not headers_values:
                LOGGER.error(
                    "Could not retrieve headers for release notes column mapping",
                )
                return False

            headers = headers_values[0]
            return await self.update_multiple_sheet_cells(
                self.settings.release_notes_worksheet_name,
                row_number,
                updates,
                headers,
            )

        except Exception as e:
            LOGGER.error(f"Error updating release note row {row_number}: {e}")
            return False

    def _parse_row_to_release_note(
        self,
        row_number: int,
        row: List[str],
        headers: List[str],
    ) -> Optional[ReleaseNoteEntity]:
        """Parse a row from Google Sheets to ReleaseNoteEntity.

        Args:
            row_number: Row number in the sheet
            row: Row data from Google Sheets
            headers: Sheet headers

        Returns:
            ReleaseNoteEntity or None if parsing fails
        """
        try:
            column_mapping = self._create_release_notes_column_mapping(headers)

            def get_mapped_value(field_name: str) -> str:
                col_idx = column_mapping.get(field_name)
                if col_idx is not None and col_idx < len(row):
                    return row[col_idx].strip()
                return ""

            release_version = get_mapped_value("release_version")
            if not release_version:
                return None

            return ReleaseNoteEntity(
                row_number=row_number,
                release_version=release_version,
                release_components=get_mapped_value("release_components") or "",
                description=get_mapped_value("description") or "",
                goals=get_mapped_value("goals") or None,
                delivery_process=get_mapped_value("delivery_process") or None,
                test_process=get_mapped_value("test_process") or None,
                telegram_message_id=get_mapped_value("telegram_message_id") or None,
            )

        except Exception as e:
            LOGGER.error(f"Error parsing release note row {row_number}: {e}")
            return None

    def _create_release_notes_column_mapping(
        self,
        headers: List[str],
    ) -> Dict[str, int]:
        """Create mapping for release notes columns.

        Args:
            headers: List of column headers from the sheet

        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}

        column_name_mappings = {
            "release_version": ["نسخه", "Version", "Release Version"],
            "release_components": ["اجزای ریلیز", "Components", "Release Components"],
            "description": ["توضیحات", "Description"],
            "goals": ["اهداف", "Goals"],
            "delivery_process": ["فرآیند تحویل", "Delivery Process"],
            "test_process": ["فرآیند تست", "Test Process"],
            "telegram_message_id": ["telegram_message_id", "Telegram Message ID"],
        }

        for idx, header in enumerate(headers):
            header_clean = header.strip()

            for field_name, possible_names in column_name_mappings.items():
                if header_clean in possible_names:
                    mapping[field_name] = idx
                    break

        return mapping
