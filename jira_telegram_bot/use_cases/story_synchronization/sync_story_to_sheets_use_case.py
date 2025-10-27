"""Use case for syncing story data to Google Sheets."""
import asyncio
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
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
from jira_telegram_bot.use_cases.interfaces.task_story_repository_interface import (
    TaskStoryRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class SyncStoryToSheetsUseCase:
    """Use case for syncing story data to Google Sheets."""

    def __init__(
        self,
        fetch_data_use_case: FetchStoryDataUseCase,
        sheets_gateway: SpreadsheetGatewayInterface,
        sync_config: StorySyncConfig,
        jira_base_url: str,
        user_config: UserConfigInterface,
        task_story_repository: TaskStoryRepositoryInterface,
    ):
        """Initialize the use case.

        Args:
            fetch_data_use_case: Use case for fetching story data.
            sheets_gateway: Gateway for interacting with Google Sheets.
            sync_config: Configuration mapping boards to sheets.
            jira_base_url: Base URL for Jira (for hyperlinks).
            user_config: User configuration interface for retrieving developer names.
            task_story_repository: Repository for task/story operations.
        """
        self.fetch_data_use_case = fetch_data_use_case
        self.sheets_gateway = sheets_gateway
        self.sync_config = sync_config
        self.jira_base_url = jira_base_url
        self.user_config = user_config
        self.task_story_repository = task_story_repository
        self.developer_names = self.user_config.list_all_users_google_sheet_names()

    def _get_range_name(self, mapping: SheetBoardMapping, include_row_start: bool = True) -> str:
        """Get the full range name for a sheet.

        Args:
            mapping: Sheet-to-board mapping configuration.
            include_row_start: Whether to include row number in range (A2:AW vs A:AW).

        Returns:
            Full range name including sheet name (e.g., "Sheet!A2:AW" or "Sheet!A:AW").
        """
        if include_row_start:
            range_spec = mapping.data_range
        else:
            # Extract column range only (e.g., "A2:AW" -> "A:AW")
            if ":" in mapping.data_range:
                start_col = mapping.data_range.split(":")[0].lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                start_col = mapping.data_range.split(":")[0][:-len(start_col)] if start_col else mapping.data_range.split(":")[0]
                end_col = mapping.data_range.split(":")[1]
                range_spec = f"{start_col}:{end_col}"
            else:
                range_spec = mapping.data_range
        
        return f"{mapping.sheet_name}!{range_spec}"

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
        rows: List[SynthPMFeatureEntity],
    ) -> bool:
        """Perform full sync - clear and rewrite all data.

        Args:
            mapping: Sheet-to-board mapping configuration.
            rows: List of rows to write.

        Returns:
            True if successful, False otherwise.
        """
        for idx in range(len(rows)):
            rows[idx] = rows[idx].model_copy(update={"row_number": idx + 1})

        # Write the entire dataset using configured range
        range_name = self._get_range_name(mapping, include_row_start=True)
        values = [self._convert_row_to_values(feat) for feat in rows]
        return await self.sheets_gateway.update_cells(
            mapping.spreadsheet_id,
            range_name,
            values,
        )

    async def _incremental_sync(
        self,
        mapping: SheetBoardMapping,
        rows: List[SynthPMFeatureEntity],
    ) -> bool:
        """Perform incremental sync - update only changed issues.

        Args:
            mapping: Sheet-to-board mapping configuration.
            rows: List of rows to update.

        Returns:
            True if successful, False otherwise.
        """
        # Extract column range from data_range (e.g., "A2:AW" -> "A:AW")
        column_range = self._get_range_name(mapping, include_row_start=False).split("!")[-1]
        
        existing_rows = await self.task_story_repository.get_sheet_features(
            mapping.spreadsheet_id,
            mapping.sheet_name,
            data_range=column_range,
        )

        existing_keys = self.task_story_repository.extract_issue_keys_from_features(
            existing_rows,
        )
        new_rows = [
            row for row in rows if row.developer_board_issue_key not in existing_keys
        ]
        update_rows = [
            row for row in rows if row.developer_board_issue_key in existing_keys
        ]

        LOGGER.info(
            f"Incremental sync: {len(new_rows)} new, {len(update_rows)} updates",
        )

        updated_data = self._merge_data(existing_rows, update_rows, rows)
        range_name = self._get_range_name(mapping, include_row_start=True)
        write_success = await self._update_with_retry(
            mapping.spreadsheet_id,
            range_name,
            [self._convert_row_to_values(row) for row in updated_data],
        )

        if not write_success:
            return False

        if new_rows:
            next_row_number = len(updated_data) + 1
            renumbered_new_rows = []
            for new_row in new_rows:
                renumbered_new_rows.append(
                    new_row.model_copy(update={"row_number": next_row_number})
                )
                next_row_number += 1

            append_range = self._get_range_name(mapping, include_row_start=False)
            return await self._append_with_retry(
                mapping.spreadsheet_id,
                append_range,
                [self._convert_row_to_values(row) for row in renumbered_new_rows],
            )

        return True

    def _merge_data(
        self,
        existing_rows: List[SynthPMFeatureEntity],
        update_rows: List[SynthPMFeatureEntity],
        all_rows: List[SynthPMFeatureEntity],
    ) -> List[SynthPMFeatureEntity]:
        """Merge existing data with updated rows.

        Preserves Google Sheet status for statuses in {۱, ۲, ۳, ۴, ۹, ۱۰}.
        Only updates status when Jira maps to {۵, ۶, ۶.۵, ۷, ۸}.

        Args:
            existing_rows: Current rows from the sheet.
            update_rows: Rows with updates.
            all_rows: All fetched rows from Jira.

        Returns:
            Merged list of rows.
        """
        update_map = {row.developer_board_issue_key: row for row in update_rows}
        all_map = {row.developer_board_issue_key: row for row in all_rows}

        merged_rows = []
        row_counter = 1

        for existing_row in existing_rows:
            if not existing_row.developer_board_issue_key:
                continue

            issue_key = existing_row.developer_board_issue_key
            existing_status = existing_row.status

            if issue_key in update_map:
                updated_row = update_map[issue_key]

                if self._should_preserve_status(existing_status):
                    updated_row = updated_row.model_copy(
                        update={"status": existing_status},
                    )

                merged_rows.append(
                    updated_row.model_copy(update={"row_number": row_counter}),
                )
            elif issue_key in all_map:
                row_to_keep = all_map[issue_key]

                if self._should_preserve_status(existing_status):
                    row_to_keep = row_to_keep.model_copy(
                        update={"status": existing_status},
                    )

                merged_rows.append(
                    row_to_keep.model_copy(update={"row_number": row_counter}),
                )
            else:
                merged_rows.append(
                    existing_row.model_copy(update={"row_number": row_counter}),
                )

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

    def _convert_row_to_values(self, row: SynthPMFeatureEntity) -> List:
        """Convert SynthPMFeatureEntity to list of values for Google Sheets.

        Args:
            row: Feature entity to convert.

        Returns:
            List of cell values.
        """
        def parse_departments(departments_str):
            if not departments_str:
                return ""
            if isinstance(departments_str, list):
                return ", ".join(departments_str)
            return departments_str

        def parse_involved_people(people_str):
            if not people_str:
                return ""
            if isinstance(people_str, list):
                return ", ".join(people_str)
            return people_str

        values = [
            row.row_number,
            row.task_title,
            row.epic or "",
            row.necessity or "",
            row.release or "",
            parse_departments(row.departments),
            row.status or "",
            row.priority or "",
            row.department_deps or "",
            row.version or "",
            row.eta_hours or 0,
            row.total_hours or 0,
            0,
            parse_involved_people(row.involved_people),
            row.ai or "",
            row.backend or "",
            row.frontend or "",
            row.devops or "",
            row.ui_ux or "",
            self._format_date(row.creation_date),
            self._format_date(row.implementation_start_date),
            self._format_date(row.deadline),
            row.sprint or "",
            row.dependencies or "",
            self._format_date(row.initial_delivery_time),
            row.description or "",
            row.acceptance_criteria or "",
            row.test_cases or "",
            row.po_notes or "",
        ]

        for dev_name in self.developer_names:
            hours = row.times.get(dev_name, 0)
            values.append(hours / 8 if hours else 0.0)

        pm_key_formula = ""
        if row.jira_issue_key:
            pm_key_formula = (
                f'=HYPERLINK("https://jira.parstechai.com/browse/{row.jira_issue_key}";'
                f'"{row.jira_issue_key}")'
            )
        values.append(pm_key_formula)

        dev_key_formula = ""
        if row.developer_board_issue_key:
            dev_key_formula = (
                f'=HYPERLINK("https://jira.parstechai.com/browse/{row.developer_board_issue_key}";'
                f'"{row.developer_board_issue_key}")'
            )
        values.append(dev_key_formula)

        return values

    def _format_date(self, date) -> str:
        """Format datetime to date string.
        
        Args:
            date: Datetime object to format.
            
        Returns:
            Date string in YYYY-MM-DD format.
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

    def _renumber_rows(self, rows: List[SynthPMFeatureEntity]) -> None:
        """Renumber rows sequentially.
        
        Args:
            rows: List of feature entities to renumber (modified in place).
        """
        for idx in range(len(rows)):
            rows[idx] = rows[idx].model_copy(update={"row_number": idx + 1})
