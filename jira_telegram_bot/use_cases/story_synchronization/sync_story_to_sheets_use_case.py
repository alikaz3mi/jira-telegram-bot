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
            f"Incremental sync: {len(new_rows)} new, {len(update_rows)} updates (before filtering)",
        )

        # Filter to only rows with actual changes in tracked fields
        rows_with_changes = self._filter_rows_with_field_changes(
            existing_rows,
            update_rows,
        )

        LOGGER.info(
            f"After field-level filtering: {len(rows_with_changes)} rows have actual changes",
        )

        if not rows_with_changes and not new_rows:
            LOGGER.info("No changes detected, skipping sync")
            return True

        # Update only the changed cells for existing rows
        if rows_with_changes:
            success = await self._update_changed_cells(
                mapping,
                existing_rows,
                rows_with_changes,
            )
            if not success:
                return False

        # Append new rows (these get all columns since they're new)
        if new_rows:
            # Calculate the next row number based on existing sheet rows
            next_row_number = len(existing_rows) + 2  # +2 for header row and 1-based indexing
            
            renumbered_new_rows = []
            for new_row in new_rows:
                renumbered_new_rows.append(
                    new_row.model_copy(update={"row_number": next_row_number - 1})
                )
                next_row_number += 1

            append_range = self._get_range_name(mapping, include_row_start=False)
            return await self._append_with_retry(
                mapping.spreadsheet_id,
                append_range,
                [self._convert_row_to_values(row) for row in renumbered_new_rows],
            )

        return True

    def _filter_rows_with_field_changes(
        self,
        existing_rows: List[SynthPMFeatureEntity],
        update_rows: List[SynthPMFeatureEntity],
    ) -> List[SynthPMFeatureEntity]:
        """Filter update rows to only those with changes in tracked fields.

        Tracked fields:
        - implementation_start_date
        - deadline
        - status
        - progress (times dict - developer work hours)

        Args:
            existing_rows: Current rows from the sheet.
            update_rows: Rows with potential updates.

        Returns:
            List of rows that have actual changes in tracked fields.
        """
        existing_map = {
            row.developer_board_issue_key: row for row in existing_rows
        }
        
        rows_with_changes = []
        
        for update_row in update_rows:
            issue_key = update_row.developer_board_issue_key
            existing_row = existing_map.get(issue_key)
            
            if not existing_row:
                continue
            
            has_changes = False
            
            # Check implementation_start_date (compare dates only, ignore time/timezone)
            if not self._dates_equal(update_row.implementation_start_date, existing_row.implementation_start_date):
                LOGGER.debug(
                    f"{issue_key}: implementation_start_date changed from "
                    f"{existing_row.implementation_start_date} to {update_row.implementation_start_date}"
                )
                has_changes = True
            
            # Check deadline (compare dates only, ignore time/timezone)
            if not self._dates_equal(update_row.deadline, existing_row.deadline):
                LOGGER.debug(
                    f"{issue_key}: deadline changed from "
                    f"{existing_row.deadline} to {update_row.deadline}"
                )
                has_changes = True
            
            # Check status (with preservation logic)
            if not self._should_preserve_status(existing_row.status):
                if update_row.status != existing_row.status:
                    LOGGER.debug(
                        f"{issue_key}: status changed from "
                        f"{existing_row.status} to {update_row.status}"
                    )
                    has_changes = True
            
            # Check progress (times dict) - compare rounded hours to avoid float precision issues
            if not self._times_equal(update_row.times, existing_row.times):
                LOGGER.debug(
                    f"{issue_key}: progress (times) changed from "
                    f"{existing_row.times} to {update_row.times}"
                )
                has_changes = True
            
            if has_changes:
                # Preserve status if needed
                if self._should_preserve_status(existing_row.status):
                    update_row = update_row.model_copy(
                        update={"status": existing_row.status},
                    )
                
                rows_with_changes.append(update_row)
        
        return rows_with_changes

    def _dates_equal(self, date1, date2) -> bool:
        """Compare two dates ignoring time and timezone.

        Args:
            date1: First datetime object (can be None).
            date2: Second datetime object (can be None).

        Returns:
            True if dates are equal (day-level), False otherwise.
        """
        if date1 is None and date2 is None:
            return True
        if date1 is None or date2 is None:
            return False
        
        # Compare only year, month, day (ignore time and timezone)
        return (
            date1.year == date2.year
            and date1.month == date2.month
            and date1.day == date2.day
        )

    def _times_equal(self, times1: dict, times2: dict) -> bool:
        """Compare two times dictionaries with rounding for precision.

        Both Jira and sheets store hours directly.
        Need to round to avoid float precision issues.

        Args:
            times1: First times dictionary {dev_name: hours}.
            times2: Second times dictionary {dev_name: hours}.

        Returns:
            True if times are equal (within rounding), False otherwise.
        """
        if not times1 and not times2:
            return True
        
        # Get all developer names from both dicts
        all_devs = set(times1.keys()) | set(times2.keys())
        
        for dev in all_devs:
            hours1 = times1.get(dev, 0)
            hours2 = times2.get(dev, 0)
            
            # Round to 2 decimal places to avoid float precision issues
            # (8.0 vs 8.000001, etc.)
            if round(hours1, 2) != round(hours2, 2):
                return False
        
        return True

    async def _update_changed_cells(
        self,
        mapping: SheetBoardMapping,
        existing_rows: List[SynthPMFeatureEntity],
        changed_rows: List[SynthPMFeatureEntity],
    ) -> bool:
        """Update only the cells that have changed.

        Args:
            mapping: Sheet-to-board mapping configuration.
            existing_rows: Current rows from the sheet.
            changed_rows: Rows with field changes.

        Returns:
            True if successful, False otherwise.
        """
        # Build a map of existing rows for quick lookup
        existing_map = {
            row.developer_board_issue_key: row for row in existing_rows
        }
        
        # Column indices for tracked fields (0-based)
        STATUS_COL = 6  # Column G
        IMPLEMENTATION_START_COL = 20  # Column U
        DEADLINE_COL = 21  # Column V
        DEVELOPER_COLS_START = 29  # Column AD onwards
        
        # Prepare batch update requests
        update_requests = []
        
        for changed_row in changed_rows:
            issue_key = changed_row.developer_board_issue_key
            existing_row = existing_map.get(issue_key)
            
            if not existing_row:
                continue
            
            # Find the sheet row number (1-indexed, includes header)
            sheet_row = existing_row.sheet_row_number
            
            # Update status (column G)
            if changed_row.status != existing_row.status:
                cell_range = f"{mapping.sheet_name}!G{sheet_row}"
                update_requests.append({
                    "range": cell_range,
                    "values": [[changed_row.status or ""]],
                })
            
            # Update implementation_start_date (column U)
            if not self._dates_equal(changed_row.implementation_start_date, existing_row.implementation_start_date):
                cell_range = f"{mapping.sheet_name}!U{sheet_row}"
                update_requests.append({
                    "range": cell_range,
                    "values": [[self._format_date(changed_row.implementation_start_date)]],
                })
            
            # Update deadline (column V)
            if not self._dates_equal(changed_row.deadline, existing_row.deadline):
                cell_range = f"{mapping.sheet_name}!V{sheet_row}"
                update_requests.append({
                    "range": cell_range,
                    "values": [[self._format_date(changed_row.deadline)]],
                })
            
            # Update progress columns (developer times)
            if not self._times_equal(changed_row.times, existing_row.times):
                for idx, dev_name in enumerate(self.developer_names):
                    old_hours = existing_row.times.get(dev_name, 0)
                    new_hours = changed_row.times.get(dev_name, 0)
                    
                    # Only update if this specific developer's hours changed
                    if round(old_hours, 2) != round(new_hours, 2):
                        # Convert column index to letter
                        col_idx = DEVELOPER_COLS_START + idx
                        col_letter = self._column_index_to_letter(col_idx)
                        cell_range = f"{mapping.sheet_name}!{col_letter}{sheet_row}"
                        update_requests.append({
                            "range": cell_range,
                            "values": [[new_hours if new_hours else 0]],
                        })
        
        if not update_requests:
            LOGGER.info("No cell updates needed")
            return True
        
        LOGGER.info(f"Updating {len(update_requests)} cells")
        
        # Batch update all changed cells
        try:
            for request in update_requests:
                await self.sheets_gateway.update_range(
                    mapping.spreadsheet_id,
                    request["range"],
                    request["values"],
                )
            return True
        except Exception as e:
            LOGGER.error(f"Failed to update cells: {e}")
            return False

    def _column_index_to_letter(self, index: int) -> str:
        """Convert 0-based column index to letter (0->A, 25->Z, 26->AA).

        Args:
            index: 0-based column index.

        Returns:
            Column letter(s).
        """
        result = ""
        index += 1  # Convert to 1-based
        while index > 0:
            index -= 1
            result = chr(65 + (index % 26)) + result
            index //= 26
        return result

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
            values.append(hours if hours else 0)

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
