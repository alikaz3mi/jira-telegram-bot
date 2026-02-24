"""Repository implementation for task/story Google Sheets operations."""
from datetime import datetime
import re
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.synth_pm.constants import RELEASE_VERSION_PATTERN
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.interfaces.metrics.spreadsheet_gateway_interface import (
    SpreadsheetGatewayInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_story_repository_interface import (
    TaskStoryRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class TaskStoryRepository(TaskStoryRepositoryInterface):
    """Repository implementation for task/story Google Sheets operations."""

    def __init__(
        self,
        sheets_gateway: SpreadsheetGatewayInterface,
        user_config: UserConfigInterface,
    ):
        """Initialize the repository.

        Args:
            sheets_gateway: Gateway for Google Sheets operations.
            user_config: User configuration interface.
        """
        self.sheets_gateway = sheets_gateway
        self.user_config = user_config
        self.developer_names = self.user_config.list_all_users_google_sheet_names()

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
        try:
            range_name = f"{sheet_name}!{data_range}"
            values = await self.sheets_gateway.get_sheet_values(
                spreadsheet_id,
                range_name,
            )

            if not values or len(values) < 2:
                LOGGER.warning(f"No data found in sheet {sheet_name}")
                return []

            headers = values[0]
            column_mapping, people_mapping = self._create_column_mapping(headers)

            data_rows = values[1:]
            features = []

            for idx, row in enumerate(data_rows, start=2):
                if len(row) < 2:
                    continue

                feature = self._parse_row_to_feature(idx, row, column_mapping, people_mapping)
                if feature:
                    features.append(feature)

            LOGGER.info(f"Retrieved {len(features)} features from {sheet_name}")
            return features

        except Exception as e:
            LOGGER.error(f"Error retrieving features from {sheet_name}: {e}")
            return []

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
        try:
            headers_range = f"{sheet_name}!1:1"
            headers_values = await self.sheets_gateway.get_sheet_values(
                spreadsheet_id,
                headers_range,
            )

            if not headers_values:
                LOGGER.error("Could not retrieve headers for column mapping")
                return False

            headers = headers_values[0]
            column_mapping, _ = self._create_column_mapping(headers)

            for field, value in updates.items():
                if field in column_mapping:
                    col_idx = column_mapping[field]
                    col_letter = self._number_to_column_letter(col_idx + 1)
                    range_name = f"{sheet_name}!{col_letter}{row_number}"

                    success = await self.sheets_gateway.update_cells(
                        spreadsheet_id,
                        range_name,
                        [[str(value) if value is not None else ""]],
                    )

                    if not success:
                        LOGGER.error(
                            f"Failed to update field {field} in row {row_number}",
                        )
                        return False
                else:
                    LOGGER.warning(
                        f"Field {field} not found in column mapping, skipping",
                    )

            LOGGER.info(
                f"Successfully updated row {row_number} with {len(updates)} fields",
            )
            return True

        except Exception as e:
            LOGGER.error(f"Error updating feature row {row_number}: {e}")
            return False

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
        return [
            feature.developer_board_issue_key
            for feature in features
            if feature.developer_board_issue_key
        ]

    def _create_column_mapping(
        self,
        headers: List[str],
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Create mapping from column names to indices.

        Args:
            headers: List of column headers from the sheet.

        Returns:
            Tuple of (field mapping, people mapping) dictionaries.
        """
        mapping = {}

        column_name_mappings = {
            "row_number": ["ردیف", "Row"],
            "task_title": ["وظیفه", "Task"],
            "epic": ["Epic"],
            "necessity": ["ضرورت", "Necessity"],
            "priority": ["اولویت", "Priority"],
            "status": ["وضعیت", "Status"],
            "release": ["ریلیز", "Release"],
            "eta_hours": ["ETA(h)", "ETA"],
            "total_hours": ["Total (h)", "Total"],
            "progress_hours": ["Progress (h)", "Progress"],
            "departments": ["Departments"],
            "involved_people": ["افراد درگیر", "Involved People"],
            "ai": ["AI"],
            "backend": ["Backend"],
            "frontend": ["Front-end", "Frontend"],
            "devops": ["DevOPS", "DevOps"],
            "ui_ux": ["UI / UX", "UI/UX"],
            "creation_date": ["تاریخ ایجاد", "Creation Date"],
            "implementation_start_date": [
                "تاریخ شروع پیاده سازی",
                "Implementation Start",
            ],
            "deadline": ["ددلاین", "Deadline"],
            "sprint": ["اسپرینت", "Sprint"],
            "dependencies": ["وابستگی ها", "Dependencies"],
            "department_deps": [
                "Department Deps",
                "Department Dependencies",
                "وابستگی های دپارتمان",
            ],
            "initial_delivery_time": ["زمان تحویل اولیه", "Initial Delivery"],
            "description": ["توضیحات", "Description"],
            "acceptance_criteria": ["معیارهای پذیرش", "Acceptance Criteria"],
            "test_cases": ["تست ها", "Test Cases"],
            "po_notes": ["علل تغییر یا توقف", "PO Notes", "Change Reasons"],
            "jira_issue_key": ["jira_issue_key", "Jira Issue Key"],
            "developer_board_issue_key": ["developer_board_issue_key"],
            "version": ["version", "ریلیز اصلی"],
        }

        people_mapping = {}
        for user in self.developer_names:
            user_index = headers.index(user) if user in headers else None
            if user_index is not None:
                people_mapping[user] = user_index

        for idx, header in enumerate(headers):
            header_clean = header.strip()
            for field_name, possible_names in column_name_mappings.items():
                if header_clean in possible_names:
                    mapping[field_name] = idx
                    break

        mapping.update(people_mapping)
        return mapping, people_mapping

    def _parse_row_to_feature(
        self,
        row_number: int,
        row: List[str],
        column_mapping: Dict[str, int],
        people_mapping: Dict[str, int],
    ) -> Optional[SynthPMFeatureEntity]:
        """Parse a row from Google Sheets to SynthPMFeatureEntity using column mapping.

        Args:
            row_number: Row number in the sheet.
            row: Row data from Google Sheets.
            column_mapping: Dictionary mapping field names to column indices.
            people_mapping: Dictionary mapping people names to column indices.

        Returns:
            SynthPMFeatureEntity or None if parsing fails.
        """
        try:

            def get_mapped_value(field_name: str) -> str:
                col_idx = column_mapping.get(field_name)
                if col_idx is not None and col_idx < len(row):
                    return row[col_idx].strip() if row[col_idx] else ""
                return ""

            def parse_date(date_str: str) -> Optional[datetime]:
                if not date_str:
                    return None
                try:
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                    return None
                except Exception:
                    return None

            def parse_int(value_str: str) -> Optional[int]:
                if not value_str or value_str.lower() in [
                    "",
                    "select",
                    "sum:",
                    "count:",
                ]:
                    return None
                try:
                    if ":" in value_str:
                        value_str = value_str.split(":")[-1].strip()
                    return int(float(value_str))
                except (ValueError, TypeError):
                    return None

            task_title = get_mapped_value("task_title")
            if not task_title:
                return None

            sprints = get_mapped_value("sprint")
            sprint_list = []
            last_sprint = None

            if sprints and sprints.strip() and sprints != "":
                items = [p.strip() for p in sprints.split(",")]
                sprint_list = items

                if items:
                    try:
                        max_item = max(items, key=lambda t: int(t.split(":", 1)[0]) if ":" in t else 0)
                        last_sprint = max_item
                    except (ValueError, IndexError):
                        last_sprint = items[-1]

            times = {key: int(get_mapped_value(key)) for key in people_mapping.keys() if get_mapped_value(key) not in ['0', '']}

            return SynthPMFeatureEntity(
                row_number=get_mapped_value("row_number"),
                sheet_row_number=row_number,
                task_title=task_title,
                epic=(
                    get_mapped_value("epic")
                    if get_mapped_value("epic") != "Select"
                    else None
                ),
                release=(
                    get_mapped_value("release")
                    if (
                        get_mapped_value("release") not in ["Select", ""]
                        and RELEASE_VERSION_PATTERN.match(
                            get_mapped_value("release").strip()
                        )
                    )
                    else None
                ),
                necessity=(
                    get_mapped_value("necessity")
                    if get_mapped_value("necessity") != "Select"
                    else None
                ),
                priority=(
                    get_mapped_value("priority")
                    if get_mapped_value("priority") != "Select"
                    else None
                ),
                status=(
                    get_mapped_value("status")
                    if get_mapped_value("status") != "Select"
                    else None
                ),
                eta_hours=parse_int(get_mapped_value("eta_hours")),
                total_hours=parse_int(get_mapped_value("total_hours")),
                departments=(
                    get_mapped_value("departments")
                    if get_mapped_value("departments") != "Select"
                    else None
                ),
                involved_people=(
                    get_mapped_value("involved_people")
                    if get_mapped_value("involved_people") != "Select"
                    else None
                ),
                ai=(
                    get_mapped_value("ai")
                    if get_mapped_value("ai") != "Select"
                    else None
                ),
                backend=(
                    get_mapped_value("backend")
                    if get_mapped_value("backend") != "Select"
                    else None
                ),
                frontend=(
                    get_mapped_value("frontend")
                    if get_mapped_value("frontend") != "Select"
                    else None
                ),
                devops=(
                    get_mapped_value("devops")
                    if get_mapped_value("devops") != "Select"
                    else None
                ),
                ui_ux=(
                    get_mapped_value("ui_ux")
                    if get_mapped_value("ui_ux") != "Select"
                    else None
                ),
                creation_date=parse_date(get_mapped_value("creation_date")),
                implementation_start_date=parse_date(
                    get_mapped_value("implementation_start_date"),
                ),
                deadline=parse_date(get_mapped_value("deadline")),
                sprint=(
                    get_mapped_value("sprint")
                    if get_mapped_value("sprint") not in ["Select", ""]
                    else None
                ),
                last_sprint=last_sprint if "last_sprint" in locals() else None,
                sprint_list=sprint_list if "sprint_list" in locals() else None,
                dependencies=(
                    get_mapped_value("dependencies")
                    if get_mapped_value("dependencies") != "Select"
                    else None
                ),
                department_deps=(
                    get_mapped_value("department_deps")
                    if get_mapped_value("department_deps") not in ["Select", ""]
                    else None
                ),
                initial_delivery_time=parse_date(
                    get_mapped_value("initial_delivery_time"),
                ),
                description=(
                    get_mapped_value("description")
                    if get_mapped_value("description") != ""
                    else None
                ),
                acceptance_criteria=(
                    get_mapped_value("acceptance_criteria")
                    if get_mapped_value("acceptance_criteria") != ""
                    else None
                ),
                test_cases=(
                    get_mapped_value("test_cases")
                    if get_mapped_value("test_cases") != ""
                    else None
                ),
                po_notes=(
                    get_mapped_value("po_notes")
                    if get_mapped_value("po_notes") != ""
                    else None
                ),
                jira_issue_key=(
                    get_mapped_value("jira_issue_key")
                    if get_mapped_value("jira_issue_key")
                    else None
                ),
                developer_board_issue_key=get_mapped_value("developer_board_issue_key")
                if get_mapped_value("developer_board_issue_key")
                else None,
                version=get_mapped_value("version")
                if get_mapped_value("version")
                else None,
                times=times,
            )
        except Exception as e:
            LOGGER.error(f"Error parsing row {row_number}: {e}")
            return None

    @staticmethod
    def _number_to_column_letter(col_num: int) -> str:
        """Convert column number to letter (1 -> A, 27 -> AA, etc.).

        Args:
            col_num: Column number (1-indexed).

        Returns:
            Column letter string.
        """
        result = ""
        while col_num > 0:
            col_num -= 1
            result = chr(col_num % 26 + ord("A")) + result
            col_num //= 26
        return result
