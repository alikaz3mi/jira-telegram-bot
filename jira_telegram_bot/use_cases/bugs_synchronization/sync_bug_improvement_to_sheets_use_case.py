import asyncio
import re
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

        # For full sync (days_back=None), collect all boards' data first
        if days_back is None:
            return await self._execute_full_sync_all_boards(board_keys)
        
        # For incremental sync, process boards one by one
        all_successful = True
        for board_key in board_keys:
            success = await self.execute_for_board(board_key, days_back)
            if not success:
                all_successful = False

        return all_successful
    
    async def _execute_full_sync_all_boards(
        self,
        board_keys: List[str],
    ) -> bool:
        """Execute full sync for multiple boards to the same sheet.
        
        Collects data from all boards first, then writes once to avoid overwriting.

        Args:
            board_keys: List of board keys to sync.

        Returns:
            True if successful, False otherwise.
        """
        # Group boards by their target sheet
        sheet_to_boards = {}
        for board_key in board_keys:
            mapping = self.sync_config.get_mapping_by_board(board_key)
            sheet_id = f"{mapping.spreadsheet_id}:{mapping.sheet_name}"
            if sheet_id not in sheet_to_boards:
                sheet_to_boards[sheet_id] = {
                    'mapping': mapping,
                    'boards': []
                }
            sheet_to_boards[sheet_id]['boards'].append(board_key)
        
        # Process each sheet
        all_successful = True
        for sheet_id, data in sheet_to_boards.items():
            mapping = data['mapping']
            boards = data['boards']
            
            LOGGER.info(f"Full sync: collecting data from {len(boards)} boards for sheet {mapping.sheet_name}")
            
            # Collect all rows from all boards
            all_rows = []
            for board_key in boards:
                LOGGER.info(f"Fetching data for board {board_key}")
                rows = self.fetch_data_use_case.execute(board_key, days_back=None)
                if rows:
                    all_rows.extend(rows)
                    LOGGER.info(f"Collected {len(rows)} rows from {board_key}")
            
            if not all_rows:
                LOGGER.info(f"No data to sync for sheet {mapping.sheet_name}")
                continue
            
            # Assign incremental row numbers across all boards
            for idx, row in enumerate(all_rows, start=1):
                row.row_number = idx
            
            LOGGER.info(f"Writing {len(all_rows)} total rows to sheet {mapping.sheet_name}")
            
            # Write all data at once
            success = await self._full_sync(mapping, all_rows)
            if success:
                LOGGER.info(f"Successfully synced {len(all_rows)} rows to {mapping.sheet_name}")
            else:
                LOGGER.error(f"Failed to sync data to {mapping.sheet_name}")
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
        # Assign incremental row numbers
        for idx, row in enumerate(rows, start=1):
            row.row_number = idx
            
        range_name = f"{mapping.sheet_name}!A2:T"
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
        range_name = f"{mapping.sheet_name}!A2:T"
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
            # Assign row numbers starting from the last row in existing data
            next_row_number = len(updated_data) + 1
            for new_row in new_rows:
                new_row.row_number = next_row_number
                next_row_number += 1
            
            append_range = f"{mapping.sheet_name}!A:T"
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
            if len(row) >= 20:
                issue_key_value = row[19]
                if issue_key_value:
                    match = re.search(r"PARSCHAT-\d+", str(issue_key_value))
                    if match:
                        issue_keys.append(match.group(0))
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
            update_rows: Rows with updates (issues that exist and were updated).
            all_rows: All fetched rows from Jira (within days_back filter).

        Returns:
            Merged list of rows - updates existing issues, preserves old issues.
        """
        update_map = {row.issue_key: row for row in update_rows}
        all_map = {row.issue_key: row for row in all_rows}

        merged_rows = []
        row_counter = 1
        
        for row_data in existing_data:
            # Extract issue key using the fixed method
            extracted_keys = self._extract_issue_keys([row_data])
            if not extracted_keys:
                continue
                
            issue_key = extracted_keys[0]

            if issue_key in update_map:
                # Issue was updated - use new data with proper row number
                updated_row = update_map[issue_key]
                updated_row.row_number = row_counter
                merged_rows.append(updated_row)
            elif issue_key in all_map:
                # Issue exists but wasn't updated - use new data anyway with proper row number
                existing_row = all_map[issue_key]
                existing_row.row_number = row_counter
                merged_rows.append(existing_row)
            else:
                # Issue not in current fetch (older than days_back) - keep existing row
                # Convert existing row data back to entity
                existing_row = self._convert_sheet_row_to_entity(row_data)
                if existing_row:
                    existing_row.row_number = row_counter
                    merged_rows.append(existing_row)
            
            row_counter += 1

        return merged_rows

    def _convert_row_to_values(self, row: BugImprovementSheetRow) -> List:
        """Convert BugImprovementSheetRow to list of values for Google Sheets.

        Args:
            row: Row entity to convert.

        Returns:
            List of cell values matching the new column order.
            Order: ردیف، وظیفه، توضیحات، گزارش دهنده، برد، افراد درگیر، اسپرینت، 
                   Epic، Story، اولویت، وضعیت، Departments، ریلیز، Total (h)، 
                   تاریخ ایجاد، تاریخ شروع پیاده سازی، ددلاین، یوزر درگیر، 
                   زمان تحویل اولیه، issue_key
        """
        return [
            row.row_number,
            row.task_title,
            row.description or "",
            row.reporter or "",
            row.board_name or "",
            ", ".join(row.involved_people) if row.involved_people else "",
            row.sprint or "",
            row.epic_name or "",
            row.linked_story or "",
            row.priority or "",
            row.status,
            ", ".join(row.departments) if row.departments else "",
            row.release or "",
            row.total_hours,
            self._format_date(row.created_date),
            self._format_date(row.implementation_start_date),
            self._format_date(row.deadline),
            row.involved_user_from_label or "",
            self._format_date(row.initial_delivery_time),
            f'=HYPERLINK("https://jira.parstechai.com/browse/{row.issue_key}";"{row.issue_key}")',
        ]

    def _convert_sheet_row_to_entity(self, row_data: List) -> Optional[BugImprovementSheetRow]:
        """Convert raw sheet row data back to BugImprovementSheetRow entity.

        Args:
            row_data: Raw row data from sheet.

        Returns:
            BugImprovementSheetRow entity or None if conversion fails.
        """
        try:
            if len(row_data) < 20:
                return None

            # Extract issue_key from HYPERLINK formula
            issue_key_cell = row_data[19] if len(row_data) > 19 else ""
            issue_key = issue_key_cell
            if '", "' in issue_key_cell:
                issue_key = issue_key_cell.split('", "')[1].replace('")', "")
            elif "HYPERLINK" in issue_key_cell:
                # Extract from formula
                import re
                match = re.search(r'PARSCHAT-\d+', issue_key_cell)
                if match:
                    issue_key = match.group(0)

            # Parse dates
            from datetime import datetime
            def parse_date(date_str):
                if not date_str or date_str == "":
                    return None
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    return None

            return BugImprovementSheetRow(
                row_number=int(row_data[0]) if row_data[0] else 0,
                task_title=row_data[1] if len(row_data) > 1 else "",
                description=row_data[2] if len(row_data) > 2 else None,
                reporter=row_data[3] if len(row_data) > 3 else None,
                board_name=row_data[4] if len(row_data) > 4 else None,
                involved_people=row_data[5].split(", ") if len(row_data) > 5 and row_data[5] else [],
                sprint=row_data[6] if len(row_data) > 6 else None,
                epic_name=row_data[7] if len(row_data) > 7 else None,
                linked_story=row_data[8] if len(row_data) > 8 else None,
                priority=row_data[9] if len(row_data) > 9 else None,
                status=row_data[10] if len(row_data) > 10 else "",
                departments=row_data[11].split(", ") if len(row_data) > 11 and row_data[11] else [],
                release=row_data[12] if len(row_data) > 12 else None,
                total_hours=float(row_data[13]) if len(row_data) > 13 and row_data[13] else 0.0,
                created_date=parse_date(row_data[14]) if len(row_data) > 14 else None,
                implementation_start_date=parse_date(row_data[15]) if len(row_data) > 15 else None,
                deadline=parse_date(row_data[16]) if len(row_data) > 16 else None,
                involved_user_from_label=row_data[17] if len(row_data) > 17 else None,
                initial_delivery_time=parse_date(row_data[18]) if len(row_data) > 18 else None,
                issue_key=issue_key,
            )
        except Exception as e:
            LOGGER.error(f"Error converting sheet row to entity: {e}")
            return None

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
