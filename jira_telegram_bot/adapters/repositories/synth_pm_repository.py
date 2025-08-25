"""Repository implementation for SynthPM operations."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import jdatetime

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.release_notes import SprintInfo
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMSheetSyncStatus
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
            values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                f"{self.settings.developer_board_worksheet_name}!A:AP",
            )

            if not values or len(values) < 2:
                LOGGER.warning("No data found in Features sheet")
                return []

            headers = values[0]
            column_mapping = self._create_column_mapping(headers)

            data_rows = values[1:]
            features = []

            for idx, row in enumerate(data_rows, start=2):
                if len(row) < 2:
                    continue

                feature = self._parse_row_to_feature_with_mapping(
                    idx,
                    row,
                    column_mapping,
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
            column_mapping = self._create_column_mapping(headers)

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
        try:
            due_date = None
            if feature.deadline:
                if isinstance(feature.deadline, str):
                    due_date = feature.deadline
                else:
                    due_date = feature.deadline.strftime("%Y-%m-%d")

            epic_link = None
            if feature.epic and feature.epic.strip() and feature.epic != "Select":
                _, epic_key = self._create_epic_not_exist(
                    feature.epic,
                    self.settings.pm_project_key,
                )
                epic_link = epic_key

            jira_status = self._determine_jira_status(feature)

            components = self._map_components(
                feature,
            )  # FIXME: get component from column department instead
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
                due_date=due_date,
            )

            if feature.sprint:
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
                self._transition_issue_to_status(issue.key, jira_status)

            if feature.involved_people and issue.fields.issuetype.name == "Task":
                developer_issue = self.jira_repository.get_issue(
                    feature.developer_board_issue_key,
                )
                developer_assignee = (
                    developer_issue.fields.assignee.name if developer_issue else None
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
                                    - {sheet_username}
                                    + {feature.involved_people.replace(" ", "-")},
                                )
                                break
            elif feature.involved_people and issue.fields.issuetype.name == "Story":
                developer_issue = self.jira_repository.get_issue(
                    feature.developer_board_issue_key,
                )
                if developer_issue:
                    developer_assignee = [developer_issue.fields.assignee.name]
                    subtasks_assignees = [
                        subtask.fields.assignee.name
                        for subtask in developer_issue.fields.subtasks
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
                                    set(issue.fields.labels) - {sheet_username},
                                ) + [feature.involved_people.replace(" ", "-")]

            else:
                LOGGER.error(f"Invalid update. Not handled for {feature} and {issue}")
                raise ValueError("Invalid issue type")

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
                f"{self.settings.release_notes_worksheet_name}!A:H",
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
        sprint_info: SprintInfo,
        assignees: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Create a Jira task from a feature with sprint.

        Args:
            feature: feature entity
            sprint_info: Sprint information for board
            assignees: List of assignee usernames for the task

        Returns:
            Jira issue key if successful, None otherwise
        """
        # TODO: If task has two sprints, handle it.
        # TODO: If the issue is only updated in the google sheet board (i.e its times and stuff, handle it)
        try:
            if not feature.jira_issue_key:
                LOGGER.error("Cannot create task without existing PM Board task")
                return None

            due_date = None
            if feature.deadline:
                if isinstance(feature.deadline, str):
                    due_date = feature.deadline
                else:
                    due_date = feature.deadline.strftime("%Y-%m-%d")

            epic_link = None
            if feature.epic and feature.epic.strip() and feature.epic != "Select":
                _, epic_key = self._create_epic_not_exist(
                    feature.epic,
                    self.settings.developer_board_project_key,
                )
                epic_link = epic_key

            components = self._map_components(feature)

            main_assignee = assignees[0] if assignees else None

            # TODO: set the year dynamically
            sprint = self.jira_repository.get_sprint_by_id(
                sprint_info.sprint_id,
                self.developer_board_id,
            )

            if sprint is None:
                start_date = sprint_info.start_date
                end_date = sprint_info.end_date
                start_date = jdatetime.JalaliToGregorian(
                    1404,
                    int(start_date.split("-")[0]),
                    int(start_date.split("-")[1]),
                )
                end_date = jdatetime.JalaliToGregorian(
                    1404,
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
                    board_id=self.developer_board_id,
                    sprint_name=f"{self.settings.developer_board_project_key} Sprint {sprint_info.sprint_id}",
                    start_date=start_date_str,
                    end_date=end_date_str,
                    goal=f"{sprint_info.start_date} to {sprint_info.end_date}",
                )

            task_type = "Story" if len(assignees) > 1 else "Task"
            if task_type == "Task":
                labels = None
                description = feature.description
                story_points = feature.total_hours / 8 if feature.total_hours else 0
            else:
                labels = [f"PM-{feature.jira_issue_key}", feature.involved_people]
                description = (
                    f"🔗 *Linked to PM Board*: {self.jira_repository.get_issue_url_by_key(feature.jira_issue_key)}\n\n"
                    f"👥 *Assignees*: {', '.join(assignees) if assignees else 'Unassigned'}\n\n"
                    f"📝 *Original Time*: {feature.total_hours}h\n\n"
                    f"✍️ *Description*: {feature.description}"
                )
                story_points = None

            developer_board_task_data = TaskData(
                project_key=self.settings.developer_board_project_key,
                summary=f"{feature.task_title}",
                description=description,
                task_type=task_type,
                priority=self._map_priority(feature.priority),
                epic_link=epic_link,
                labels=labels,
                components=components,
                assignee=main_assignee,
                due_date=due_date,
                story_points=story_points,
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
                        due_date,
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
        # TODO: if issue assignees are updated, assigneess of sub-tasks must be handled or reassigned.
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

            if feature.task_title:
                if feature.task_title != issue.fields.summary:
                    update_fields["summary"] = feature.task_title

            if feature.release != None or feature.version != None:
                if set([feature.release, feature.version]) != set(
                    issue.fields.fixVersions,
                ):  # Replace with actual custom field ID
                    self._create_release_not_exist_during_update(
                        feature,
                        self.settings.developer_board_project_key,
                    )
                    update_fields["fixVersions"] = [
                        {"name": release}
                        for release in [feature.release, feature.version]
                        if release
                    ]

            if feature_assignees and len(feature_assignees) > 1 and feature.description:
                current_desc = issue.fields.description or ""
                preserved_lines = []

                lines = current_desc.split("\n")
                for line in lines:
                    if any(
                        keyword in line
                        for keyword in [
                            "🔗 **Linked to PM Board**:",
                            "📅 **Sprint**:",
                            "👥 **Assignees**:",
                            "📝 **Original ETA**:",
                        ]
                    ):
                        preserved_lines.append(line)
                    elif line.strip() == "":
                        preserved_lines.append(line)
                        if len(preserved_lines) > 5:
                            break

                preserved_lines = [
                    line for line in preserved_lines if "👥 **Assignees**:" not in line
                ]
                preserved_lines.insert(
                    -1,
                    f"👥 **Assignees**: {', '.join(feature_assignees)}",
                )

                update_fields["description"] = (
                    "\n".join(preserved_lines) + f"\n{feature.description}"
                )

            if feature.priority:
                feature_priority = self._map_priority(feature.priority)
                if feature_priority != issue.fields.priority.name:
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
            if check_for_task_assignee_change:
                if feature_assignees[0] != issue.fields.assignee.name:
                    update_fields["assignee"] = {
                        "name": feature_assignees[0],
                    }
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
                # TODO: previously assigned users must be removed + previously assigneed tasks

                update_fields["labels"] = [
                    {
                        "name": list(
                            set(issue.fields.labels + [feature.involved_people]),
                        ),
                    },
                ]
            elif check_for_change_from_task_to_story:
                # TODO: change task type to Story, and assignee to users
                update_fields["issuetype"] = {"name": "Story"}
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
                            self.jira_repository.get_issue(
                                subtask.key,
                            ).fields.assignee.name
                            for subtask in issue.fields.subtasks
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
                        update_fields["labels"] = list(
                            set(issue.fields.labels) - {sheet_username},
                        ) + [name.replace(" ", "-") for name in names]

            else:
                LOGGER.error(f"Invalid update. Not handled for {feature} and {issue}")
                raise ValueError("Invalid issue type")

            if update_fields:
                issue.update(fields=update_fields)
                LOGGER.info(f"Updated task {feature.developer_board_issue_key}")

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

            pm_board_issue_key = None
            for label in developer_board_issue.fields.labels:
                # FIXME
                if label.startswith("PM Board-"):
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

    @staticmethod
    def _create_column_mapping(headers: List[str]) -> Dict[str, int]:
        """Create mapping from column names to indices.

        Args:
            headers: List of column headers from the sheet

        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}

        # FIXME: read these columns from database
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
            "initial_delivery_time": [
                "زمان تحویل اولیه",
                "Initial Delivery",
                "زمان تحویل اولیه",
            ],
            "description": ["توضیحات", "Description", "توضیحات"],
            "kazemi": ["کاظمی", "Kazemi"],
            "mousavi": ["موسوی", "Mousavi"],
            "moradi": ["مرادی", "Moradi"],
            "janloo": ["جانلو", "Janloo"],
            "hosseini": ["حسینی", "Hosseini"],
            "ghamari": ["قمری", "Ghamari"],
            "zangane": ["زنگنه", "Zanganeh"],
            "samei": ["سامعی", "Samei"],
            "oruji": ["اروجی", "Oruji"],
            "lotfian": ["لطفیان", "Lotfian"],
            "adabi": ["آدابی", "Adabi"],
            "dadjo": ["دادجو", "Dadjo"],
            "sadraei": ["صدرایی", "Sadraei"],
            "emam_dadi": ["امام دادی", "Emam Dadi"],
            "nasim": ["نسیم", "Nasim"],
            "dr_heravi": ["دکتر هروی", "Dr Heravi"],
            "jira_issue_key": ["jira_issue_key", "Jira Issue Key", "jira_issue_key"],
            "developer_board_issue_key": ["developer_board_issue_key"],
            "version": ["version", "ریلیز اصلی"],
        }

        for idx, header in enumerate(headers):
            header_clean = header.strip()

            for field_name, possible_names in column_name_mappings.items():
                if header_clean in possible_names:
                    mapping[field_name] = idx
                    break

        LOGGER.info(f"Created column mapping with {len(mapping)} fields")
        LOGGER.debug(f"Column mapping: {mapping}")

        return mapping

    @staticmethod
    def _parse_row_to_feature_with_mapping(
        row_number: int,
        row: List[str],
        column_mapping: Dict[str, int],
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

            # TODO: set multiple sprint for each task
            sprints = get_mapped_value("sprint")
            if sprints != "" and len(sprints.split(",")) >= 1:
                items = [p.strip() for p in sprints.split(",")]
                max_item = max(items, key=lambda t: int(t.split(":", 1)[0]))
                last_sprint = max_item
                sprint_list = items

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
                    if get_mapped_value("sprint") != "Select"
                    else None
                ),
                last_sprint=last_sprint if "last_sprint" in locals() else None,
                sprint_list=sprint_list if "sprint_list" in locals() else None,
                dependencies=(
                    get_mapped_value("dependencies")
                    if get_mapped_value("dependencies") != "Select"
                    else None
                ),
                initial_delivery_time=parse_date(
                    get_mapped_value("initial_delivery_time"),
                ),
                description=(
                    get_mapped_value("description")
                    if get_mapped_value("description")
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
            "۲": "SELECTED FOR DEVELOPMENT",
            "۲. تحلیل مسئله و RFP": "SELECTED FOR DEVELOPMENT",
            "۳. آماده سازی یوزر استوری": "TO DO",
            "۴. در مرحله طراحی": "IN REVIEW",
            "۵. پیاده سازی فنی": "OPEN",
            "۶. در حال پیاده سازی": "IN PROGRESS",
            "۷. تست فنی": "REVIEW",
            "۸. آماده تحویل": "RESOLVED",
            "۹. مستندسازی فنی": "DONE",
            "۱۰. تکمیل شده": "CLOSED",
        }

    def _create_epic_not_exist(
        self,
        epic_name: str,
        board_name: str,
    ) -> Tuple[bool, Optional[str]]:
        """Create if an epic doesn't exists in Jira.

        Args:
            epic_name: Epic name to create

        Returns:
            True if epic exists, False otherwise
            Epic key if exists, None otherwise
        """
        # TODO: clean and modify function name as its not needed this way anymore
        try:
            jql = f'project = "{board_name}" AND issuetype = Epic AND summary ~ "{epic_name}"'
            issues = self.jira_repository.search_issues(jql, max_results=1)
            if len(issues) == 0:
                task_data = TaskData(
                    project_key=board_name,
                    summary=epic_name,
                    description=f"Epic created for {epic_name}",  # TODO: add description from epic spec shet
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
        if (
            feature.ui_ux and feature.status == "۶. در حال پیاده سازی"
        ):  # در حال پیاده سازی # FIXME: use constants instead
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
            # Log available link types for debugging
            self._log_available_link_types()

            # Try to find the best link type for creating dependency
            available_link_types = self.jira_repository.get_issue_link_types()

            # Preferred link types in order of preference
            preferred_types = ["Dependency", "Blocks", "Relates to", "Relates"]
            selected_link_type = "Relates"  # Default fallback

            for preferred in preferred_types:
                for link_type in available_link_types:
                    if link_type["name"].lower() == preferred.lower():
                        selected_link_type = preferred
                        break
                if selected_link_type == preferred:
                    break

            # Create dependency link: PM Board issue depends on Developer Board issue
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
        due_date: Optional[str] = None,
    ) -> List[str]:
        """Create subtasks for each assignee.

        Args:
            parent_issue_key: Parent story issue key
            assignees: List of assignee usernames
            feature: Feature entity containing task details
            sprint_info: Sprint information
            due_date: Due date for subtasks

        Returns:
            List of created subtask keys
        """
        if not assignees:
            return []

        project_key = self.settings.developer_board_project_key
        created_subtasks = []

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

                story_points = self._get_assignee_story_points(
                    assignee,
                    feature,
                    component,
                )

                subtask_data = TaskData(
                    project_key=project_key,
                    summary=f"{feature.task_title}",
                    description=f"{feature.description or ''}",
                    task_type="Sub-task",
                    priority=self._map_priority(feature.priority),
                    components=[component] if component else None,
                    assignee=assignee,
                    parent_issue_key=parent_issue_key,
                    due_date=due_date,
                    story_points=story_points / 8 if story_points else 0,
                )

                subtask_issue = self.jira_repository.create_task(subtask_data)
                created_subtasks.append(subtask_issue.key)

                LOGGER.info(
                    f"Created subtask {subtask_issue.key} for assignee {assignee} in component {component}",
                )

            except Exception as e:
                LOGGER.error(f"Error creating subtask for assignee {assignee}: {e}")
                continue

        return created_subtasks

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
            "description": ["شرح", "Description"],
            "goals": ["اهداف", "Goals"],
            "delivery_process": ["فرایند تحویل", "Delivery Process"],
            "test_process": ["فرایند تست", "Test Process"],
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
                description=description,
                goals=get_mapped_value("goals") if get_mapped_value("goals") else None,
                delivery_process=(
                    get_mapped_value("delivery_process")
                    if get_mapped_value("delivery_process")
                    else None
                ),
                test_process=(
                    get_mapped_value("test_process")
                    if get_mapped_value("test_process")
                    else None
                ),
                telegram_message_id=(
                    get_mapped_value("telegram_message_id")
                    if get_mapped_value("telegram_message_id")
                    else None
                ),
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
            Story points allocation for the assignee
        """
        try:
            if component:
                story_points = int(
                    feature.__getattribute__(
                        component.lower().strip("-").replace("-", ""),
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
                assignee_name = self.jira_repository.get_issue(
                    subtask.key,
                ).fields.assignee.name
                if assignee_name:
                    current_assignees.add(assignee_name)
                    if assignee_name not in subtask_assignees:
                        subtask_assignees[assignee_name] = [subtask]
                    else:
                        subtask_assignees[assignee_name].append(subtask)

            # If assignees haven't changed, update time estimates on existing subtasks
            if set(feature_assignees) == current_assignees:
                await self._update_subtask_time_estimates(
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
                        # Delete the subtask
                        self.jira_repository.delete_issue(subtask.key)
                        LOGGER.info(
                            f"Deleted subtask {subtask.key} for removed assignee {old_assignee}",
                        )

                # Create or update subtasks for assignees (excluding main assignee)
                for assignee in feature_assignees:
                    if assignee not in subtask_assignees:
                        # Create new subtask
                        await self._create_subtask_for_assignee(
                            issue_key,
                            assignee,
                            feature,
                        )
                    else:
                        # Update existing subtask time estimate
                        subtask = subtask_assignees[assignee]
                        await self._update_subtask_time_estimate(
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
    ) -> Optional[str]:
        """Create a subtask for a specific assignee.

        Args:
            parent_issue_key: Parent issue key
            assignee: Assignee username
            feature: Feature entity

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

            subtask_data = TaskData(
                project_key=self.settings.developer_board_project_key,
                summary=f"{feature.task_title}",
                description=f"{feature.description or ''}",
                task_type="Sub-task",
                priority=self._map_priority(feature.priority),
                components=[component] if component else None,
                assignee=assignee,
                parent_issue_key=parent_issue_key,
                due_date=feature.deadline.strftime("%Y-%m-%d")
                if feature.deadline
                else None,
                story_points=story_points / 8 if story_points else 0,
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

    async def _update_subtask_time_estimates(
        self,
        subtasks: List,
        feature_assignees: List[str],
        feature: SynthPMFeatureEntity,
    ):
        """Update time estimates for all subtasks.

        Args:
            subtasks: List of subtask objects
            feature_assignees: List[str]: Feature assignees
            feature: SynthPMFeatureEntity,
        """
        for subtask in subtasks:
            subtask_assignee = self.jira_repository.get_issue(
                subtask.key,
            ).fields.assignee.name
            if subtask_assignee in feature_assignees:
                await self._update_subtask_time_estimate(
                    subtask,
                    subtask_assignee,
                    feature,
                )

    async def _update_subtask_time_estimate(
        self,
        subtask,
        assignee: str,
        feature: SynthPMFeatureEntity,
    ):
        """Update time estimate for a specific subtask.

        Args:
            subtask: Subtask object
            assignee: Assignee username
            feature: Feature entity
        """
        try:
            component = self.user_config.get_user_component(
                assignee,
                self.settings.developer_board_project_key,
            )

            # Get time allocation for this assignee
            # TODO: get issue of subtask from the very first function call to avoid lots of redundant calls
            story_point_hour = self._get_assignee_story_points(
                assignee,
                feature,
                component,
            )
            issue = self.jira_repository.get_issue(subtask.key)
            # Update subtask if story points changed
            issue_time = issue.fields.timetracking
            current_story_points = (
                getattr(
                    issue_time,
                    "originalEstimateSeconds",
                    0,
                )
                / 3600
            )

            if (
                abs(current_story_points - story_point_hour) > 0.01
            ):  # Avoid floating point precision issues
                # TODO: update the time correctly
                logged_time = int(
                    self.jira_repository.get_issue_spent_time_in_seconds(subtask.key)
                    / 3600,
                )
                remaining_estimate = (
                    story_point_hour - logged_time
                    if logged_time < story_point_hour
                    else 0
                )
                update_fields = {
                    "timetracking": {
                        "originalEstimate": f"{story_point_hour}h",
                        "remainingEstimate": f"{remaining_estimate}h",
                    },
                }
                subtask.update(fields=update_fields)
                LOGGER.info(
                    f"Updated time estimate for subtask {subtask.key}: {story_point_hour} story points",
                )

        except Exception as e:
            LOGGER.error(f"Error updating time estimate for subtask {subtask.key}: {e}")
