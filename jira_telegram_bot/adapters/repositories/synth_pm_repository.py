"""Repository implementation for SynthPM operations."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from typing import List
from typing import Optional
from typing import Tuple

import jdatetime

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.release_notes import SprintInfo
from jira_telegram_bot.entities.synth_pm.change_tracker import SynthPMChangeTracker
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMSheetSyncStatus
from jira_telegram_bot.entities.synth_pm.change_tracker import FeatureSnapshot
from jira_telegram_bot.entities.synth_pm.constants import (
    STATUS_DESCRIPTIONS,
    SynthPMStatus,
)
from jira_telegram_bot.entities.synth_pm.department_dependency_calculator import (
    DepartmentDependencyCalculator,
)
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.interfaces.synth_pm_repository_interface import (
    SynthPMRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class SynthPMRepository(SynthPMRepositoryInterface):
    """Repository implementation for SynthPM operations."""

    def __init__(
        self,
        google_sheet_client: GoogleSheetClient,
        jira_repository: TaskManagerRepositoryInterface,
        settings: SynthPMSettings,
        user_config: UserConfigInterface,
    ):
        """Initialize the repository.

        Args:
            google_sheet_client: Google Sheets client
            jira_repository: Jira repository interface
            settings: SynthPM settings
        """
        self.google_sheet_client = google_sheet_client
        self.jira_repository = jira_repository
        self.settings = settings
        self.sync_status_file = Path(
            f"{DEFAULT_PATH}/data/synth_developer_board_sync_status.json",
        )
        self.change_tracker_file = Path(
            f"{DEFAULT_PATH}/data/synth_pm_change_tracker.json",
        )
        self.user_config = user_config
        self.developer_board_id = self.jira_repository.get_board_id(
            self.settings.developer_board_project_key,
        )
        self.pm_board_id = self.jira_repository.get_board_id(
            self.settings.pm_project_key,
        )

    async def get_developer_board_features(self) -> List[SynthPMFeatureEntity]:
        """Get all eatures from Google Sheets.

        Returns:
            List of eature entities
        """
        try:
            # TODO: get the range of headers dynamically.
            values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                f"{self.settings.developer_board_worksheet_name}!A:AY",
            )

            if not values or len(values) < 2:
                LOGGER.warning("No data found in Features sheet")
                return []

            headers = values[0]
            column_mapping, people_mapping = self._create_column_mapping(headers)

            data_rows = values[1:]
            features = []

            for idx, row in enumerate(data_rows, start=2):
                if len(row) < 2:
                    continue



                feature = self._parse_row_to_feature_with_mapping(
                    idx,
                    row,
                    column_mapping,
                    people_mapping
                )
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
        updates: Dict[str, any],
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
            headers_values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
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
                    col_letter = self._number_to_column_letter(
                        col_idx + 1,
                    )
                    range_name = f"{self.settings.developer_board_worksheet_name}!{col_letter}{row_number}"

                    success = await self.google_sheet_client.update_cells(
                        self.settings.google_sheets_id,
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

    async def create_jira_task_from_feature(
        self,
        feature: SynthPMFeatureEntity,
    ) -> Optional[str]:
        """Create a PM Board Jira task from a feature.
        Note: task creation moved to separate method.

        Args:
            feature: feature entity

        Returns:
            PM Board Jira issue key if successful, None otherwise
        """
        # Start and target end dates are extracted and set for each task
        try:
            feature_dates_str = self.extract_dates_from_feature_in_str(feature)

            epic_link = None
            if feature.epic and feature.epic.strip() and feature.epic != "Select":
                _, epic_key = self._create_epic_if_not_exists(
                    feature.epic,
                    self.settings.pm_project_key,
                )
                epic_link = epic_key

            jira_status = self._determine_jira_status(feature)

            components = self._map_components(feature)
            labels = [feature.involved_people] if feature.involved_people else []
            labels = labels + [f"PM-{feature.row_number}"]
            pm_board_task_data = TaskData(
                project_key=self.settings.pm_project_key,
                summary=feature.task_title,
                description=feature.description or "",
                task_type="Task",
                priority=self._map_priority(feature.priority),
                epic_link=epic_link,
                labels=labels,
                components=components,
                story_points=feature.total_hours / 8 if feature.total_hours else 0,
                assignee=None,
                due_date=feature_dates_str.get("due_date"),
                target_start=feature_dates_str.get("target_start"),
                target_end=feature_dates_str.get("target_end"),
            )

            # Smart sprint assignment for PM Board
            if feature.sprint_list and len(feature.sprint_list) > 0:
                # Get current Jalali year for sprint creation if needed
                current_jalali_year = jdatetime.datetime.now().year
                
                # Sort sprints by sprint ID (earliest first)
                sorted_sprints = sorted(
                    feature.sprint_list,
                    key=lambda s: int(s.split(':')[0]) if ':' in s else 0
                )
                
                # Find the closest active or future sprint
                selected_sprint = None
                selected_sprint_info = None
                
                for s in sorted_sprints:
                    temp_sprint_info = SprintInfo.parse_sprint_string(s)
                    sprint_name = f"{self.settings.pm_project_key} Sprint {temp_sprint_info.sprint_id}"
                    temp_sprint = self.jira_repository.get_sprint_by_name(
                        sprint_name,
                        self.pm_board_id,
                    )
                    
                    if temp_sprint is not None:
                        if temp_sprint.get('state') == 'active':
                            # Found an active sprint - use it
                            selected_sprint = temp_sprint
                            selected_sprint_info = temp_sprint_info
                            LOGGER.info(f"PM Board: Assigning feature {feature.task_title} to active sprint {temp_sprint_info.sprint_id}")
                            break
                        elif temp_sprint.get('state') == 'future' and not selected_sprint:
                            # Found a future sprint - remember it but keep looking for active
                            selected_sprint = temp_sprint
                            selected_sprint_info = temp_sprint_info
                            LOGGER.info(f"PM Board: Found future sprint {temp_sprint_info.sprint_id} for feature {feature.task_title}")
                
                # If no active/future sprint found, create the earliest one
                if not selected_sprint:
                    selected_sprint_info = SprintInfo.parse_sprint_string(sorted_sprints[0])
                    sprint_name = f"{self.settings.pm_project_key} Sprint {selected_sprint_info.sprint_id}"
                    # Double-check if sprint exists before creating
                    selected_sprint = self.jira_repository.get_sprint_by_name(
                        sprint_name,
                        self.pm_board_id,
                    )
                    if not selected_sprint:
                        LOGGER.info(f"PM Board: No active/future sprint found, will create sprint {selected_sprint_info.sprint_id} for feature {feature.task_title}")
                        selected_sprint = self._create_sprint(
                            selected_sprint_info, 
                            current_jalali_year,
                            self.pm_board_id,
                            self.settings.pm_project_key
                        )
                    else:
                        LOGGER.info(f"PM Board: Sprint {sprint_name} already exists (state: {selected_sprint.get('state')}), using it for feature {feature.task_title}")
                
                # Assign the sprint ID to the task
                if selected_sprint:
                    pm_board_task_data.sprint_id = selected_sprint.get('id')
                    LOGGER.debug(f"PM Board: Assigned sprint ID {selected_sprint.get('id')} to task {feature.task_title}")
            elif feature.sprint:
                # Fallback to old logic if sprint_list is not available but sprint field is
                pm_board_task_data.sprint_id = self._get_sprint_id(
                    "Active",
                    self.pm_board_id,
                )

            self._create_release_not_exist(
                feature,
                pm_board_task_data,
                self.settings.pm_project_key,
            )

            pm_board_issue = self.jira_repository.create_task(pm_board_task_data)
            LOGGER.info(
                f"Created PM Board task {pm_board_issue.key} for feature:"
                f"{feature.task_title}: {self.jira_repository.get_issue_url(pm_board_issue)}",
            )

            try:
                self._transition_issue_to_status(pm_board_issue.key, jira_status)
            except Exception as e:
                LOGGER.warning(f"Could not transition issue to {jira_status}: {e}")

            await self.update_developer_board_feature(
                feature.sheet_row_number,
                {"jira_issue_key": pm_board_issue.key},
            )

            return pm_board_issue.key

        except Exception as e:
            error_msg = (
                f"Error creating Jira tasks for feature {feature.task_title}: {e}"
            )
            LOGGER.error(error_msg)

            LOGGER.debug(
                f"Feature data: epic='{feature.epic}', deadline='{feature.deadline}' (type: {type(feature.deadline)})",
            )

            return None

    def extract_dates_from_feature_in_str(self, feature) -> Dict[str, Optional[str]]:
        due_date = None
        if feature.deadline:
            if isinstance(feature.deadline, str):
                due_date = feature.deadline
            else:
                due_date = feature.deadline.strftime("%Y-%m-%d")
        target_start = None
        if feature.implementation_start_date:
            if isinstance(feature.implementation_start_date, str):
                target_start = feature.implementation_start_date
            else:
                target_start = feature.implementation_start_date.strftime("%Y-%m-%d")
        target_end = None
        if feature.deadline:
            if isinstance(feature.deadline, str):
                target_end = feature.deadline
            else:
                target_end = feature.deadline.strftime("%Y-%m-%d")
        result = {
            "due_date": due_date,
            "target_start": target_start,
            "target_end": target_end
        }
        return result

    def _create_release_not_exist(
        self,
        feature: SynthPMFeatureEntity,
        task_data: TaskData,
        project_key: str,
    ):
        if feature.release:
            if not self.jira_repository.release_exist(project_key, feature.release):
                self.jira_repository.create_release(
                    project_key=project_key,
                    name=feature.release,
                )
            task_data.releases = [feature.release]
        if feature.version:
            if not self.jira_repository.release_exist(project_key, feature.version):
                self.jira_repository.create_release(
                    project_key=project_key,
                    name=feature.version,
                )
            task_data.releases = (
                task_data.releases + [feature.version]
                if task_data.releases
                else [feature.version]
            )

    def _create_release_not_exist_during_update(
        self,
        feature: SynthPMFeatureEntity,
        project_key: str,
    ):
        if feature.release:
            if not self.jira_repository.release_exist(project_key, feature.release):
                self.jira_repository.create_release(
                    project_key=project_key,
                    name=feature.release,
                )
        if feature.version:
            if not self.jira_repository.release_exist(project_key, feature.version):
                self.jira_repository.create_release(
                    project_key=project_key,
                    name=feature.version,
                )

    async def update_jira_task_from_feature(
        self,
        feature: SynthPMFeatureEntity,
    ) -> bool:
        """Update an existing Jira task from a feature.

        Args:
            feature: feature entity

        Returns:
            True if successful, False otherwise
        """
        try:
            if not feature.jira_issue_key:
                LOGGER.warning(f"No Jira issue key for feature: {feature.task_title}")
                return False

            issue = self.jira_repository.get_issue(feature.jira_issue_key)
            if not issue:
                LOGGER.warning(f"Jira issue {feature.jira_issue_key} not found")
                return False

            update_fields = {}

            if feature.task_title:
                if feature.task_title != issue.fields.summary:
                    update_fields["summary"] = feature.task_title

            if feature.release != None or feature.version != None:
                if set([feature.release, feature.version]) != set(
                    issue.fields.fixVersions,
                ):  # Replace with actual custom field ID
                    self._create_release_not_exist_during_update(
                        feature,
                        self.settings.pm_project_key,
                    )
                    update_fields["fixVersions"] = [
                        {"name": release}
                        for release in [feature.release, feature.version]
                        if release
                    ]

            if feature.description:
                if feature.description != issue.fields.description:
                    update_fields["description"] = feature.description

            if feature.priority:
                feature_priority = self._map_priority(feature.priority)
                if feature_priority != issue.fields.priority.name:
                    update_fields["priority"] = {
                        "name": feature_priority,
                    }

            feature_dates_str = self.extract_dates_from_feature_in_str(feature)
            if feature_dates_str:
                if (
                    feature_dates_str.get("target_start")
                    != issue.fields.__dict__.get(self.jira_repository.jira_target_start_id)
                ):
                    update_fields[self.jira_repository.jira_target_start_id] = feature_dates_str.get("target_start")

                if (
                    feature_dates_str.get("target_end")
                    != issue.fields.__dict__.get(self.jira_repository.jira_target_end_id)
                ):
                    update_fields[self.jira_repository.jira_target_end_id] = feature_dates_str.get("target_end")

            if (
                feature.sprint is None
                and issue.fields.__dict__.get(self.jira_repository.jira_sprint_id)
                is not None
            ):
                update_fields[self.jira_repository.jira_sprint_id] = None

                # For PM board, no need to change the sprint. It is only in active sprint or no sprint

            if feature.deadline:
                feature_duedate = feature.deadline.strftime("%Y-%m-%d")
                if feature_duedate != issue.fields.duedate:
                    update_fields["duedate"] = feature_duedate

            if feature.total_hours:
                if (
                    feature.total_hours * 3600
                    != issue.fields.timetracking.originalEstimateSeconds
                ):
                    logged_time = self.jira_repository.get_issue_spent_time_in_seconds(
                        issue.key,
                    )
                    remaining_estimate = (
                        int((feature.total_hours * 3600 - logged_time) / 3600)
                        if feature.total_hours * 3600 - logged_time > 0
                        else 0
                    )
                    update_fields["timetracking"] = {
                        "originalEstimate": f"{feature.total_hours}h",
                        "remainingEstimate": f"{remaining_estimate}h",
                    }

            # Update components based on feature department flags
            components = self._map_components(feature)
            current_components = [comp.name for comp in issue.fields.components]
            if set(current_components) != set(components):
                update_fields["components"] = [{"name": comp} for comp in components]

            if feature.status:
                jira_status = self._determine_jira_status(feature)
                current_jira_status = issue.fields.status.name
                if current_jira_status.lower() != jira_status.lower():
                    self._transition_issue_to_status(issue.key, jira_status)

            if feature.involved_people and issue.fields.issuetype.name == "Task":
                developer_issue = self.jira_repository.get_issue(
                    feature.developer_board_issue_key,
                )
                developer_assignee = (
                    developer_issue.fields.assignee.name
                    if developer_issue and developer_issue.fields.assignee
                    else None
                )
                if developer_assignee:
                    sheet_username = self.user_config.get_user_config_by_jira_username(
                        developer_assignee,
                    ).google_sheet_name
                    for idx, label in enumerate(issue.fields.labels):
                        if sheet_username in label:
                            label_index = idx
                            if issue.fields.labels[
                                label_index
                            ] != feature.involved_people.replace(" ", "-"):
                                update_fields["labels"] = list(
                                    set(issue.fields.labels)
                                    - {issue.fields.labels[label_index]}
                                ) + [feature.involved_people.replace(" ", "-")]
                                break
            elif feature.involved_people and issue.fields.issuetype.name == "Story":
                developer_issue = self.jira_repository.get_issue(
                    feature.developer_board_issue_key,
                )
                if developer_issue:
                    developer_assignee = [developer_issue.fields.assignee.name] if developer_issue.fields.assignee else []
                    subtasks_assignees = [
                        subtask_issue.fields.assignee.name
                        for subtask in developer_issue.fields.subtasks
                        if (subtask_issue := self.jira_repository.get_issue(subtask.key)) is not None
                        and subtask_issue.fields.assignee is not None
                    ]
                    all_assignees = list(set(developer_assignee + subtasks_assignees))
                    sheet_usernames = []
                    label_index = None
                    for assignee in all_assignees:
                        sheet_username = (
                            self.user_config.get_user_config_by_jira_username(
                                assignee,
                            ).google_sheet_name
                        )
                        sheet_usernames.append(sheet_username)
                        if label_index is None:
                            for i, label in enumerate(issue.fields.labels):
                                if label == sheet_username:
                                    label_index = i
                                    break
                        if label_index is not None:
                            names = [
                                name.strip(" ")
                                for name in issue.fields.labels[label_index].split("-")
                            ]
                            if set(sheet_usernames) != set(names):
                                update_fields["labels"] = list(
                                    set(issue.fields.labels) - {sheet_username}
                                ) + [feature.involved_people.replace(" ", "-")]

            else:
                LOGGER.warning(f"Invalid update. Not handled for {feature} and {issue}")

            if update_fields:
                update_fields["project"] = {"key": self.settings.pm_project_key}
                issue.update(fields=update_fields)
                LOGGER.info(f"Updated Jira task {feature.jira_issue_key}")

            return True

        except Exception as e:
            LOGGER.error(f"Error updating Jira task {feature.jira_issue_key}: {e}")
            return False

    async def get_release_notes(self) -> List[ReleaseNoteEntity]:
        """Get all release notes from Google Sheets.

        Returns:
            List of release note entities
        """
        try:
            values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                f"{self.settings.release_notes_worksheet_name}!A:AG",
            )

            if not values or len(values) < 2:
                LOGGER.warning("No data found in Release Notes sheet")
                return []

            headers = values[0]
            column_mapping = self._create_release_notes_column_mapping(headers)

            data_rows = values[1:]
            release_notes = []

            for idx, row in enumerate(data_rows, start=2):
                if len(row) < 2:
                    continue

                release_note = self._parse_row_to_release_note(idx, row, column_mapping)
                if release_note:
                    release_notes.append(release_note)

            LOGGER.info(f"Retrieved {len(release_notes)} release notes")
            return release_notes

        except Exception as e:
            LOGGER.error(f"Error retrieving release notes: {e}")
            return []

    async def get_release_note_by_version(
        self,
        version: str,
    ) -> Optional[ReleaseNoteEntity]:
        """Get a specific release note by version from Google Sheets.

        Args:
            version: Release version to search for

        Returns:
            ReleaseNoteEntity if found, None otherwise
        """
        try:
            release_notes = await self.get_release_notes()

            for release_note in release_notes:
                if release_note.release_version == version:
                    LOGGER.info(f"Found release note for version: {version}")
                    return release_note

            LOGGER.warning(f"Release note not found for version: {version}")
            return None

        except Exception as e:
            LOGGER.error(f"Error retrieving release note for version {version}: {e}")
            return None

    async def update_release_note(
        self,
        row_number: int,
        updates: Dict[str, any],
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
            headers_values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                headers_range,
            )

            if not headers_values:
                LOGGER.error(
                    "Could not retrieve headers for release notes column mapping",
                )
                return False

            headers = headers_values[0]
            column_mapping = self._create_release_notes_column_mapping(headers)

            for field, value in updates.items():
                if field in column_mapping:
                    col_idx = column_mapping[field]
                    col_letter = self._number_to_column_letter(col_idx + 1)
                    range_name = f"{self.settings.release_notes_worksheet_name}!{col_letter}{row_number}"

                    success = await self.google_sheet_client.update_cells(
                        self.settings.google_sheets_id,
                        range_name,
                        [[str(value) if value is not None else ""]],
                    )

                    if not success:
                        LOGGER.error(
                            f"Failed to update field {field} in release note row {row_number}",
                        )
                        return False
                else:
                    LOGGER.warning(
                        f"Field {field} not found in release notes column mapping, skipping",
                    )

            LOGGER.info(
                f"Successfully updated release note row {row_number} with {len(updates)} fields",
            )
            return True

        except Exception as e:
            LOGGER.error(f"Error updating release note row {row_number}: {e}")
            return False

    async def create_developer_board_task_from_feature(
        self,
        feature: SynthPMFeatureEntity,
        assignees: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Create a Jira task from a feature with sprint.

        Args:
            feature: feature entity
            assignees: List of assignee usernames for the task

        Returns:
            Jira issue key if successful, None otherwise
        """
        # Get current Persian/Jalali year for dynamic date handling
        current_jalali_year = jdatetime.datetime.now().year
        
        # TODO: If task has two sprints, handle it: get the first active sprint or future sprint as the sprint for the task
        # TODO: If the issue is only updated in the google sheet board (i.e its times and stuff, handle it)
        try:
            if not feature.jira_issue_key:
                LOGGER.error("Cannot create task without existing PM Board task")
                return None

            feature_dates_str = self.extract_dates_from_feature_in_str(feature)

            epic_link = None
            if feature.epic and feature.epic.strip() and feature.epic != "Select":
                _, epic_key = self._create_epic_if_not_exists(
                    feature.epic,
                    self.settings.developer_board_project_key,
                )
                epic_link = epic_key

            components = self._map_components(feature)

            if len(feature.sprint_list) > 1:
                # Sort sprints by sprint ID (first number when splitting by ':')
                sorted_sprints = sorted(
                    feature.sprint_list,
                    key=lambda s: int(s.split(':')[0]) if ':' in s else 0
                )
                
                # Find the closest active or future sprint
                sprint = None
                sprint_info = None
                active_sprint_found = False
                
                for s in sorted_sprints:
                    temp_sprint_info = SprintInfo.parse_sprint_string(s)
                    sprint_name = f"{self.settings.developer_board_project_key} Sprint {temp_sprint_info.sprint_id}"
                    temp_sprint = self.jira_repository.get_sprint_by_name(
                        sprint_name,
                        self.developer_board_id,
                    )
                    
                    if temp_sprint is not None:
                        if temp_sprint.get('state') == 'active':
                            # Found an active sprint - use it
                            sprint = temp_sprint
                            sprint_info = temp_sprint_info
                            active_sprint_found = True
                            LOGGER.info(f"Assigning feature {feature.task_title} to active sprint {sprint_info.sprint_id}")
                            break
                        elif temp_sprint.get('state') == 'future' and not sprint:
                            # Found a future sprint - remember it but keep looking for active
                            sprint = temp_sprint
                            sprint_info = temp_sprint_info
                            LOGGER.info(f"Found future sprint {sprint_info.sprint_id} for feature {feature.task_title}")
                
                # If no active/future sprint found, create the earliest one
                if not sprint:
                    sprint_info = SprintInfo.parse_sprint_string(sorted_sprints[0])
                    sprint_name = f"{self.settings.developer_board_project_key} Sprint {sprint_info.sprint_id}"
                    # Double-check if sprint exists before creating
                    sprint = self.jira_repository.get_sprint_by_name(
                        sprint_name,
                        self.developer_board_id,
                    )
                    if sprint:
                        LOGGER.info(f"Sprint {sprint_name} already exists (state: {sprint.get('state')}), using it for feature {feature.task_title}")
                    else:
                        LOGGER.info(f"No active/future sprint found, will create sprint {sprint_info.sprint_id} for feature {feature.task_title}")
                        sprint = None  # Will be created below
                    
            elif len(feature.sprint_list) == 1:
                sprint_info = SprintInfo.parse_sprint_string(feature.sprint_list[0])
                sprint_name = f"{self.settings.developer_board_project_key} Sprint {sprint_info.sprint_id}"
                sprint = self.jira_repository.get_sprint_by_name(
                    sprint_name,
                    self.developer_board_id,
                )
                if sprint is not None and sprint.get('state') == "closed":
                    return None # TODO test it. In this state, issue must not be created
                
            else:
                return None

            if sprint is None:
                LOGGER.info(f"Creating new sprint: {sprint_info.sprint_id} for feature {feature.task_title}")
                sprint = self._create_sprint(
                    sprint_info, 
                    current_jalali_year,
                    self.developer_board_id,
                    self.settings.developer_board_project_key
                )
                LOGGER.debug(f"Created sprint: {sprint}")
            elif sprint.get('state') == 'closed':
                LOGGER.warning(f"Cannot create task for feature {feature.task_title} - assigned sprint is closed")
                return None

            task_type = "Story" if len(assignees) > 1 else "Task"
            if task_type == "Task":
                labels = None
                description = feature.description
                story_points = feature.total_hours / 8 if feature.total_hours else 0
                assignee = assignees[0] if assignees else None
            else:
                labels = [f"PM-{feature.jira_issue_key}", feature.involved_people]
                description = (
                    f"🔗 *Linked to PM Board*: {self.jira_repository.get_issue_url_by_key(feature.jira_issue_key)}\n\n"
                    f"👥 *Assignees*: {', '.join(assignees) if assignees else 'Unassigned'}\n\n"
                    f"📝 *Original Time*: {feature.total_hours}h\n\n"
                    f"✍️ *Description*: {feature.description}"
                )
                story_points = None
                assignee = None  # Stories don't have direct assignee, use subtasks

            developer_board_task_data = TaskData(
                project_key=self.settings.developer_board_project_key,
                summary=f"{feature.task_title}",
                description=description,
                task_type=task_type,
                priority=self._map_priority(feature.priority),
                epic_link=epic_link,
                labels=labels,
                components=components,
                assignee=assignee,
                due_date=feature_dates_str.get("due_date"),
                story_points=story_points,
                target_start=feature_dates_str.get("target_start"),
                target_end=feature_dates_str.get("target_end"),
            )
            if sprint and sprint.get("state") != "closed":
                developer_board_task_data.sprint_id = sprint.get("id")
                developer_board_task_data.sprint_name = sprint.get("name")

            self._create_release_not_exist(
                feature,
                developer_board_task_data,
                self.settings.developer_board_project_key,
            )

            developer_board_issue = self.jira_repository.create_task(
                developer_board_task_data,
            )

            LOGGER.info(
                f"Created task {self.jira_repository.get_issue_url_by_key(developer_board_issue.key)}"
                f"for feature: {feature.task_title}",
            )

            if task_type == "Story":
                try:
                    subtask_keys = await self._create_subtasks_for_assignees(
                        developer_board_issue.key,
                        assignees,
                        feature,
                        sprint_info,
                        feature_dates_str
                    )
                    if subtask_keys:
                        LOGGER.info(
                            f"Created {len(subtask_keys)} subtasks for story {developer_board_issue.key}: {subtask_keys}",
                        )
                except Exception as e:
                    LOGGER.warning(
                        f"Could not create subtasks for {developer_board_issue.key}: {e}",
                    )

            try:
                self._link_issues(feature.jira_issue_key, developer_board_issue.key)
            except Exception as e:
                LOGGER.warning(
                    f"Could not link issues {feature.jira_issue_key} and {developer_board_issue.key}: {e}",
                )

            # Update the sheet with issue key
            await self.update_developer_board_feature(
                feature.sheet_row_number,
                {"developer_board_issue_key": developer_board_issue.key},
            )

            return developer_board_issue.key

        except Exception as e:
            LOGGER.error(f"Error creating task for feature {feature.task_title}: {e}")
            return None

    def _create_sprint(self, sprint_info, current_jalali_year, board_id: int, project_key: str):
        """Create a sprint in the specified board.
        
        Args:
            sprint_info: Sprint information
            current_jalali_year: Current Jalali year
            board_id: Board ID where sprint should be created
            project_key: Project key for sprint naming
            
        Returns:
            Created sprint object
        """
        start_date = sprint_info.start_date
        end_date = sprint_info.end_date
        start_date = jdatetime.JalaliToGregorian(
                    current_jalali_year,
                    int(start_date.split("-")[0]),
                    int(start_date.split("-")[1]),
                )
        end_date = jdatetime.JalaliToGregorian(
                    current_jalali_year,
                    int(end_date.split("-")[0]),
                    int(end_date.split("-")[1]),
                )
        start_date = start_date.getGregorianList()
        end_date = end_date.getGregorianList()
        start_date_str = (
                    f"{start_date[0]}-{start_date[1]:02d}-{start_date[2]:02d}"
                )
        end_date_str = f"{end_date[0]}-{end_date[1]:02d}-{end_date[2]:02d}"
        sprint = self.jira_repository.create_sprint(
                    board_id=board_id,
                    sprint_name=f"{project_key} Sprint {sprint_info.sprint_id}",
                    start_date=start_date_str,
                    end_date=end_date_str,
                    goal=f"{sprint_info.start_date} to {sprint_info.end_date}",
                )
        
        return sprint

    async def update_developer_board_task_from_feature(
        self,
        feature: SynthPMFeatureEntity,
        feature_assignees: Optional[List[str]] = None,
    ) -> bool:
        """Update an existing Jira task from a feature.

        Args:
            feature: feature entity
            feature_assignees: List of assignee usernames for the task

        Returns:
            True if successful, False otherwise
        """
        # Assignee updates and sub-task reassignment are handled in _update_assignees_and_subtasks method
        try:
            if not feature.developer_board_issue_key:
                LOGGER.warning(f"No issue key for feature: {feature.task_title}")
                return False

            # Similar to update_jira_task_from_feature but for
            issue = self.jira_repository.get_issue(feature.developer_board_issue_key)
            if not issue:
                LOGGER.warning(f"issue {feature.developer_board_issue_key} not found")
                return False

            update_fields = {}
            
            feature_dates_str = self.extract_dates_from_feature_in_str(feature)
            
            # Update dates for the story/task (handle both setting and clearing)
            target_start_new = feature_dates_str.get("target_start")
            target_start_current = issue.fields.__dict__.get(self.jira_repository.jira_target_start_id)
            if target_start_new != target_start_current:
                update_fields[self.jira_repository.jira_target_start_id] = target_start_new
            
            target_end_new = feature_dates_str.get("target_end")
            target_end_current = issue.fields.__dict__.get(self.jira_repository.jira_target_end_id)
            if target_end_new != target_end_current:
                update_fields[self.jira_repository.jira_target_end_id] = target_end_new
            
            due_date_new = feature_dates_str.get("due_date")
            due_date_current = issue.fields.duedate
            if due_date_new != due_date_current:
                update_fields["duedate"] = due_date_new
            
            # Handle epic changes
            if feature.epic and feature.epic.strip() and feature.epic != "Select":
                # Check if this is a subtask - subtasks cannot have epics assigned directly
                if issue.fields.issuetype.name == "Sub-task":
                    LOGGER.debug(f"Skipping epic assignment for subtask {issue.key} - subtasks inherit epic from parent issue")
                else:
                    _, epic_key = self._create_epic_if_not_exists(
                        feature.epic,
                        self.settings.developer_board_project_key,
                    )
                    
                    current_epic = getattr(issue.fields, self.jira_repository.jira_epic_link_id, None)
                    if current_epic != epic_key:
                        update_fields[self.jira_repository.jira_epic_link_id] = epic_key
                    
                    # Subtasks automatically inherit epic from parent story, no need to update them explicitly
                    if issue.fields.issuetype.name == "Story":
                        LOGGER.debug(f"Epic updated for story {issue.key} to {epic_key} - subtasks will automatically inherit this epic")

            elif not feature.epic or feature.epic == "Select":
                # Remove epic link if no epic specified
                # Check if this is a subtask - subtasks cannot have epics modified directly
                if issue.fields.issuetype.name == "Sub-task":
                    LOGGER.debug(f"Skipping epic removal for subtask {issue.key} - subtasks inherit epic from parent issue")
                else:
                    current_epic = getattr(issue.fields, self.jira_repository.jira_epic_link_id, None)
                    if current_epic:
                        update_fields[self.jira_repository.jira_epic_link_id] = None
                    
                    # Subtasks automatically inherit epic from parent story, no need to remove epic from them explicitly
                    if issue.fields.issuetype.name == "Story":
                        LOGGER.debug(f"Epic removed from story {issue.key} - subtasks will automatically inherit this change")
            if feature_dates_str:
                if (
                    feature_dates_str.get("target_start")
                    != issue.fields.__dict__.get(self.jira_repository.jira_target_start_id)
                ):
                    update_fields[self.jira_repository.jira_target_start_id] = feature_dates_str.get("target_start")

                if (
                    feature_dates_str.get("target_end")
                    != issue.fields.__dict__.get(self.jira_repository.jira_target_end_id)
                ):
                    update_fields[self.jira_repository.jira_target_end_id] = feature_dates_str.get("target_end")

            if feature.task_title:
                if feature.task_title != issue.fields.summary:
                    update_fields["summary"] = feature.task_title
                    # Update summaries of sub-tasks if feature.task_title changed
                    # TODO: refactor it to some place else
                    if feature.task_title and issue.fields.issuetype.name == "Story":
                        for subtask in issue.fields.subtasks:
                            subtask_issue = self.jira_repository.get_issue(subtask.key)
                            if subtask_issue is not None:
                                if subtask_issue.fields.summary != feature.task_title:
                                    subtask_issue.update(fields={"summary": feature.task_title})
                                    LOGGER.info(f"Updated summary for subtask {subtask.key} to '{feature.task_title}'")
                            else:
                                LOGGER.warning(f"Subtask {subtask.key} not found, skipping summary update")

            # Update fixVersions (handle both setting and clearing)
            feature_versions = set([v for v in [feature.release, feature.version] if v])
            current_versions = set([field.name for field in issue.fields.fixVersions])
            if feature_versions != current_versions:
                if feature_versions:  # Only create releases if we're setting versions
                    self._create_release_not_exist_during_update(
                        feature,
                        self.settings.developer_board_project_key,
                    )
                update_fields["fixVersions"] = [
                    {"name": release}
                    for release in [feature.release, feature.version]
                    if release
                ] if feature_versions else []

            # Handle sprint updates using the same logic as create method
            current_jalali_year = jdatetime.datetime.now().year
            target_sprint = None
            
            # Handle sprint assignment based on feature.sprint_list (multiple sprints possible)
            if feature.sprint_list and len(feature.sprint_list) > 0:
                if len(feature.sprint_list) > 1:
                    # Sort sprints by the first number when splitting by ':'
                    sorted_sprints = sorted(
                        feature.sprint_list,
                        key=lambda s: int(s.split(':')[0]) if ':' in s else 0
                    )
                    
                    # Find first active or future sprint (don't create in loop)
                    for s in sorted_sprints:
                        sprint_info = SprintInfo.parse_sprint_string(s)
                        sprint_name = f"{self.settings.developer_board_project_key} Sprint {sprint_info.sprint_id}"
                        LOGGER.debug(f"Looking for sprint: '{sprint_name}' on board {self.developer_board_id}")
                        sprint = self.jira_repository.get_sprint_by_name(
                            sprint_name,
                            self.developer_board_id,
                        )
                        LOGGER.debug(f"Sprint lookup result: {sprint}")
                        if sprint is not None:
                            if sprint.get('state') == "closed":
                                LOGGER.debug(f"Sprint {sprint_name} is closed, continuing search")
                                continue
                            elif sprint.get('state') == "active":
                                LOGGER.debug(f"Found active sprint {sprint_name}")
                                target_sprint = sprint
                                break
                            elif sprint.get('state') == 'future' and not target_sprint:
                                # Found a future sprint - remember it but keep looking for active
                                LOGGER.debug(f"Found future sprint {sprint_name}")
                                target_sprint = sprint
                    
                    # If no active sprint found, use first non-closed sprint or create first sprint
                    if target_sprint is None:
                        sprint_info = SprintInfo.parse_sprint_string(sorted_sprints[0])
                        sprint_name = f"{self.settings.developer_board_project_key} Sprint {sprint_info.sprint_id}"
                        sprint = self.jira_repository.get_sprint_by_name(
                            sprint_name,
                            self.developer_board_id,
                        )
                        if sprint is None:
                            target_sprint = self._create_sprint(
                                sprint_info, 
                                current_jalali_year,
                                self.developer_board_id,
                                self.settings.developer_board_project_key
                            )
                        elif sprint.get('state') != "closed":
                            target_sprint = sprint
                        
                elif len(feature.sprint_list) == 1:
                    sprint_info = SprintInfo.parse_sprint_string(feature.sprint_list[0])
                    sprint_name = f"{self.settings.developer_board_project_key} Sprint {sprint_info.sprint_id}"
                    LOGGER.debug(f"Looking for single sprint: '{sprint_name}' on board {self.developer_board_id}")
                    sprint = self.jira_repository.get_sprint_by_name(
                        sprint_name,
                        self.developer_board_id,
                    )
                    LOGGER.debug(f"Single sprint lookup result: {sprint}")
                    
                    if sprint is not None and sprint.get('state') != "closed":
                        LOGGER.debug(f"Found existing non-closed sprint {sprint_name}")
                        target_sprint = sprint
                    elif sprint is None:
                        # Create sprint if it doesn't exist
                        LOGGER.info(f"Creating new single sprint: {sprint_name}")
                        target_sprint = self._create_sprint(
                            sprint_info, 
                            current_jalali_year,
                            self.developer_board_id,
                            self.settings.developer_board_project_key
                        )
                        LOGGER.debug(f"Created single sprint: {target_sprint}")
                    # If sprint is closed, target_sprint remains None (will remove sprint assignment)
            # If feature.sprint_list is empty or None, target_sprint remains None (will remove sprint assignment)
            
            # Update sprint assignment based on target_sprint
            current_sprint_data = issue.fields.__dict__.get(self.jira_repository.jira_sprint_id)
            current_sprint_id = None
            
            # Extract current sprint ID from Jira field (handles Jira's sprint field format)
            if current_sprint_data and isinstance(current_sprint_data, list) and len(current_sprint_data) > 0:
                sprint_str = current_sprint_data[0]
                if "id=" in sprint_str:
                    id_start = sprint_str.find("id=") + 3
                    id_end = sprint_str.find(",", id_start)
                    if id_end == -1:
                        id_end = sprint_str.find("]", id_start)
                    current_sprint_id = int(sprint_str[id_start:id_end])
            
            # Compare and update sprint assignment
            if target_sprint is None:
                # Remove sprint assignment if no valid sprint found
                if current_sprint_data is not None:
                    update_fields[self.jira_repository.jira_sprint_id] = None
                    LOGGER.debug(f"Removing sprint assignment from {issue.key} - no valid sprint found")
            else:
                # Assign to target sprint if different
                target_sprint_id = target_sprint.get("id")
                if current_sprint_id != target_sprint_id:
                    update_fields[self.jira_repository.jira_sprint_id] = target_sprint_id
                    LOGGER.debug(f"Updating sprint for {issue.key} from {current_sprint_id} to {target_sprint_id}")

            if feature.priority:
                feature_priority = self._map_priority(feature.priority)
                if feature_priority.lower() != issue.fields.priority.name.lower():
                    update_fields["priority"] = {
                        "name": self._map_priority(feature.priority),
                    }

            if feature.deadline:
                feature_deadline = feature.deadline.strftime("%Y-%m-%d")
                if feature_deadline != issue.fields.duedate:
                    update_fields["duedate"] = feature_deadline

            check_for_task_assignee_change = (
                feature_assignees
                and len(feature_assignees) == 1
                and issue.fields.issuetype.name == "Task"
            )
            check_for_change_from_story_to_task = (
                feature_assignees
                and len(feature_assignees) == 1
                and issue.fields.issuetype.name == "Story"
            )
            check_for_story_assignee_update = (
                feature_assignees
                and len(feature_assignees) == 1
                and issue.fields.issuetype.name == "Story"
            )
            check_for_change_from_task_to_story = (
                feature_assignees
                and len(feature_assignees) > 1
                and issue.fields.issuetype.name == "Task"
            )
            check_for_updating_assignees = (
                feature_assignees
                and len(feature_assignees) > 1
                and issue.fields.issuetype.name == "Story"
            )
            
            if check_for_task_assignee_change:
                assignee_name = issue.fields.assignee.name if issue.fields.assignee else None
                if assignee_name != feature_assignees[0]:
                    update_fields["assignee"] = {"name": feature_assignees[0]}
            elif check_for_change_from_story_to_task:
                # Story to task conversion
                update_fields["issuetype"] = {"name": "Task"}
                update_fields["assignee"] = {
                    "name": feature_assignees[0],
                }

            elif check_for_story_assignee_update:
                await self._update_assignees_and_subtasks(
                    feature.developer_board_issue_key,
                    feature_assignees,
                    feature,
                )

                update_fields["labels"] = [
                    {
                        "name": list(
                            set(issue.fields.labels + [feature.involved_people]),
                        ),
                    },
                ]
            elif check_for_change_from_task_to_story:
                # Change task type to Story and manage assignees accordingly
                update_fields["issuetype"] = {"name": "Story"}
                await self._update_assignees_and_subtasks(
                    feature.developer_board_issue_key,
                    feature_assignees,
                    feature,
                )
            elif check_for_updating_assignees:
                await self._update_assignees_and_subtasks(
                    feature.developer_board_issue_key,
                    feature_assignees,
                    feature,
                )
            # Update story points based on ETA hours
            if feature.total_hours and issue.fields.issuetype.name == "Task":
                if feature_assignees and len(feature_assignees) > 1:
                    update_fields["timetracking"] = {
                        "originalEstimate": None,
                        "remainingEstimate": None,
                    }
                else:
                    if (
                        feature.total_hours * 3600
                        != issue.fields.timetracking.originalEstimateSeconds
                    ):
                        time_logged = (
                            self.jira_repository.get_issue_spent_time_in_seconds(
                                issue.key,
                            )
                        )
                        remaining_estimate = (
                            int((feature.total_hours * 3600 - time_logged) / 3600)
                            if feature.total_hours * 3600 - time_logged > 0
                            else 0
                        )
                        update_fields["timetracking"] = {
                            "originalEstimate": f"{feature.total_hours}h",
                            "remainingEstimate": f"{remaining_estimate}h",
                        }
            elif feature.total_hours and issue.fields.issuetype.name == "Story":
                LOGGER.debug(f"times must be updated in _update_assignees_and_subtasks")

            components = self._map_components(feature)
            current_components = [comp.name for comp in issue.fields.components]
            if set(current_components) != set(components):
                update_fields["components"] = [{"name": comp} for comp in components]

            if feature.involved_people and issue.fields.issuetype.name == "Task":
                LOGGER.debug(
                    "skip checks. issue of type task doesn't have label for assignees. Issue type must be changed to Story if more than one person is involved",
                )
                if len(feature_assignees) > 1:
                    update_fields["labels"] = [
                        feature.involved_people.replace(" ", "-"),
                    ]
            elif feature.involved_people and issue.fields.issuetype.name == "Story":
                all_assignees = list(
                    set(
                        [
                            subtask_issue.fields.assignee.name
                            for subtask in issue.fields.subtasks
                            if (subtask_issue := self.jira_repository.get_issue(subtask.key)) is not None
                            and subtask_issue.fields.assignee is not None
                        ],
                    ),
                )
                sheet_usernames = []
                label_index = None
                for assignee in all_assignees:
                    sheet_username = self.user_config.get_user_config_by_jira_username(
                        assignee,
                    ).google_sheet_name
                    sheet_usernames.append(sheet_username)
                    if label_index is None:
                        for i, label in enumerate(issue.fields.labels):
                            if sheet_username in label:
                                label_index = i
                                break
                if label_index is not None:
                    names = [
                        name.strip(" ")
                        for name in issue.fields.labels[label_index].split("---")
                    ]
                    if set(sheet_usernames) != set(names):
                        # Remove all individual assignee labels and the old combined label
                        existing_labels = set(issue.fields.labels)
                        # Remove all sheet usernames (individual labels) and the old combined label
                        for username in sheet_usernames:
                            existing_labels.discard(username.replace(" ", "-"))
                        if label_index < len(issue.fields.labels):
                            existing_labels.discard(issue.fields.labels[label_index])
                        
                        # Add only the new combined label
                        combined_label = "---".join(sorted([name.replace(" ", "-") for name in sheet_usernames]))
                        update_fields["labels"] = list(existing_labels) + [combined_label]

            else:
                LOGGER.warning(f"Invalid update. Not handled for {feature} and {issue}")

            if update_fields:
                issue.update(fields=update_fields)
                LOGGER.info(f"Updated task {feature.developer_board_issue_key} with {update_fields}")

            return True

        except Exception as e:
            LOGGER.error(
                f"Error updating task {feature.developer_board_issue_key} for {feature}, {issue}: {e}",
            )
            return False

    async def track_time_in_developer_board(
        self,
        developer_board_issue_key: str,
        time_spent: int,
        user: str,
    ) -> bool:
        """Track time spent on task and deduct from original story points.

        Args:
            developer_board_issue_key: issue key
            time_spent: Time spent in hours
            user: User who spent the time

        Returns:
            True if successful, False otherwise
        """
        try:
            developer_board_issue = self.jira_repository.get_issue(
                developer_board_issue_key,
            )
            if not developer_board_issue:
                LOGGER.error(f"issue {developer_board_issue_key} not found")
                return False

            # Find linked PM Board issue key from labels
            pm_board_issue_key = None
            for label in developer_board_issue.fields.labels:
                if label.startswith("PM-"):
                    pm_board_issue_key = label.replace("PM-", "")
                    break
                elif label.startswith("PM Board-"):
                    pm_board_issue_key = label.replace("PM Board-", "")
                    break

            if not pm_board_issue_key:
                LOGGER.error(
                    f"No linked PM Board issue found for {developer_board_issue_key}",
                )
                return False

            pm_board_issue = self.jira_repository.get_issue(pm_board_issue_key)
            if not pm_board_issue:
                LOGGER.error(f"Linked PM Board issue {pm_board_issue_key} not found")
                return False

            worklog = self.jira_repository.add_worklog(
                developer_board_issue_key,
                timeSpent=f"{time_spent}h",
                comment=f"Time tracked by {user}",
            )

            if worklog:
                current_story_points = (
                    getattr(
                        pm_board_issue.fields,
                        self.jira_repository.jira_original_estimate_id,
                        0,
                    )
                    or 0
                )
                new_story_points = max(0, current_story_points - time_spent)

                pm_board_issue.update(
                    fields={
                        self.jira_repository.jira_original_estimate_id: new_story_points,
                    },
                )

                LOGGER.info(
                    f"Tracked {time_spent}h for {user} on {developer_board_issue_key}, "
                    f"deducted from PM Board {pm_board_issue_key} story points: {current_story_points} -> {new_story_points}",
                )

                features = await self.get_developer_board_features()
                for feature in features:
                    if feature.jira_issue_key == pm_board_issue_key:
                        await self.update_developer_board_feature(
                            feature.row_number,
                            {"total_hours": new_story_points},
                        )
                        break

                return True

            return False

        except Exception as e:
            LOGGER.error(f"Error tracking time for {developer_board_issue_key}: {e}")
            return False

    async def get_sync_status(self) -> Optional[SynthPMSheetSyncStatus]:
        """Get the current sync status.

        Returns:
            Sync status entity or None if not found
        """
        try:
            if self.sync_status_file.exists():
                with open(self.sync_status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return SynthPMSheetSyncStatus(**data)
            return None

        except Exception as e:
            LOGGER.error(f"Error reading sync status: {e}")
            return None

    async def update_sync_status(self, status: SynthPMSheetSyncStatus) -> bool:
        """Update the sync status.

        Args:
            status: Sync status entity

        Returns:
            True if successful, False otherwise
        """
        try:
            self.sync_status_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.sync_status_file, "w", encoding="utf-8") as f:
                json.dump(status.dict(), f, ensure_ascii=False, indent=2, default=str)

            return True

        except Exception as e:
            LOGGER.error(f"Error updating sync status: {e}")
            return False

    def _create_column_mapping(self, headers: List[str]) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Create mapping from column names to indices.

        Args:
            headers: List of column headers from the sheet

        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}

        # Column name mappings - TODO: Make this configurable through database/settings
        column_name_mappings = {
            "row_number": ["ردیف", "Row", "ردیف"],
            "task_title": ["وظیفه", "Task", "وظیفه"],
            "epic": ["Epic", "Epic"],
            "necessity": ["ضرورت", "Necessity", "ضرورت"],
            "priority": ["اولویت", "Priority", "اولویت"],
            "status": ["وضعیت", "Status", "وضعیت"],
            "release": ["ریلیز", "Release", "ریلیز"],
            "eta_hours": ["ETA(h)", "ETA", "ETA(h)"],
            "total_hours": ["Total (h)", "Total", "Total (h)"],
            "departments": ["Departments", "Departments"],
            "involved_people": ["افراد درگیر", "Involved People", "افراد درگیر"],
            "ai": ["AI", "AI"],
            "backend": ["Backend", "Backend"],
            "frontend": ["Front-end", "Frontend", "Front-end"],
            "devops": ["DevOPS", "DevOps", "DevOPS"],
            "ui_ux": ["UI / UX", "UI/UX", "UI / UX"],
            "creation_date": ["تاریخ ایجاد", "Creation Date", "تاریخ ایجاد"],
            "implementation_start_date": [
            "تاریخ شروع پیاده سازی",
            "Implementation Start",
            "تاریخ شروع پیاده سازی",
            ],
            "deadline": ["ددلاین", "Deadline", "ددلاین"],
            "sprint": ["اسپرینت", "Sprint", "اسپرینت"],
            "dependencies": ["وابستگی ها", "Dependencies", "وابستگی ها"],
            "department_deps": ["Department Deps", "Department Dependencies", "وابستگی های دپارتمان"],
            "initial_delivery_time": [
            "زمان تحویل اولیه",
            "Initial Delivery",
            "زمان تحویل اولیه",
            ],
            "description": ["توضیحات", "Description", "توضیحات"],
            "acceptance_criteria": ["معیارهای پذیرش", "Acceptance Criteria", "معیارهای پذیرش"],
            "test_cases": ["تست ها", "Test Cases", "تست ها"],
            "po_notes": ["علل تغییر یا توقف", "PO Notes", "علل تغییر یا توقف"],
            "jira_issue_key": ["jira_issue_key", "Jira Issue Key", "jira_issue_key"],
            "developer_board_issue_key": ["developer_board_issue_key"],
            "version": ["version", "ریلیز اصلی"],
            
        }
        people_mapping = {}

        for user in self.user_config.list_all_users_google_sheet_names():
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

    def _parse_row_to_feature_with_mapping(
        self, 
        row_number: int,
        row: List[str],
        column_mapping: Dict[str, int],
        people_mapping: Dict[str, int]
    ) -> Optional[SynthPMFeatureEntity]:
        """Parse a row from Google Sheets to SynthPMFeatureEntity using column mapping.

        Args:
            row_number: Row number in the sheet
            row: Row data from Google Sheets
            column_mapping: Dictionary mapping field names to column indices

        Returns:
            SynthPMFeatureEntity or None if parsing fails
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
                    # Try different date formats
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                    return None
                except Exception:
                    return None

            def parse_float(value_str: str) -> Optional[float]:
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
                    return float(value_str)
                except (ValueError, TypeError):
                    return None

            task_title = get_mapped_value("task_title")
            if not task_title:
                return None

            # Handle multiple sprints for each task
            sprints = get_mapped_value("sprint")
            sprint_list = []
            last_sprint = None
            
            if sprints and sprints.strip() and sprints != "":
                # Parse comma-separated sprints like "1: Sprint 1, 2: Sprint 2"
                items = [p.strip() for p in sprints.split(",")]
                sprint_list = items
                
                if items:
                    # Find the latest sprint (highest number)
                    try:
                        max_item = max(items, key=lambda t: int(t.split(":", 1)[0]) if ":" in t else 0)
                        last_sprint = max_item
                    except (ValueError, IndexError):
                        # Fallback to last item if parsing fails
                        last_sprint = items[-1]
            times = {key: parse_float(get_mapped_value(key)) for key in people_mapping.keys() if parse_float(get_mapped_value(key)) is not None}
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
                    if get_mapped_value("release") not in ["Select", ""]
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
                eta_hours=parse_float(get_mapped_value("eta_hours")),
                total_hours=parse_float(get_mapped_value("total_hours")),
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
                times=times
            )

        except Exception as e:
            LOGGER.error(f"Error parsing row {row_number}: {e}")
            return None

    @staticmethod
    def _number_to_column_letter(col_num: int) -> str:
        """Convert column number to Excel column letter.

        Args:
            col_num: Column number (1-based)

        Returns:
            Excel column letter (e.g., 1 -> A, 26 -> Z, 27 -> AA)
        """
        result = ""
        while col_num > 0:
            col_num -= 1
            result = chr(col_num % 26 + ord("A")) + result
            col_num //= 26
        return result

    @staticmethod
    def _map_priority(priority: Optional[str]) -> str:
        """Map sheet priority to Jira priority.

        Args:
            priority: Priority from sheet

        Returns:
            Jira priority name
        """
        if not priority:
            return "Medium"

        priority_mapping = {
            "Highest": "Highest",
            "High": "High",
            "Medium": "Medium",
            "Low": "Low",
            "Lowest": "Lowest",
            "۱": "Highest",
            "۱. بالاترین": "Highest",
            "۲": "High",
            "۲. بالا": "High",
            "۳": "Medium",
            "۳. متوسط": "Medium",
            "۴": "Low",
            "۴. پایین": "Low",
            "۵": "Lowest",
            "۵. پایین ترین": "Lowest",
            "بالاترین": "Highest",
            "بالا": "High",
            "متوسط": "Medium",
            "پایین": "Low",
            "بحرانی": "Highest",
            "خیلی پایین": "Low",
        }

        return priority_mapping.get(priority, "Medium")

    def _map_components(self, feature: SynthPMFeatureEntity) -> List[str]:
        """Map feature department flags to Jira components.

        Args:
            feature: feature entity

        Returns:
            List of Jira component names
        """
        components = []

        # Prefer using departments field if available
        if feature.departments and feature.departments.strip():
            # Parse departments field (could be comma-separated)
            dept_list = [dept.strip() for dept in feature.departments.split(",")]
            for dept in dept_list:
                if dept.lower() in ["ai", "artificial intelligence"]:
                    components.append("AI")
                elif dept.lower() in ["backend", "back-end"]:
                    components.append("Backend")
                elif dept.lower() in ["frontend", "front-end", "فرانت"]:
                    components.append("Front-end")
                elif dept.lower() in ["devops", "dev-ops"]:
                    components.append("DevOps")
                elif dept.lower() in ["ui/ux", "ui", "ux", "design"]:
                    components.append("UI/UX")
        else:
            # Fallback to individual department fields
            if feature.ai != "" and float(feature.ai) > 0:
                components.append("AI")
            if feature.backend != "" and float(feature.backend) > 0:
                components.append("Backend")
            if feature.frontend != "" and float(feature.frontend) > 0:
                components.append("Front-end")
            if feature.devops != "" and float(feature.devops) > 0:
                components.append("DevOps")
            if feature.ui_ux != "" and float(feature.ui_ux) > 0:
                components.append("UI/UX")

        return components

    def _get_status_mapping(self) -> Dict[str, str]:
        """Get mapping of sheet status to Jira status.

        Returns:
            Dictionary mapping sheet status to Jira status
        """
        return {
            "۱. ثبت و اولویت بندی": "BACKLOG",
            "۲. تحلیل مسئله و RFP": "SELECTED FOR DEVELOPMENT",
            "۳. آماده سازی یوزر استوری": "TO DO",
            "۴. در مرحله طراحی": "IN REVIEW",
            "۵. آماده پیاده سازی فنی": "OPEN",
            "۶. در حال پیاده سازی": "IN PROGRESS",
            "۷. تست فنی": "REVIEW",
            "۸. آماده تحویل": "RESOLVED",
            "۹. مستندسازی فنی": "DONE",
            "۱۰. تکمیل شده": "CLOSED",
        }

    def _create_epic_if_not_exists(
        self,
        epic_name: str,
        board_name: str,
    ) -> Tuple[bool, Optional[str]]:
        """Create epic if it doesn't exist in Jira.

        Args:
            epic_name: Epic name to create
            board_name: Board/project key where epic should be created

        Returns:
            Tuple of (epic_exists, epic_key)
        """
        try:
            jql = f'project = "{board_name}" AND issuetype = Epic AND summary ~ "{epic_name}"'
            issues = self.jira_repository.search_issues(jql, max_results=1)
            if len(issues) == 0:
                # TODO: In the future, get epic description from an epic specification sheet
                epic_description = (
                    f"Epic for {epic_name}\n\n"
                    f"This epic was automatically created to group related tasks and stories."
                )
                
                task_data = TaskData(
                    project_key=board_name,
                    summary=epic_name,
                    description=epic_description,
                    task_type="Epic",
                )
                issue = self.jira_repository.create_task(task_data)
                issues = [issue]

            return len(issues) > 0, issues[0].key if issues else None
        except Exception as e:
            LOGGER.warning(f"Error validating epic '{epic_name}': {e}")
            return False, None

    def _get_sprint_id(self, sprint_name: str, board_id: int) -> Optional[int]:
        """Get sprint ID by name.

        Args:
            sprint_name: Sprint name

        Returns:
            Sprint ID if found, None otherwise
        """
        # TODO: for now, settings pm board sprint to "active"
        try:
            sprint_id = self.jira_repository.get_sprint_by_name(
                sprint_name,
                board_id,
            ).get("id")
            return sprint_id
        except Exception as e:
            LOGGER.warning(f"Error getting sprint ID for '{sprint_name}': {e}")
            return None

    def _determine_jira_status(self, feature: SynthPMFeatureEntity) -> str:
        """Determine the appropriate Jira status based on feature properties.

        Args:
            feature: feature entity

        Returns:
            Jira status name
        """
        components = self._map_components(feature)
        if (
            'UI/UX' in components and feature.status == STATUS_DESCRIPTIONS[SynthPMStatus.IN_IMPLEMENTATION.value]
        ):
            return "In Progress"

        # Map other statuses
        status_mapping = self._get_status_mapping()
        jira_status = status_mapping.get(feature.status, "To Do")

        if jira_status == "Selected for Development":
            return "To Do"

        return jira_status

    def _link_issues(self, pm_board_issue_key: str, developer_board_issue_key: str):
        """Link PM Board and Developer Board issues.

        Args:
            pm_board_issue_key: PM Board issue key
            developer_board_issue_key: Developer Board issue key
        """
        try:
            available_link_types = self.jira_repository.get_issue_link_types()

            preferred_types = ["Dependency", "Blocks", "Relates to", "Relates"]
            selected_link_type = "Relates"  # Default fallback

            for preferred in preferred_types:
                for link_type in available_link_types:
                    if link_type["name"].lower() == preferred.lower():
                        selected_link_type = preferred
                        break
                if selected_link_type == preferred:
                    break

            success = self.jira_repository.link_issues(
                dependent_issue_key=pm_board_issue_key,
                dependency_issue_key=developer_board_issue_key,
                link_type=selected_link_type,
            )

            if success:
                LOGGER.info(
                    f"Successfully linked issues: {pm_board_issue_key} -> {developer_board_issue_key} ({selected_link_type})",
                )
            else:
                LOGGER.warning(
                    f"Failed to link issues: {pm_board_issue_key} -> {developer_board_issue_key}",
                )
        except Exception as e:
            LOGGER.error(
                f"Error linking issues {pm_board_issue_key} and {developer_board_issue_key}: {e}",
            )

    def _transition_issue_to_status(self, issue_key: str, target_status: str):
        """Transition an issue to the target status.

        Args:
            issue_key: Jira issue key
            target_status: Target status name
        """
        try:
            transitions = self.jira_repository.get_transitions(issue_key)
            for transition in transitions:
                if transition["to"]["name"].lower() == target_status.lower():
                    self.jira_repository.transition_issue(issue_key, transition["id"])
                    LOGGER.info(f"Transitioned {issue_key} to {target_status}")
                    return

            LOGGER.warning(f"No transition found to {target_status} for {issue_key}")
        except Exception as e:
            LOGGER.error(f"Error transitioning {issue_key} to {target_status}: {e}")

    def get_reverse_status_mapping(self) -> Dict[str, str]:
        """Get mapping of Jira status to sheet status.

        Returns:
            Dictionary mapping Jira status to sheet status
        """
        key_values = self._get_status_mapping()
        return {value: key for key, value in key_values.items()}

    async def _create_subtasks_for_assignees(
        self,
        parent_issue_key: str,
        assignees: List[str],
        feature: SynthPMFeatureEntity,
        sprint_info: SprintInfo,
        dates: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Create subtasks for each assignee with dependency handling.

        Args:
            parent_issue_key: Parent story issue key
            assignees: List of assignee usernames
            feature: Feature entity containing task details
            sprint_info: Sprint information
            dates: Due dates for subtasks

        Returns:
            List of created subtask keys
        """
        if not assignees:
            return []

        project_key = self.settings.developer_board_project_key
        created_subtasks = {}

        # Parse department dependencies
        dept_deps_dict = DepartmentDependencyCalculator.parse_department_deps(
            feature.department_deps,
        )

        # Build department hours mapping from feature.times
        department_hours = {}
        component_to_dept = {}

        for assignee in assignees:
            component = self.user_config.get_user_component(
                assignee,
                self.settings.developer_board_project_key,
            )
            if component:
                dept_name = DepartmentDependencyCalculator.get_department_from_component(component)
                story_points = self._get_assignee_story_points(assignee, feature, component)
                if story_points and story_points > 0:
                    department_hours[dept_name] = story_points
                    component_to_dept[component] = dept_name

        # Get holidays for deadline calculation
        current_year = datetime.now().year
        try:
            from jira_telegram_bot.adapters.repositories.calendar.json_calendar_repository import JsonCalendarRepository
            calendar_repo = JsonCalendarRepository()
            holidays = await calendar_repo.get_holidays(current_year)
            holidays.update(await calendar_repo.get_holidays(current_year + 1))
        except Exception as e:
            LOGGER.warning(f"Could not load holidays: {e}, using empty set")
            holidays = set()

        # Calculate department deadlines considering dependencies
        department_deadlines = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature.deadline,
            dept_deps_dict,
            department_hours,
            holidays,
            feature.implementation_start_date,
        )

        # Create subtasks with calculated deadlines
        for assignee in assignees:
            try:
                component = self.user_config.get_user_component(
                    assignee,
                    self.settings.developer_board_project_key,
                )
                if not component:
                    LOGGER.warning(
                        f"No component found for user {assignee}, skipping component assignment",
                    )
                    continue

                story_points = self._get_assignee_story_points(
                    assignee,
                    feature,
                    component,
                )

                # Get reporter (component lead)
                reporter = self.get_component_lead(project_key, component)

                # Get department-specific deadlines
                dept_name = component_to_dept.get(component)
                dept_dates = department_deadlines.get(dept_name, {})

                # Use calculated dates if available, otherwise use parent dates
                subtask_due_date = dept_dates.get("end")
                subtask_target_start = dept_dates.get("start")
                subtask_target_end = dept_dates.get("end")

                # Fallback to parent dates if no calculation available
                if not subtask_due_date and dates:
                    subtask_due_date = dates.get("due_date")
                if not subtask_target_start and dates:
                    subtask_target_start = dates.get("target_start")
                if not subtask_target_end and dates:
                    subtask_target_end = dates.get("target_end")

                # Convert datetime to string format for Jira
                due_date_str = subtask_due_date.strftime("%Y-%m-%d") if subtask_due_date else None
                target_start_str = subtask_target_start.strftime("%Y-%m-%d") if subtask_target_start else None
                target_end_str = subtask_target_end.strftime("%Y-%m-%d") if subtask_target_end else None

                subtask_data = TaskData(
                    project_key=project_key,
                    summary=f"{feature.task_title}",
                    description=f"{feature.description or ''}",
                    task_type="Sub-task",
                    priority=self._map_priority(feature.priority),
                    components=[component] if component else None,
                    assignee=assignee,
                    parent_issue_key=parent_issue_key,
                    due_date=due_date_str,
                    target_start=target_start_str,
                    target_end=target_end_str,
                    story_points=story_points / 8 if story_points and story_points > 0 else None,
                    reporter=reporter,
                )

                subtask_issue = self.jira_repository.create_task(subtask_data)
                created_subtasks[component] = subtask_issue.key

                LOGGER.info(
                    f"Created subtask {subtask_issue.key} for assignee {assignee} in component {component} "
                    f"with dates: start={target_start_str}, end={target_end_str}",
                )

            except Exception as e:
                LOGGER.error(f"Error creating subtask for assignee {assignee}: {e}")
                continue

        # Create blocking relationships between subtasks
        await self._create_subtask_blocking_links(
            created_subtasks,
            dept_deps_dict,
            component_to_dept,
        )

        return list(created_subtasks.values())

    async def _create_subtask_blocking_links(
        self,
        created_subtasks: Dict[str, str],
        dept_deps_dict: Dict[str, List[str]],
        component_to_dept: Dict[str, str],
    ):
        """Create blocking links between subtasks based on department dependencies.

        Args:
            created_subtasks: Dict mapping component to subtask key
            dept_deps_dict: Dict mapping blocked department to list of blocking departments
            component_to_dept: Dict mapping component to department name
        """
        try:
            # Reverse the component_to_dept mapping
            dept_to_component = {v: k for k, v in component_to_dept.items()}

            for blocked_dept, blocking_depts in dept_deps_dict.items():
                blocked_component = dept_to_component.get(blocked_dept)
                if not blocked_component or blocked_component not in created_subtasks:
                    continue

                blocked_subtask_key = created_subtasks[blocked_component]

                for blocking_dept in blocking_depts:
                    blocking_component = dept_to_component.get(blocking_dept)
                    if not blocking_component or blocking_component not in created_subtasks:
                        continue

                    blocking_subtask_key = created_subtasks[blocking_component]

                    # Create "Blocks" link
                    success = self.jira_repository.link_issues(
                        dependent_issue_key=blocked_subtask_key,
                        dependency_issue_key=blocking_subtask_key,
                        link_type="Dependency",
                    )

                    if success:
                        LOGGER.info(
                            f"Created blocking link: {blocking_subtask_key} ({blocking_dept}) "
                            f"blocks {blocked_subtask_key} ({blocked_dept})",
                        )
                    else:
                        LOGGER.warning(
                            f"Failed to create blocking link between "
                            f"{blocking_subtask_key} and {blocked_subtask_key}",
                        )

        except Exception as e:
            LOGGER.error(f"Error creating subtask blocking links: {e}")

    def _create_release_notes_column_mapping(
        self,
        headers: List[str],
    ) -> Dict[str, int]:
        """Create column mapping for Release Notes sheet.

        Args:
            headers: List of column headers from the Release Notes sheet

        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}

        column_name_mappings = {
            "row_number": ["ردیف", "Row"],
            "release_version": ["ریلیز اصلی", "Release Version", "Version"],
            "release_components": ["اجزای ریلیز", "Release Components", "Components"],
            "person_hours": ["نفر ساعت", "Person Hours"],
            "involved_people": ["افراد درگیر", "Involved People"],
            "epic": ["Epic", "Epic"],
            "percent_complete": ["% Complete", "Percent Complete"],
            "status": ["وضعیت", "Status"],
            "rag": ["RAG", "RAG"],
            "description": ["شرح", "Description"],
            "goals": ["اهداف", "Goals"],
            "delivery_process": ["فرایند تحویل", "Delivery Process"],
            "test_process": ["فرایند تست", "Test Process"],
            "start_date": ["تاریخ شروع", "Start Date"],
            "alpha_plan": ["Alpha Plan", "Alpha Plan"],
            "alpha_delivery": ["Alpha Delivery", "Alpha Delivery"],
            "beta_plan": ["Beta Plan", "Beta Plan"],
            "beta_delivery": ["Beta Delivery", "Beta Delivery"],
            "freeze": ["Freeze", "Freeze"],
            "env_dev": ["Env Dev ✅", "Env Dev"],
            "env_staging": ["Env Staging ✅", "Env Staging"],
            "env_prod": ["Env Prod ✅", "Env Prod"],
            "total_issues": ["Total Issues", "Total Issues"],
            "done_issues": ["Done Issues", "Done Issues"],
            "blockers": ["Blockers", "Blockers"],
            "delay_days": ["Delay Days", "Delay Days"],
            "test_pass_rate": ["Test Pass Rate (0-1)", "Test Pass Rate"],
            "sev1_open": ["Sev1 Open", "Sev1 Open"],
            "sev2_open": ["Sev2 Open", "Sev2 Open"],
            "pipeline_green_rate": ["Pipeline Green Rate (0-1)", "Pipeline Green Rate"],
            "checklist_completion": ["Checklist Completion (0-1)", "Checklist Completion"],
            "readiness_score": ["Readiness Score (0-100)", "Readiness Score"],
            "notes_risks": ["Notes / Risks", "Notes", "Risks"],
            "telegram_message_id": ["Telegram Message ID", "Message ID"],
            "last_updated": ["Last Updated", "Updated"],
        }

        for idx, header in enumerate(headers):
            header_clean = header.strip()

            for field_name, possible_names in column_name_mappings.items():
                if header_clean in possible_names:
                    mapping[field_name] = idx
                    break

        return mapping

    def _parse_row_to_release_note(
        self,
        row_number: int,
        row: List[str],
        column_mapping: Dict[str, int],
    ) -> Optional[ReleaseNoteEntity]:
        """Parse a row from Release Notes sheet to ReleaseNoteEntity.

        Args:
            row_number: Row number in the sheet
            row: Row data from Google Sheets
            column_mapping: Dictionary mapping field names to column indices

        Returns:
            ReleaseNoteEntity or None if parsing fails
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

            release_version = get_mapped_value("release_version")
            release_components = get_mapped_value("release_components")
            description = get_mapped_value("description")

            if not release_version or not release_components or not description:
                return None

            return ReleaseNoteEntity(
                row_number=row_number,
                release_version=release_version,
                release_components=release_components,
                person_hours=get_mapped_value("person_hours") if get_mapped_value("person_hours") else None,
                involved_people=get_mapped_value("involved_people") if get_mapped_value("involved_people") else None,
                epic=get_mapped_value("epic") if get_mapped_value("epic") else None,
                percent_complete=get_mapped_value("percent_complete") if get_mapped_value("percent_complete") else None,
                status=get_mapped_value("status") if get_mapped_value("status") else None,
                rag=get_mapped_value("rag") if get_mapped_value("rag") else None,
                description=description,
                goals=get_mapped_value("goals") if get_mapped_value("goals") else None,
                delivery_process=get_mapped_value("delivery_process") if get_mapped_value("delivery_process") else None,
                test_process=get_mapped_value("test_process") if get_mapped_value("test_process") else None,
                start_date=get_mapped_value("start_date") if get_mapped_value("start_date") else None,
                alpha_plan=get_mapped_value("alpha_plan") if get_mapped_value("alpha_plan") else None,
                alpha_delivery=get_mapped_value("alpha_delivery") if get_mapped_value("alpha_delivery") else None,
                beta_plan=get_mapped_value("beta_plan") if get_mapped_value("beta_plan") else None,
                beta_delivery=get_mapped_value("beta_delivery") if get_mapped_value("beta_delivery") else None,
                freeze=get_mapped_value("freeze") if get_mapped_value("freeze") else None,
                env_dev=get_mapped_value("env_dev") if get_mapped_value("env_dev") else None,
                env_staging=get_mapped_value("env_staging") if get_mapped_value("env_staging") else None,
                env_prod=get_mapped_value("env_prod") if get_mapped_value("env_prod") else None,
                total_issues=get_mapped_value("total_issues") if get_mapped_value("total_issues") else None,
                done_issues=get_mapped_value("done_issues") if get_mapped_value("done_issues") else None,
                blockers=get_mapped_value("blockers") if get_mapped_value("blockers") else None,
                delay_days=get_mapped_value("delay_days") if get_mapped_value("delay_days") else None,
                test_pass_rate=get_mapped_value("test_pass_rate") if get_mapped_value("test_pass_rate") else None,
                sev1_open=get_mapped_value("sev1_open") if get_mapped_value("sev1_open") else None,
                sev2_open=get_mapped_value("sev2_open") if get_mapped_value("sev2_open") else None,
                pipeline_green_rate=get_mapped_value("pipeline_green_rate") if get_mapped_value("pipeline_green_rate") else None,
                checklist_completion=get_mapped_value("checklist_completion") if get_mapped_value("checklist_completion") else None,
                readiness_score=get_mapped_value("readiness_score") if get_mapped_value("readiness_score") else None,
                notes_risks=get_mapped_value("notes_risks") if get_mapped_value("notes_risks") else None,
                telegram_message_id=get_mapped_value("telegram_message_id") if get_mapped_value("telegram_message_id") else None,
                last_updated=parse_date(get_mapped_value("last_updated")),
            )

        except Exception as e:
            LOGGER.error(f"Error parsing release note row {row_number}: {e}")
            return None

    def _log_available_link_types(self):
        """Log available Jira issue link types for debugging."""
        try:
            link_types = self.jira_repository.get_issue_link_types()
            LOGGER.info(
                f"Available Jira link types: {[lt['name'] for lt in link_types]}",
            )
            for link_type in link_types:
                LOGGER.debug(
                    f"Link type: {link_type['name']} - "
                    f"Inward: {link_type.get('inward', 'N/A')}, "
                    f"Outward: {link_type.get('outward', 'N/A')}",
                )
        except Exception as e:
            LOGGER.error(f"Error getting link types for debugging: {e}")

    def _get_assignee_story_points(
        self,
        assignee: str,
        feature: SynthPMFeatureEntity,
        component: Optional[str],
    ) -> float | None:
        """Get story points allocation for a specific assignee.

        Args:
            assignee: Assignee username (Jira username)
            feature: Feature entity
            component: Component name (can be None)

        Returns:
            Story points allocation for the assignee in hours
        """
        try:
            sheet_username = self.user_config.get_user_config_by_jira_username(assignee).google_sheet_name
            story_points = feature.times.get(sheet_username)
            if story_points is not None:
                return story_points
            else:
                if component:
                    story_points = int(
                        feature.__getattribute__(
                            component.lower().strip("-").replace("-", "").replace("/","_"),
                        ),
                    )
                else:
                    story_points = None
            return story_points

        except Exception as e:
            LOGGER.error(
                f"Error calculating story points for {feature.task_title}: {e}",
            )
            return None

    async def _update_assignees_and_subtasks(
        self,
        issue_key: str,
        feature_assignees: List[str],
        feature: SynthPMFeatureEntity,
    ) -> bool:
        """Update issue assignees and manage subtasks accordingly.

        Args:
            issue_key: Jira issue key
            assignees: List of assignee usernames
            feature: Feature entity for subtask creation/updates

        Returns:
            True if successful, False otherwise
        """
        try:
            issue = self.jira_repository.get_issue(issue_key)
            if not issue:
                LOGGER.warning(f"Issue {issue_key} not found")
                return False

            # Get current assignees from issue and subtasks
            current_assignee = (
                issue.fields.assignee.name if issue.fields.assignee else None
            )
            current_assignees = set()
            if current_assignee:
                current_assignees.add(current_assignee)

            # Get subtasks and their assignees
            subtasks = issue.fields.subtasks
            subtask_assignees = {}
            for subtask in subtasks:
                subtask_issue = self.jira_repository.get_issue(subtask.key)
                if subtask_issue is not None:
                    assignee = subtask_issue.fields.assignee
                    assignee_name = assignee.name if assignee else None
                else:
                    LOGGER.warning(f"Subtask {subtask.key} not found, skipping assignee check")
                    assignee_name = None
                if assignee_name:
                    current_assignees.add(assignee_name)
                    if assignee_name not in subtask_assignees:
                        subtask_assignees[assignee_name] = [subtask]
                    else:
                        subtask_assignees[assignee_name].append(subtask)

            # If assignees haven't changed, update time estimates on existing subtasks
            feature_assignees = set(feature_assignees)
            if feature_assignees == current_assignees:
                await self._update_subtask_time_estimates_and_dependencies(
                    subtasks,
                    feature_assignees,
                    feature,
                )
                return True

            if len(feature_assignees) > 1:
                # Remove assignees that are no longer needed
                for old_assignee in current_assignees:
                    if (
                        old_assignee not in feature_assignees
                        and old_assignee in subtask_assignees
                    ):
                        subtask = subtask_assignees[old_assignee]
                        if isinstance(subtask, list):
                            for sub in subtask:
                                self.jira_repository.delete_issue(sub.key)
                                LOGGER.info(
                                    f"Deleted subtask {sub.key} for removed assignee {old_assignee}",
                                )
                        else:
                            self.jira_repository.delete_issue(subtask.key)
                            LOGGER.info(
                                f"Deleted subtask {subtask.key} for removed assignee {old_assignee}",
                            )

                # Create or update subtasks for assignees
                feature_dates_str = self.extract_dates_from_feature_in_str(feature)
                for assignee in feature_assignees:
                    if assignee not in subtask_assignees:
                        # Create new subtask
                        await self._create_subtask_for_assignee(
                            issue_key,
                            assignee,
                            feature,
                            dates=feature_dates_str,
                        )
                    else:
                        # Update existing subtask time estimate
                        subtask = subtask_assignees[assignee]
                        if isinstance(subtask, list):
                            for tak in subtask:
                                await self._update_subtask_time_estimate_and_dates(
                                    tak,
                                    assignee,
                                    feature,
                                )
                        else:
                            await self._update_subtask_time_estimate_and_dates(
                                subtask,
                                assignee,
                                feature,
                            )

            return True

        except Exception as e:
            LOGGER.error(f"Error updating assignees and subtasks for {issue_key}: {e}")
            return False

    async def _create_subtask_for_assignee(
        self,
        parent_issue_key: str,
        assignee: str,
        feature: SynthPMFeatureEntity,
        dates: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Create a subtask for a specific assignee.

        Args:
            parent_issue_key: Parent issue key
            assignee: Assignee username
            feature: Feature entity
            dates: Optional dates dictionary with due_date, target_start, target_end

        Returns:
            Created subtask key if successful, None otherwise
        """
        try:
            component = self.user_config.get_user_component(
                assignee,
                self.settings.developer_board_project_key,
            )
            if not component:
                LOGGER.warning(
                    f"No component found for user {assignee}, skipping component assignment",
                )

            # Get time allocation for this assignee
            story_points = self._get_assignee_story_points(assignee, feature, component)
            
            # Use provided dates or extract from feature
            if dates is None:
                dates = self.extract_dates_from_feature_in_str(feature)

            # Build releases list from feature
            releases = [r for r in [feature.release, feature.version] if r]
            
            subtask_data = TaskData(
                project_key=self.settings.developer_board_project_key,
                summary=f"{feature.task_title}",
                description=f"{feature.description or ''}",
                task_type="Sub-task",
                priority=self._map_priority(feature.priority),
                components=[component] if component else None,
                assignee=assignee,
                parent_issue_key=parent_issue_key,
                due_date=dates.get("due_date"),
                story_points=story_points / 8 if story_points and story_points > 0 else None,
                target_start=dates.get("target_start"),
                target_end=dates.get("target_end"),
                releases=releases if releases else None,
            )

            subtask_issue = self.jira_repository.create_task(subtask_data)
            if subtask_issue:
                LOGGER.info(
                    f"Created subtask {subtask_issue.key} for assignee {assignee}",
                )
                return subtask_issue.key

            return None

        except Exception as e:
            LOGGER.error(f"Error creating subtask for assignee {assignee}: {e}")
            return None

    async def _update_subtask_time_estimates_and_dependencies(
        self,
        subtasks: List,
        feature_assignees: List[str],
        feature: SynthPMFeatureEntity,
    ):
        """Update time estimates and dependencies for all subtasks.

        Args:
            subtasks: List of subtask objects
            feature_assignees: List[str]: Feature assignees
            feature: SynthPMFeatureEntity
        """
        # Fetch all subtask issues in one batch to reduce API calls
        subtask_issues = {}
        subtask_components = {}
        
        for subtask in subtasks:
            try:
                issue = self.jira_repository.get_issue(subtask.key)
                subtask_issues[subtask.key] = issue
                if issue and issue.fields.components:
                    subtask_components[subtask.key] = issue.fields.components[0].name
            except Exception as e:
                LOGGER.warning(f"Could not fetch subtask {subtask.key}: {e}")

        # Parse department dependencies
        dept_deps_dict = DepartmentDependencyCalculator.parse_department_deps(
            feature.department_deps,
        )

        # Build department hours mapping
        department_hours = {}
        component_to_dept = {}
        
        for subtask_key, component in subtask_components.items():
            dept_name = DepartmentDependencyCalculator.get_department_from_component(component)
            issue = subtask_issues.get(subtask_key)
            if issue and issue.fields.assignee:
                assignee = issue.fields.assignee.name
                story_points = self._get_assignee_story_points(assignee, feature, component)
                if story_points and story_points > 0:
                    department_hours[dept_name] = story_points
                    component_to_dept[component] = dept_name

        # Get holidays for deadline calculation
        current_year = datetime.now().year
        try:
            from jira_telegram_bot.adapters.repositories.calendar.json_calendar_repository import JsonCalendarRepository
            calendar_repo = JsonCalendarRepository()
            holidays = await calendar_repo.get_holidays(current_year)
            holidays.update(await calendar_repo.get_holidays(current_year + 1))
        except Exception as e:
            LOGGER.warning(f"Could not load holidays: {e}, using empty set")
            holidays = set()

        # Calculate department deadlines
        department_deadlines = DepartmentDependencyCalculator.calculate_department_deadlines(
            feature.deadline,
            dept_deps_dict,
            department_hours,
            holidays,
            feature.implementation_start_date,
        )

        # Build mapping of subtask keys by component
        subtask_by_component = {}
        for subtask_key, component in subtask_components.items():
            subtask_by_component[component] = subtask_key

        # Update each subtask with calculated deadlines
        for subtask in subtasks:
            issue = subtask_issues.get(subtask.key)
            if not issue:
                continue
                
            subtask_assignee = issue.fields.assignee.name if issue.fields.assignee else None
            if subtask_assignee in feature_assignees:
                component = subtask_components.get(subtask.key)
                dept_name = component_to_dept.get(component) if component else None
                dept_dates = department_deadlines.get(dept_name, {}) if dept_name else {}
                
                await self._update_subtask_time_estimate_and_dates(
                    subtask,
                    subtask_assignee,
                    feature,
                    subtask_issue=issue,
                    department_dates=dept_dates,
                )

        # Update blocking relationships
        await self._update_subtask_blocking_links(
            subtask_by_component,
            dept_deps_dict,
            component_to_dept,
        )

    async def _update_subtask_blocking_links(
        self,
        subtask_by_component: Dict[str, str],
        dept_deps_dict: Dict[str, List[str]],
        component_to_dept: Dict[str, str],
    ):
        """Update blocking links between subtasks based on department dependencies.

        Args:
            subtask_by_component: Dict mapping component to subtask key
            dept_deps_dict: Dict mapping blocked department to list of blocking departments
            component_to_dept: Dict mapping component to department name
        """
        try:
            # Reverse the component_to_dept mapping
            dept_to_component = {v: k for k, v in component_to_dept.items()}

            # Get existing links for all subtasks
            existing_links = {}
            for component, subtask_key in subtask_by_component.items():
                try:
                    issue = self.jira_repository.get_issue_with_expand(subtask_key, "issuelinks")
                    if issue and hasattr(issue.fields, 'issuelinks'):
                        existing_links[subtask_key] = issue.fields.issuelinks
                    else:
                        existing_links[subtask_key] = []
                except Exception as e:
                    LOGGER.warning(f"Could not fetch links for {subtask_key}: {e}")
                    existing_links[subtask_key] = []

            # Process dependencies
            for blocked_dept, blocking_depts in dept_deps_dict.items():
                blocked_component = dept_to_component.get(blocked_dept)
                if not blocked_component or blocked_component not in subtask_by_component:
                    continue

                blocked_subtask_key = subtask_by_component[blocked_component]

                for blocking_dept in blocking_depts:
                    blocking_component = dept_to_component.get(blocking_dept)
                    if not blocking_component or blocking_component not in subtask_by_component:
                        continue

                    blocking_subtask_key = subtask_by_component[blocking_component]

                    # Check if link already exists
                    link_exists = False
                    for link in existing_links.get(blocked_subtask_key, []):
                        if hasattr(link, 'inwardIssue') and link.inwardIssue.key == blocking_subtask_key:
                            link_exists = True
                            break
                        if hasattr(link, 'outwardIssue') and link.outwardIssue.key == blocking_subtask_key:
                            link_exists = True
                            break

                    if not link_exists:
                        # Create new link
                        success = self.jira_repository.link_issues(
                            dependent_issue_key=blocked_subtask_key,
                            dependency_issue_key=blocking_subtask_key,
                            link_type="Dependency",
                        )

                        if success:
                            LOGGER.info(
                                f"Created blocking link: {blocking_subtask_key} ({blocking_dept}) "
                                f"blocks {blocked_subtask_key} ({blocked_dept})",
                            )
                        else:
                            LOGGER.warning(
                                f"Failed to create blocking link between "
                                f"{blocking_subtask_key} and {blocked_subtask_key}",
                            )

        except Exception as e:
            LOGGER.error(f"Error updating subtask blocking links: {e}")

    async def _update_subtask_time_estimate_and_dates(
        self,
        subtask,
        assignee: str,
        feature: SynthPMFeatureEntity,
        subtask_issue=None,
        department_dates: Optional[Dict[str, datetime]] = None,
    ):
        """Update time estimate and dates for a specific subtask.

        Args:
            subtask: Subtask object
            assignee: Assignee username
            feature: Feature entity
            subtask_issue: Optional already-fetched issue object to avoid redundant API calls
            department_dates: Optional dict with "start" and "end" datetime objects
        """
        try:
            component = self.user_config.get_user_component(
                assignee,
                self.settings.developer_board_project_key,
            )

            story_point_hour = self._get_assignee_story_points(
                assignee,
                feature,
                component,
            )
            
            issue = subtask_issue or self.jira_repository.get_issue(subtask.key)
            
            issue_time = issue.fields.timetracking
            current_story_points = (
                getattr(
                    issue_time,
                    "originalEstimateSeconds",
                    0,
                )
                / 3600
            )
            
            # Use department-specific dates if available, otherwise use feature dates
            if department_dates:
                due_date_str = department_dates.get("end").strftime("%Y-%m-%d") if department_dates.get("end") else None
                target_start_str = department_dates.get("start").strftime("%Y-%m-%d") if department_dates.get("start") else None
                target_end_str = department_dates.get("end").strftime("%Y-%m-%d") if department_dates.get("end") else None
            else:
                feature_dates_str = self.extract_dates_from_feature_in_str(feature)
                due_date_str = feature_dates_str.get("due_date")
                target_start_str = feature_dates_str.get("target_start")
                target_end_str = feature_dates_str.get("target_end")
            
            update_fields = {}
            
            # Update dates (handle both setting and clearing)
            if issue.fields.duedate != due_date_str:
                update_fields["duedate"] = due_date_str
            
            current_target_start = issue.fields.__dict__.get(self.jira_repository.jira_target_start_id)
            if current_target_start != target_start_str:
                update_fields[self.jira_repository.jira_target_start_id] = target_start_str
            
            current_target_end = issue.fields.__dict__.get(self.jira_repository.jira_target_end_id)
            if current_target_end != target_end_str:
                update_fields[self.jira_repository.jira_target_end_id] = target_end_str
            
            # Update fixVersions (handle both setting and clearing)
            feature_versions = set([v for v in [feature.release, feature.version] if v])
            current_versions = set([field.name for field in issue.fields.fixVersions])
            if feature_versions != current_versions:
                if feature_versions:  # Only create releases if we're setting versions
                    self._create_release_not_exist_during_update(
                        feature,
                        self.settings.developer_board_project_key,
                    )
                update_fields["fixVersions"] = [
                    {"name": release}
                    for release in [feature.release, feature.version]
                    if release
                ] if feature_versions else []

            if (
                abs(current_story_points - story_point_hour) > 0.01
            ):  # Avoid floating point precision issues
                logged_time = int(
                    self.jira_repository.get_issue_spent_time_in_seconds(subtask.key)
                    / 3600,
                )
                remaining_estimate = (
                    story_point_hour - logged_time
                    if logged_time < story_point_hour
                    else 0
                )
                
                # Add time tracking to existing update_fields (don't overwrite dates)
                update_fields["timetracking"] = {
                    "originalEstimate": f"{story_point_hour}h",
                    "remainingEstimate": f"{remaining_estimate}h",
                }

                LOGGER.info(
                    f"Updated time estimate and dates for subtask {subtask.key}: {story_point_hour}h",
                )

            if update_fields:
                subtask.update(fields=update_fields)
                LOGGER.debug(f"Updated fields for subtask {subtask.key}: {update_fields}")

        except Exception as e:
            LOGGER.error(f"Error updating time estimate for subtask {subtask}: {e}")

    async def get_project_info(self, project_key: str) -> Dict[str, any]:
        """Get project information from projects_info.json.

        Args:
            project_key: Project key to get info for

        Returns:
            Project information dictionary
        """
        try:
            projects_info_path = Path(f"{DEFAULT_PATH}/jira_telegram_bot/settings/projects_info.json")
            
            if not projects_info_path.exists():
                LOGGER.warning(f"projects_info.json not found at {projects_info_path}")
                return {}

            with open(projects_info_path, "r", encoding="utf-8") as f:
                projects_data = json.load(f)

            return projects_data.get(project_key, {}).get("project_info", {})

        except Exception as e:
            LOGGER.error(f"Error loading project info for {project_key}: {e}")
            return {}

    def get_component_lead(self, project_key: str, component_name: str) -> Optional[str]:
        """Get the lead username for a component from projects_info.json.

        Args:
            project_key: Project key
            component_name: Component name

        Returns:
            Lead username or None
        """
        try:
            projects_info_path = Path(f"{DEFAULT_PATH}/jira_telegram_bot/settings/projects_info.json")
            
            if not projects_info_path.exists():
                return None

            with open(projects_info_path, "r", encoding="utf-8") as f:
                projects_data = json.load(f)

            project_data = projects_data.get(project_key, {})
            components = project_data.get("components", [])

            for component in components:
                if component.get("name") == component_name:
                    return component.get("lead")

            return None

        except Exception as e:
            LOGGER.error(f"Error getting component lead for {component_name}: {e}")
            return None

    async def update_jira_task_description(
        self,
        issue_key: str,
        description: str,
    ) -> bool:
        """Update Jira task description with generated documentation.

        Args:
            issue_key: Jira issue key
            description: New description content

        Returns:
            True if successful, False otherwise
        """
        try:
            issue = self.jira_repository.get_issue(issue_key)
            if not issue:
                LOGGER.error(f"Issue {issue_key} not found")
                return False

            # Update the description field
            issue.update(fields={"description": description})
            
            LOGGER.info(f"Updated description for issue {issue_key}")
            return True

        except Exception as e:
            LOGGER.error(f"Error updating description for {issue_key}: {e}")
            return False

    async def update_jira_task_custom_fields(
        self,
        issue_key: str,
        custom_fields: Dict[str, str],
    ) -> bool:
        """Update Jira task with custom fields for documentation.

        Args:
            issue_key: Jira issue key
            custom_fields: Dictionary of custom field values

        Returns:
            True if successful, False otherwise
        """
        try:
            issue = self.jira_repository.get_issue(issue_key)
            if not issue:
                LOGGER.error(f"Issue {issue_key} not found")
                return False

            # For now, append to description since custom fields depend on Jira configuration
            current_description = issue.fields.description or ""
            
            # Add sections to description
            new_description_parts = [current_description]
            
            if custom_fields.get("user_story"):
                new_description_parts.extend([
                    "",
                    "## یوزر استوری",
                    custom_fields["user_story"],
                ])
            
            if custom_fields.get("acceptance_criteria"):
                new_description_parts.extend([
                    "",
                    "## معیارهای پذیرش",
                    custom_fields["acceptance_criteria"],
                ])
            
            if custom_fields.get("test_scenarios"):
                new_description_parts.extend([
                    "",
                    "## سناریوهای تست",
                    custom_fields["test_scenarios"],
                ])

            new_description = "\n".join(new_description_parts)
            issue.update(fields={"description": new_description})
            
            LOGGER.info(f"Updated custom fields for issue {issue_key}")
            return True

        except Exception as e:
            LOGGER.error(f"Error updating custom fields for {issue_key}: {e}")
            return False

    async def update_jira_release(
        self,
        project_key: str,
        release_name: str,
        description: str,
    ) -> bool:
        """Update Jira release description with enhanced content.

        Args:
            project_key: Jira project key
            release_name: Name of the release to update
            description: New description content

        Returns:
            True if successful, False otherwise
        """
        try:
            success = self.jira_repository.update_release(
                project_key=project_key,
                release_name=release_name,
                description=description,
            )
            
            if success:
                LOGGER.info(f"Successfully updated Jira release '{release_name}' in project {project_key}")
            else:
                LOGGER.error(f"Failed to update Jira release '{release_name}' in project {project_key}")
            
            return success

        except Exception as e:
            LOGGER.error(f"Error updating Jira release '{release_name}' in project {project_key}: {e}")
            return False

    async def get_change_tracker(self) -> SynthPMChangeTracker:
        """Get the current change tracker state.

        Returns:
            SynthPMChangeTracker instance
        """
        try:
            if not self.change_tracker_file.exists():
                LOGGER.info("Change tracker file not found, creating new tracker")
                return SynthPMChangeTracker()

            with open(self.change_tracker_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            return SynthPMChangeTracker.model_validate(data)

        except Exception as e:
            LOGGER.error(f"Error loading change tracker: {e}")
            return SynthPMChangeTracker()

    async def save_change_tracker(self, tracker: SynthPMChangeTracker) -> bool:
        """Save the change tracker state.

        Args:
            tracker: SynthPMChangeTracker instance to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            self.change_tracker_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dict and handle datetime serialization
            data = tracker.model_dump(mode="json")

            with open(self.change_tracker_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            LOGGER.info(f"Change tracker saved with {len(tracker.snapshots)} snapshots")
            return True

        except Exception as e:
            LOGGER.error(f"Error saving change tracker: {e}")
            return False

    async def detect_feature_changes(
        self,
        current_features: List[SynthPMFeatureEntity],
    ) -> Dict[str, List[SynthPMFeatureEntity]]:
        """Detect what features have changed since last sync.

        Args:
            current_features: Current list of features from Google Sheets

        Returns:
            Dictionary categorizing features by change type
        """
        try:
            tracker = await self.get_change_tracker()
            changes = tracker.detect_changes(current_features)

            LOGGER.info(
                f"Change detection: {len(changes['new'])} new, "
                f"{len(changes['modified'])} modified, "
                f"{len(changes['unchanged'])} unchanged, "
                f"{len(changes['needs_docs'])} need docs"
            )
            
            # Debug logging for modified features
            if changes['modified']:
                LOGGER.info("Modified features detected:")
                for feature in changes['modified']:
                    old_snapshot = tracker.snapshots.get(feature.sheet_row_number)
                    new_snapshot = FeatureSnapshot.from_feature(feature)
                    LOGGER.info(f"  Row {feature.sheet_row_number}: {feature.task_title}")
                    LOGGER.info(f"    Old hash: {old_snapshot.content_hash if old_snapshot else 'None'}")
                    LOGGER.info(f"    New hash: {new_snapshot.content_hash}")
                    LOGGER.info(f"    Description: '{feature.description}'")

            return changes

        except Exception as e:
            LOGGER.error(f"Error detecting changes: {e}")
            # Fallback: treat all as needing docs
            return {
                "new": current_features,
                "modified": [],
                "unchanged": [],
                "needs_docs": current_features,
            }

    async def update_change_tracker(
        self,
        processed_features: List[SynthPMFeatureEntity],
        generated_docs_for: Optional[List[int]] = None,
    ) -> bool:
        """Update change tracker after processing features.

        Args:
            processed_features: List of processed features
            generated_docs_for: List of sheet_row_numbers that got documentation generated

        Returns:
            True if successful, False otherwise
        """
        try:
            tracker = await self.get_change_tracker()
            tracker.update_snapshots(processed_features, generated_docs_for)
            return await self.save_change_tracker(tracker)

        except Exception as e:
            LOGGER.error(f"Error updating change tracker: {e}")
            return False

    async def force_documentation_regeneration(self, sheet_row_numbers: List[int]) -> bool:
        """Force documentation regeneration for specific features.

        Args:
            sheet_row_numbers: List of row numbers to force regeneration for

        Returns:
            True if successful, False otherwise
        """
        try:
            tracker = await self.get_change_tracker()
            tracker.force_documentation_regeneration(sheet_row_numbers)
            return await self.save_change_tracker(tracker)

        except Exception as e:
            LOGGER.error(f"Error forcing documentation regeneration: {e}")
            return False

    async def update_google_sheet_custom_fields(self,
        issue_key: str,
        custom_fields: Dict[str, Any]
        ):
        pass