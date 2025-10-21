import asyncio
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.bugs_synchronization import BugImprovementSheetRow
from jira_telegram_bot.entities.bugs_synchronization import BugImprovementSyncConfig
from jira_telegram_bot.entities.bugs_synchronization import SheetBoardMapping
from jira_telegram_bot.use_cases.bugs_synchronization.fetch_bug_improvement_data_use_case import (
    FetchBugImprovementDataUseCase,
)
from jira_telegram_bot.use_cases.interfaces.metrics.spreadsheet_gateway_interface import (
    SpreadsheetGatewayInterface,
)


class SyncBugImprovementToSheetsUseCase:
    """Use case for syncing bug and improvement data to Google Sheets."""

    def __init__(
        self,
        fetch_data_use_case: FetchBugImprovementDataUseCase,
        sheets_gateway: SpreadsheetGatewayInterface,
        sync_config: BugImprovementSyncConfig,
        jira_base_url: str,
    ):
        """Initialize the use case.

        Args:
            fetch_data_use_case: Use case for fetching bug/improvement data.
            sheets_gateway: Gateway for interacting with Google Sheets.
            sync_config: Configuration mapping boards to sheets.
            jira_base_url: Base URL for Jira (for hyperlinks).
        """
        self.fetch_data_use_case = fetch_data_use_case
        self.sheets_gateway = sheets_gateway
        self.sync_config = sync_config
        self.jira_base_url = jira_base_url

    async def execute_for_board(
        self,
        board_key: str,
        days_back: Optional[int] = None,
    ) -> bool:
        """Sync bugs and improvements for a single board.

        Args:
            board_key: Jira board/project key.
            days_back: Number of days to look back for updated issues.

        Returns:
            True if sync was successful, False otherwise.
        """
        try:
            mapping = self.sync_config.get_mapping_by_board(board_key)
            LOGGER.info(f"Syncing board {board_key} to sheet {mapping.sheet_name}")

            rows = self.fetch_data_use_case.execute(board_key, days_back)

            if not rows:
                LOGGER.info(f"No data to sync for board {board_key}")
                return True

            self._renumber_rows(rows)

            if days_back is None:
                success = await self._full_sync(mapping, rows)
            else:
                success = await self._incremental_sync(mapping, rows)

            if success:
                LOGGER.info(
                    f"Successfully synced {len(rows)} rows for board {board_key}",
                )
            else:
                LOGGER.error(f"Failed to sync data for board {board_key}")

            return success

        except Exception as e:
            LOGGER.error(f"Error syncing board {board_key}: {e}")
            return False

    async def execute_for_all_boards(
        self,
        days_back: Optional[int] = None,
    ) -> bool:
        """Sync bugs and improvements for all configured boards.

        Args:
            days_back: Number of days to look back for updated issues.

        Returns:
            True if all syncs were successful, False otherwise.
        """
        board_keys = self.sync_config.get_all_board_keys()
        LOGGER.info(f"Syncing {len(board_keys)} boards")

        all_successful = True
        for board_key in board_keys:
            success = await self.execute_for_board(board_key, days_back)
            if not success:
                all_successful = False

        return all_successful

    async def _full_sync(
        self,
        mapping: SheetBoardMapping,
        rows: List[BugImprovementSheetRow],
    ) -> bool:
        """Perform full sync - clear and rewrite all data.

        Args:
            mapping: Sheet-to-board mapping configuration.
            rows: List of rows to write.

        Returns:
            True if successful, False otherwise.
        """
        range_name = f"{mapping.sheet_name}!A2:Q"
        values = [self._convert_row_to_values(row) for row in rows]
        return await self.sheets_gateway.update_cells(
            mapping.spreadsheet_id,
            range_name,
            values,
        )

    async def _incremental_sync(
        self,
        mapping: SheetBoardMapping,
        rows: List[BugImprovementSheetRow],
    ) -> bool:
        """Perform incremental sync - update only changed issues.

        Args:
            mapping: Sheet-to-board mapping configuration.
            rows: List of rows to update.

        Returns:
            True if successful, False otherwise.
        """
        range_name = f"{mapping.sheet_name}!A2:Q"
        existing_data = await self.sheets_gateway.get_sheet_values(
            mapping.spreadsheet_id,
            range_name,
        )

        existing_keys = self._extract_issue_keys(existing_data)
        new_rows = [row for row in rows if row.issue_key not in existing_keys]
        update_rows = [row for row in rows if row.issue_key in existing_keys]

        LOGGER.info(f"Incremental sync: {len(new_rows)} new, {len(update_rows)} updates")

        updated_data = self._merge_data(existing_data, update_rows, rows)
        write_success = await self._update_with_retry(
            mapping.spreadsheet_id,
            range_name,
            [self._convert_row_to_values(row) for row in updated_data],
        )

        if not write_success:
            return False

        if new_rows:
            append_range = f"{mapping.sheet_name}!A:Q"
            return await self._append_with_retry(
                mapping.spreadsheet_id,
                append_range,
                [self._convert_row_to_values(row) for row in new_rows],
            )

        return True

    def _extract_issue_keys(self, data: List[List]) -> List[str]:
        """Extract issue keys from sheet data.

        Args:
            data: Raw sheet data.

        Returns:
            List of issue keys.
        """
        issue_keys = []
        for row in data:
            if len(row) >= 17:
                issue_key = row[16]
                if '", "' in issue_key:
                    issue_key = issue_key.split('", "')[1].replace('")', "")
                issue_keys.append(issue_key)
        return issue_keys

    def _merge_data(
        self,
        existing_data: List[List],
        update_rows: List[BugImprovementSheetRow],
        all_rows: List[BugImprovementSheetRow],
    ) -> List[BugImprovementSheetRow]:
        """Merge existing data with updated rows.

        Args:
            existing_data: Current data from the sheet.
            update_rows: Rows with updates.
            all_rows: All fetched rows.

        Returns:
            Merged list of rows.
        """
        update_map = {row.issue_key: row for row in update_rows}
        all_map = {row.issue_key: row for row in all_rows}

        merged_rows = []
        for row_data in existing_data:
            if len(row_data) >= 17:
                issue_key = row_data[16]
                if '", "' in issue_key:
                    issue_key = issue_key.split('", "')[1].replace('")', "")

                if issue_key in update_map:
                    merged_rows.append(update_map[issue_key])
                elif issue_key in all_map:
                    merged_rows.append(all_map[issue_key])

        return merged_rows

    def _convert_row_to_values(self, row: BugImprovementSheetRow) -> List:
        """Convert BugImprovementSheetRow to list of values for Google Sheets.

        Args:
            row: Row entity to convert.

        Returns:
            List of cell values.
        """
        return [
            row.row_number,
            row.task_title,
            row.description or "",
            row.epic_name or "",
            row.linked_story or "",
            row.priority or "",
            row.status,
            ", ".join(row.departments) if row.departments else "",
            row.release or "",
            row.total_hours,
            ", ".join(row.involved_people) if row.involved_people else "",
            self._format_date(row.created_date),
            self._format_date(row.implementation_start_date),
            self._format_date(row.deadline),
            row.sprint or "",
            self._format_date(row.initial_delivery_time),
            f'=HYPERLINK("https://jira.parstechai.com/browse/{row.issue_key}";"{row.issue_key}")',
        ]

    def _format_date(self, date) -> str:
        """Format datetime to date string (YYYY-MM-DD only).

        Args:
            date: Datetime object or None.

        Returns:
            Formatted date string or empty string.
        """
        if date is None:
            return ""
        return date.strftime("%Y-%m-%d")

    async def _update_with_retry(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List],
        max_retries: int = 5,
    ) -> bool:
        """Update cells with retry logic for quota exceeded errors.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID.
            range_name: Range to update.
            values: Values to write.
            max_retries: Maximum number of retries.

        Returns:
            True if successful, False otherwise.
        """
        for attempt in range(max_retries):
            try:
                return await self.sheets_gateway.update_cells(
                    spreadsheet_id,
                    range_name,
                    values,
                )
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Quota exceeded" in error_str or "quota metric" in error_str.lower():
                    wait_time = 60 * (attempt + 1)
                    LOGGER.warning(
                        f"Quota exceeded (429), waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})",
                    )
                    await asyncio.sleep(wait_time)
                    if attempt == max_retries - 1:
                        LOGGER.error(f"Max retries exceeded for update_cells after {max_retries} attempts")
                        return False
                else:
                    LOGGER.error(f"Error updating cells (non-quota error): {e}")
                    return False
        return False

    async def _append_with_retry(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List],
        max_retries: int = 5,
    ) -> bool:
        """Append rows with retry logic for quota exceeded errors.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID.
            range_name: Range to append to.
            values: Values to append.
            max_retries: Maximum number of retries.

        Returns:
            True if successful, False otherwise.
        """
        for attempt in range(max_retries):
            try:
                return await self.sheets_gateway.append_rows(
                    spreadsheet_id,
                    range_name,
                    values,
                )
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Quota exceeded" in error_str or "quota metric" in error_str.lower():
                    wait_time = 60 * (attempt + 1)
                    LOGGER.warning(
                        f"Quota exceeded (429), waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})",
                    )
                    await asyncio.sleep(wait_time)
                    if attempt == max_retries - 1:
                        LOGGER.error(f"Max retries exceeded for append_rows after {max_retries} attempts")
                        return False
                else:
                    LOGGER.error(f"Error appending rows (non-quota error): {e}")
                    return False
        return False

    def _renumber_rows(self, rows: List[BugImprovementSheetRow]) -> None:
        """Renumber rows sequentially.

        Args:
            rows: List of rows to renumber.
        """
        for idx, row in enumerate(rows, start=1):
            row.row_number = idx
