"""Mixin for data parsing operations in SynthPM."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.services import SynthPMColumnMappingService
from jira_telegram_bot.entities.synth_pm.services import SynthPMDateService
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class DataParsingMixin:
    """Mixin for data parsing operations."""

    user_config: UserConfigInterface

    def parse_row_to_feature(
        self,
        row_number: int,
        row: List[str],
        headers: List[str],
    ) -> Optional[SynthPMFeatureEntity]:
        """Parse a row from Google Sheets to SynthPMFeatureEntity.

        Args:
            row_number: Row number in the sheet
            row: Row data from Google Sheets
            headers: Sheet headers

        Returns:
            SynthPMFeatureEntity or None if parsing fails
        """
        try:
            column_mapping = SynthPMColumnMappingService.create_column_mapping(headers)
            people_mapping = self._create_people_mapping(headers)

            def get_mapped_value(field_name: str) -> str:
                col_idx = column_mapping.get(field_name)
                if col_idx is not None and col_idx < len(row):
                    return row[col_idx].strip()
                return ""

            def parse_int(value_str: str) -> Optional[int]:
                if not value_str or value_str.strip() == "":
                    return None
                try:
                    return int(float(value_str))
                except (ValueError, TypeError):
                    return None

            task_title = get_mapped_value("task_title")
            if not task_title:
                return None

            # Handle multiple sprints
            sprints = get_mapped_value("sprint")
            sprint_list = []
            last_sprint = None

            if sprints and sprints.strip():
                if "|" in sprints:
                    sprint_list = [s.strip() for s in sprints.split("|") if s.strip()]
                else:
                    sprint_list = [sprints.strip()]
                last_sprint = sprint_list[-1] if sprint_list else None

            # Parse people times
            times = {}
            for person_name, col_idx in people_mapping.items():
                if col_idx < len(row):
                    time_value = row[col_idx].strip()
                    if time_value and time_value != "0":
                        parsed_time = parse_int(time_value)
                        if parsed_time:
                            times[person_name] = parsed_time

            return SynthPMFeatureEntity(
                row_number=parse_int(get_mapped_value("row_number")) or row_number - 1,
                sheet_row_number=row_number,
                task_title=task_title,
                epic=get_mapped_value("epic") or None,
                release=get_mapped_value("release") or None,
                version=get_mapped_value("version") or None,
                necessity=get_mapped_value("necessity") or None,
                priority=get_mapped_value("priority") or None,
                status=get_mapped_value("status") or None,
                eta_hours=parse_int(get_mapped_value("eta_hours")),
                total_hours=parse_int(get_mapped_value("total_hours")),
                departments=get_mapped_value("departments") or None,
                involved_people=get_mapped_value("involved_people") or None,
                ai=get_mapped_value("ai") or None,
                backend=get_mapped_value("backend") or None,
                frontend=get_mapped_value("frontend") or None,
                devops=get_mapped_value("devops") or None,
                ui_ux=get_mapped_value("ui_ux") or None,
                creation_date=SynthPMDateService.parse_date_string(
                    get_mapped_value("creation_date"),
                ),
                implementation_start_date=SynthPMDateService.parse_date_string(
                    get_mapped_value("implementation_start_date"),
                ),
                deadline=SynthPMDateService.parse_date_string(
                    get_mapped_value("deadline"),
                ),
                sprint=last_sprint,
                sprint_list=sprint_list if sprint_list else None,
                dependencies=get_mapped_value("dependencies") or None,
                initial_delivery_time=SynthPMDateService.parse_date_string(
                    get_mapped_value("initial_delivery_time"),
                ),
                description=get_mapped_value("description") or None,
                acceptance_criteria=get_mapped_value("acceptance_criteria") or None,
                test_cases=get_mapped_value("test_cases") or None,
                po_notes=get_mapped_value("po_notes") or None,
                jira_issue_key=get_mapped_value("jira_issue_key") or None,
                developer_board_issue_key=get_mapped_value("developer_board_issue_key")
                or None,
                times=times if times else None,
            )

        except Exception as e:
            LOGGER.error(f"Error parsing row {row_number}: {e}")
            return None

    def _create_people_mapping(self, headers: List[str]) -> Dict[str, int]:
        """Create mapping for people columns.

        Args:
            headers: Sheet headers

        Returns:
            Dictionary mapping person names to column indices
        """
        people_mapping = {}

        for user in self.user_config.list_all_users_google_sheet_names():
            try:
                user_index = headers.index(user)
                people_mapping[user] = user_index
            except ValueError:
                continue

        return people_mapping
