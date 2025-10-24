"""Use case for syncing story data to Google Sheets."""
import asyncio
import re
from datetime import datetime
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.story_synchronization import StorySheetRow
from jira_telegram_bot.entities.story_synchronization import StorySyncConfig
from jira_telegram_bot.entities.story_synchronization.constants import (
    STORY_SYNC_PRESERVE_STATUSES,
)
from jira_telegram_bot.entities.story_synchronization.story_sync_config import (
    SheetBoardMapping,
)
from jira_telegram_bot.use_cases.story_synchronization.fetch_story_data_use_case import (
    FetchStoryDataUseCase,
)
from jira_telegram_bot.use_cases.interfaces.metrics.spreadsheet_gateway_interface import (
    SpreadsheetGatewayInterface,
)


class SyncStoryToSheetsUseCase:
    """Use case for syncing story data to Google Sheets."""

    DEVELOPER_NAMES = [
        "کاظمی",
        "موسوی",
        "مرادی",
        "جانلو",
        "سجادی",
        "حسینی",
        "قمری",
        "زنگنه",
        "سامعی",
        "اروجی",
        "لطفیان",
        "آدابی",
        "دادجو",
        "قاسمی",
        "صدرایی",
        "امام دادی",
        "نسیم",
        "هروی",
    ]

    PRESERVE_STATUSES = [
        "۱",
        "۱. ثبت و اولویت بندی",
        "۲",
        "۲. تحلیل مسئله و RFP",
        "۳",
        "۳. آماده سازی یوزر استوری",
        "۴",
        "۴. در مرحله طراحی",
        "۹",
        "۹. مستندسازی فنی",
        "۱۰",
        "۱۰. تکمیل شده",
    ]

    def __init__(
        self,
        fetch_data_use_case: FetchStoryDataUseCase,
        sheets_gateway: SpreadsheetGatewayInterface,
        sync_config: StorySyncConfig,
        jira_base_url: str,
    ):
        """Initialize the use case.

        Args:
            fetch_data_use_case: Use case for fetching story data.
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
        """Sync stories for a single board.

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
                LOGGER.info(f"Successfully synced {len(rows)} rows for board {board_key}")
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
        """Sync stories for all configured boards.

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
        rows: List[StorySheetRow],
    ) -> bool:
        """Perform full sync - clear and rewrite all data.

        Args:
            mapping: Sheet-to-board mapping configuration.
            rows: List of rows to write.

        Returns:
            True if successful, False otherwise.
        """
        for idx, row in enumerate(rows, start=1):
            row.row_number = idx

        range_name = f"{mapping.sheet_name}!A2:AO"
        values = [self._convert_row_to_values(row) for row in rows]
        return await self.sheets_gateway.update_cells(
            mapping.spreadsheet_id,
            range_name,
            values,
        )

    async def _incremental_sync(
        self,
        mapping: SheetBoardMapping,
        rows: List[StorySheetRow],
    ) -> bool:
        """Perform incremental sync - update only changed issues.

        Args:
            mapping: Sheet-to-board mapping configuration.
            rows: List of rows to update.

        Returns:
            True if successful, False otherwise.
        """
        range_name = f"{mapping.sheet_name}!A2:AO"
        existing_data = await self.sheets_gateway.get_sheet_values(
            mapping.spreadsheet_id,
            range_name,
        )

        existing_keys = self._extract_developer_board_keys(existing_data)
        new_rows = [row for row in rows if row.developer_board_issue_key not in existing_keys]
        update_rows = [row for row in rows if row.developer_board_issue_key in existing_keys]

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
            next_row_number = len(updated_data) + 1
            for new_row in new_rows:
                new_row.row_number = next_row_number
                next_row_number += 1

            append_range = f"{mapping.sheet_name}!A:AO"
            return await self._append_with_retry(
                mapping.spreadsheet_id,
                append_range,
                [self._convert_row_to_values(row) for row in new_rows],
            )

        return True

    def _extract_developer_board_keys(self, data: List[List]) -> List[str]:
        """Extract developer_board_issue_key values from sheet data.

        Args:
            data: Raw sheet data.

        Returns:
            List of developer board issue keys.
        """
        issue_keys = []
        for row in data:
            if len(row) >= 41:
                dev_key_cell = row[40]
                if dev_key_cell:
                    match = re.search(r"PARSCHAT-\d+", str(dev_key_cell))
                    if match:
                        issue_keys.append(match.group(0))
        return issue_keys

    def _merge_data(
        self,
        existing_data: List[List],
        update_rows: List[StorySheetRow],
        all_rows: List[StorySheetRow],
    ) -> List[StorySheetRow]:
        """Merge existing data with updated rows.

        Preserves Google Sheet status for statuses in {۱, ۲, ۳, ۴, ۹, ۱۰}.
        Only updates status when Jira maps to {۵, ۶, ۶.۵, ۷, ۸}.

        Args:
            existing_data: Current data from the sheet.
            update_rows: Rows with updates.
            all_rows: All fetched rows from Jira.

        Returns:
            Merged list of rows.
        """
        update_map = {row.developer_board_issue_key: row for row in update_rows}
        all_map = {row.developer_board_issue_key: row for row in all_rows}

        merged_rows = []
        row_counter = 1

        for row_data in existing_data:
            extracted_keys = self._extract_developer_board_keys([row_data])
            if not extracted_keys:
                continue

            issue_key = extracted_keys[0]
            existing_status = row_data[6] if len(row_data) > 6 else ""

            if issue_key in update_map:
                updated_row = update_map[issue_key]
                
                if self._should_preserve_status(existing_status):
                    updated_row.status = existing_status
                
                updated_row.row_number = row_counter
                merged_rows.append(updated_row)
            elif issue_key in all_map:
                existing_row = all_map[issue_key]
                
                if self._should_preserve_status(existing_status):
                    existing_row.status = existing_status
                
                existing_row.row_number = row_counter
                merged_rows.append(existing_row)
            else:
                existing_row = self._convert_sheet_row_to_entity(row_data)
                if existing_row:
                    existing_row.row_number = row_counter
                    merged_rows.append(existing_row)

            row_counter += 1

        return merged_rows

    def _should_preserve_status(self, status: str) -> bool:
        """Check if the Google Sheet status should be preserved.

        Statuses in {۱, ۲, ۳, ۴, ۹, ۱۰} should not be overwritten by Jira status.

        Args:
            status: Current Google Sheet status.

        Returns:
            True if status should be preserved, False otherwise.
        """
        return status in STORY_SYNC_PRESERVE_STATUSES

    def _convert_row_to_values(self, row: StorySheetRow) -> List:
        """Convert StorySheetRow to list of values for Google Sheets.

        Args:
            row: Row entity to convert.

        Returns:
            List of cell values.
        """
        values = [
            row.row_number,
            row.task_title,
            row.epic or "",
            row.necessity or "",
            row.release or "",
            ", ".join(row.departments) if row.departments else "",
            row.status,
            row.priority or "",
            row.department_deps or "",
            row.main_release or "",
            row.eta_hours,
            row.total_hours,
            row.progress_hours,
            ", ".join(row.involved_people) if row.involved_people else "",
            row.ai_hours,
            row.backend_hours,
            row.frontend_hours,
            row.devops_hours,
            row.ui_ux_hours,
            self._format_date(row.created_date),
            self._format_date(row.implementation_start_date),
            self._format_date(row.deadline),
            row.sprint or "",
            row.dependencies or "",
            self._format_date(row.initial_delivery_time),
            row.description or "",
            row.acceptance_criteria or "",
            row.tests or "",
            row.change_reasons or "",
        ]

        for dev_name in self.DEVELOPER_NAMES:
            values.append(row.individual_hours.get(dev_name, 0.0))

        pm_key_formula = ""
        if row.jira_issue_key:
            pm_key_formula = (
                f'=HYPERLINK("https://jira.parstechai.com/browse/{row.jira_issue_key}";'
                f'"{row.jira_issue_key}")'
            )
        values.append(pm_key_formula)

        dev_key_formula = (
            f'=HYPERLINK("https://jira.parstechai.com/browse/{row.developer_board_issue_key}";'
            f'"{row.developer_board_issue_key}")'
        )
        values.append(dev_key_formula)

        return values

    def _convert_sheet_row_to_entity(self, row_data: List) -> Optional[StorySheetRow]:
        """Convert raw sheet row data back to StorySheetRow entity.

        Args:
            row_data: Raw row data from sheet.

        Returns:
            StorySheetRow entity or None if conversion fails.
        """
        try:
            if len(row_data) < 41:
                return None

            def parse_date(date_str):
                if not date_str or date_str == "":
                    return None
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    return None

            def extract_key_from_hyperlink(cell_value):
                if not cell_value:
                    return ""
                match = re.search(r"PARSCHAT-\d+|PCD-\d+", str(cell_value))
                if match:
                    return match.group(0)
                return cell_value

            individual_hours = {}
            for i, dev_name in enumerate(self.DEVELOPER_NAMES):
                idx = 29 + i
                if len(row_data) > idx and row_data[idx]:
                    try:
                        individual_hours[dev_name] = float(row_data[idx])
                    except:
                        pass

            jira_issue_key = ""
            if len(row_data) > 47:
                jira_issue_key = extract_key_from_hyperlink(row_data[47])

            developer_board_issue_key = ""
            if len(row_data) > 48:
                developer_board_issue_key = extract_key_from_hyperlink(row_data[48])

            return StorySheetRow(
                row_number=int(row_data[0]) if row_data[0] else 0,
                task_title=row_data[1] if len(row_data) > 1 else "",
                epic=row_data[2] if len(row_data) > 2 else None,
                necessity=row_data[3] if len(row_data) > 3 else None,
                release=row_data[4] if len(row_data) > 4 else None,
                departments=(
                    row_data[5].split(", ") if len(row_data) > 5 and row_data[5] else []
                ),
                status=row_data[6] if len(row_data) > 6 else "",
                priority=row_data[7] if len(row_data) > 7 else None,
                department_deps=row_data[8] if len(row_data) > 8 else None,
                main_release=row_data[9] if len(row_data) > 9 else None,
                eta_hours=float(row_data[10]) if len(row_data) > 10 and row_data[10] else 0.0,
                total_hours=(
                    float(row_data[11]) if len(row_data) > 11 and row_data[11] else 0.0
                ),
                progress_hours=(
                    float(row_data[12]) if len(row_data) > 12 and row_data[12] else 0.0
                ),
                involved_people=(
                    row_data[13].split(", ") if len(row_data) > 13 and row_data[13] else []
                ),
                ai_hours=float(row_data[14]) if len(row_data) > 14 and row_data[14] else 0.0,
                backend_hours=(
                    float(row_data[15]) if len(row_data) > 15 and row_data[15] else 0.0
                ),
                frontend_hours=(
                    float(row_data[16]) if len(row_data) > 16 and row_data[16] else 0.0
                ),
                devops_hours=(
                    float(row_data[17]) if len(row_data) > 17 and row_data[17] else 0.0
                ),
                ui_ux_hours=(
                    float(row_data[18]) if len(row_data) > 18 and row_data[18] else 0.0
                ),
                created_date=parse_date(row_data[19]) if len(row_data) > 19 else None,
                implementation_start_date=(
                    parse_date(row_data[20]) if len(row_data) > 20 else None
                ),
                deadline=parse_date(row_data[21]) if len(row_data) > 21 else None,
                sprint=row_data[22] if len(row_data) > 22 else None,
                dependencies=row_data[23] if len(row_data) > 23 else None,
                initial_delivery_time=(
                    parse_date(row_data[24]) if len(row_data) > 24 else None
                ),
                description=row_data[25] if len(row_data) > 25 else None,
                acceptance_criteria=row_data[26] if len(row_data) > 26 else None,
                tests=row_data[27] if len(row_data) > 27 else None,
                change_reasons=row_data[28] if len(row_data) > 28 else None,
                individual_hours=individual_hours,
                jira_issue_key=jira_issue_key,
                developer_board_issue_key=developer_board_issue_key,
            )
        except Exception as e:
            LOGGER.error(f"Error converting sheet row to entity: {e}")
            return None

    def _format_date(self, date) -> str:
        """Format datetime to date string."""
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
        """Update cells with retry logic for quota exceeded errors."""
        for attempt in range(max_retries):
            try:
                return await self.sheets_gateway.update_cells(
                    spreadsheet_id,
                    range_name,
                    values,
                )
            except Exception as e:
                error_str = str(e)
                if (
                    "429" in error_str
                    or "Quota exceeded" in error_str
                    or "quota metric" in error_str.lower()
                ):
                    wait_time = 60 * (attempt + 1)
                    LOGGER.warning(
                        f"Quota exceeded (429), waiting {wait_time}s before retry "
                        f"(attempt {attempt + 1}/{max_retries})",
                    )
                    await asyncio.sleep(wait_time)
                    if attempt == max_retries - 1:
                        LOGGER.error(
                            f"Max retries exceeded for update_cells after {max_retries} attempts",
                        )
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
        """Append rows with retry logic for quota exceeded errors."""
        for attempt in range(max_retries):
            try:
                return await self.sheets_gateway.append_rows(
                    spreadsheet_id,
                    range_name,
                    values,
                )
            except Exception as e:
                error_str = str(e)
                if (
                    "429" in error_str
                    or "Quota exceeded" in error_str
                    or "quota metric" in error_str.lower()
                ):
                    wait_time = 60 * (attempt + 1)
                    LOGGER.warning(
                        f"Quota exceeded (429), waiting {wait_time}s before retry "
                        f"(attempt {attempt + 1}/{max_retries})",
                    )
                    await asyncio.sleep(wait_time)
                    if attempt == max_retries - 1:
                        LOGGER.error(
                            f"Max retries exceeded for append_rows after {max_retries} attempts",
                        )
                        return False
                else:
                    LOGGER.error(f"Error appending rows (non-quota error): {e}")
                    return False
        return False

    def _renumber_rows(self, rows: List[StorySheetRow]) -> None:
        """Renumber rows sequentially."""
        for idx, row in enumerate(rows, start=1):
            row.row_number = idx
