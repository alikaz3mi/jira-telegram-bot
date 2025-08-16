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

from jira_telegram_bot import LOGGER, DEFAULT_PATH
from jira_telegram_bot.adapters.google_sheet import GoogleSheetClient
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMSheetSyncStatus
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity, SprintInfo
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.synth_pm_repository_interface import (
    SynthPMRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface


class SynthPMRepository(SynthPMRepositoryInterface):
    """Repository implementation for SynthPM operations."""
    
    def __init__(
        self,
        google_sheet_client: GoogleSheetClient,
        jira_repository: TaskManagerRepositoryInterface,
        settings: SynthPMSettings,
        user_config: UserConfigInterface
        
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
        self.sync_status_file = Path(f"{DEFAULT_PATH}/data/synth_developer_board_sync_status.json")
        self.user_config = user_config
        self.developer_board_id = self.jira_repository.get_board_id(self.settings.developer_board_project_key)
        self.pm_board_id = self.jira_repository.get_board_id(self.settings.pm_project_key)
        
        
        
    async def get_developer_board_features(self) -> List[SynthPMFeatureEntity]:
        """Get all eatures from Google Sheets.
        
        Returns:
            List of eature entities
        """
        try:
            # Get data from sheet - expand range to include all person columns
            values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                f"{self.settings.developer_board_worksheet_name}!A:AZ"  # Extended range for all columns
            )
            
            if not values or len(values) < 2:
                LOGGER.warning("No data found in Features sheet")
                return []
            
            # Get headers from first row and create column mapping
            headers = values[0]
            column_mapping = self._create_column_mapping(headers)
            
            # Skip header row
            data_rows = values[1:]
            features = []
            
            for idx, row in enumerate(data_rows, start=2):  # Start from row 2
                if len(row) < 2:  # Skip empty rows
                    continue
                    
                feature = self._parse_row_to_feature_with_mapping(idx, row, column_mapping)
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
        updates: Dict[str, any]
    ) -> bool:
        """Update a specific feature in Google Sheets.
        
        Args:
            row_number: Row number to update
            updates: Dictionary of field updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get headers to create column mapping
            headers_range = f"{self.settings.developer_board_worksheet_name}!1:1"
            headers_values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                headers_range
            )
            
            if not headers_values:
                LOGGER.error("Could not retrieve headers for column mapping")
                return False
            
            headers = headers_values[0]
            column_mapping = self._create_column_mapping(headers)
            
            # Map field names to column indices and update
            for field, value in updates.items():
                if field in column_mapping:
                    col_idx = column_mapping[field]
                    col_letter = self._number_to_column_letter(col_idx + 1)  # +1 for 1-based indexing
                    range_name = f"{self.settings.developer_board_worksheet_name}!{col_letter}{row_number}"
                    
                    success = await self.google_sheet_client.update_cells(
                        self.settings.google_sheets_id,
                        range_name,
                        [[str(value) if value is not None else ""]]
                    )
                    
                    if not success:
                        LOGGER.error(f"Failed to update field {field} in row {row_number}")
                        return False
                else:
                    LOGGER.warning(f"Field {field} not found in column mapping, skipping")
            
            LOGGER.info(f"Successfully updated row {row_number} with {len(updates)} fields")
            return True
            
        except Exception as e:
            LOGGER.error(f"Error updating feature row {row_number}: {e}")
            return False
    
    async def create_jira_task_from_feature(
        self, 
        feature: SynthPMFeatureEntity
    ) -> Optional[str]:
        """Create a PM Board Jira task from a feature.
        Note: task creation moved to separate method.
        
        Args:
            feature: feature entity
            
        Returns:
            PM Board Jira issue key if successful, None otherwise
        """
        try:
            # Format due date properly
            due_date = None
            if feature.deadline:
                if isinstance(feature.deadline, str):
                    due_date = feature.deadline
                else:
                    # Convert datetime to string format YYYY-MM-DD
                    due_date = feature.deadline.strftime("%Y-%m-%d")
            
            # Handle epic link - only set if it exists and is not empty
            epic_link = None
            if feature.epic and feature.epic.strip() and feature.epic != "Select": # TODO: what is Select? 
                # Validate epic exists in Jira before setting it
                epic_exists, epic_key = self._validate_epic_exists(feature.epic, self.settings.pm_project_key)
                if epic_exists:
                    epic_link = epic_key
                else:
                    LOGGER.warning(f"Epic '{feature.epic}' not found in Jira, skipping epic assignment") # FIXME: the epic must be created if not exists
            
            # Determine status based on components and current status
            jira_status = self._determine_jira_status(feature)
            # FIXME: check if the issue exists. If it exists, update it instead of creating a new one. To check for the issue existance, check its label starting with PM, and its title
            
            # Map feature components to Jira components
            components = self._map_components(feature) # FIXME: get compoments from column department instead
            labels = [feature.involved_people] if feature.involved_people else []
            labels = labels + [f'PM-{feature.row_number}']  # Add row number as label
            # Create task in PM Board project first
            pm_board_task_data = TaskData(
                project_key=self.settings.pm_project_key,  # PM Board
                summary=feature.task_title,
                description=feature.description or "",
                task_type="Task",
                priority=self._map_priority(feature.priority),
                epic_link=epic_link,
                labels=labels,
                components=components,
                story_points=(feature.total_hours) / 8 if feature.total_hours else 0,  # Set story points from total hours
                assignee=None,
                due_date=due_date,
            )
            
            # Set additional fields if available
            if feature.sprint:
                pm_board_task_data.sprint_id = self._get_sprint_id(feature.sprint)
            
            pm_board_issue = self.jira_repository.create_task(pm_board_task_data)
            LOGGER.info(f"Created PM Board task {pm_board_issue.key} for feature: {feature.task_title}: {self.jira_repository.get_issue_url(pm_board_issue)}")
            
            # Update status if needed
            if jira_status != "To Do":
                try:
                    self._transition_issue_to_status(pm_board_issue.key, jira_status)
                except Exception as e:
                    LOGGER.warning(f"Could not transition issue to {jira_status}: {e}")
            
            # Update the sheet with the PM Board issue key only
            await self.update_developer_board_feature(
                feature.row_number,
                {"jira_issue_key": pm_board_issue.key}
            )
            
            return pm_board_issue.key
            
        except Exception as e:
            error_msg = f"Error creating Jira tasks for feature {feature.task_title}: {e}"
            LOGGER.error(error_msg)
            
            # Log more details for debugging
            LOGGER.debug(f"Feature data: epic='{feature.epic}', deadline='{feature.deadline}' (type: {type(feature.deadline)})")
            
            return None
    
    async def update_jira_task_from_feature(
        self, 
        feature: SynthPMFeatureEntity
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
            
            # Get the existing issue
            issue = self.jira_repository.get_issue(feature.jira_issue_key)
            if not issue:
                LOGGER.warning(f"Jira issue {feature.jira_issue_key} not found")
                return False
            
            # Update issue fields
            update_fields = {}
            
            if feature.task_title:
                update_fields["summary"] = feature.task_title
            
            if feature.description:
                update_fields["description"] = feature.description
            
            if feature.priority:
                update_fields["priority"] = {"name": self._map_priority(feature.priority)}
            
            if feature.deadline:
                update_fields["duedate"] = feature.deadline.strftime("%Y-%m-%d")
            
            if feature.status:
                # Handle status transitions
                status_mapping = self._get_status_mapping()
                if feature.status in status_mapping:
                    jira_status = status_mapping[feature.status]
                    # Get available transitions and transition if possible
                    transitions = self.jira_repository.get_transitions(feature.jira_issue_key)
                    for transition in transitions:
                        if transition["to"]["name"] == jira_status:
                            self.jira_repository.transition_issue(
                                feature.jira_issue_key,
                                transition["id"]
                            )
                            break
            
            if update_fields:
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
            # Get data from Release Notes sheet
            values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                f"{self.settings.release_notes_worksheet_name}!A:H"  # Extended range for all columns
            )
            
            if not values or len(values) < 2:
                LOGGER.warning("No data found in Release Notes sheet")
                return []
            
            # Get headers from first row and create column mapping
            headers = values[0]
            column_mapping = self._create_release_notes_column_mapping(headers)
            
            # Skip header row
            data_rows = values[1:]
            release_notes = []
            
            for idx, row in enumerate(data_rows, start=2):  # Start from row 2
                if len(row) < 2:  # Skip empty rows
                    continue
                    
                release_note = self._parse_row_to_release_note(idx, row, column_mapping)
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
        updates: Dict[str, any]
    ) -> bool:
        """Update a specific release note in Google Sheets.
        
        Args:
            row_number: Row number to update
            updates: Dictionary of field updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Similar to update_developer_board_feature but for Release Notes sheet
            headers_range = f"{self.settings.release_notes_worksheet_name}!1:1"
            headers_values = await self.google_sheet_client.get_values(
                self.settings.google_sheets_id,
                headers_range
            )
            
            if not headers_values:
                LOGGER.error("Could not retrieve headers for release notes column mapping")
                return False
            
            headers = headers_values[0]
            column_mapping = self._create_release_notes_column_mapping(headers)
            
            # Map field names to column indices and update
            for field, value in updates.items():
                if field in column_mapping:
                    col_idx = column_mapping[field]
                    col_letter = self._number_to_column_letter(col_idx + 1)
                    range_name = f"{self.settings.release_notes_worksheet_name}!{col_letter}{row_number}"
                    
                    success = await self.google_sheet_client.update_cells(
                        self.settings.google_sheets_id,
                        range_name,
                        [[str(value) if value is not None else ""]]
                    )
                    
                    if not success:
                        LOGGER.error(f"Failed to update field {field} in release note row {row_number}")
                        return False
                else:
                    LOGGER.warning(f"Field {field} not found in release notes column mapping, skipping")
            
            LOGGER.info(f"Successfully updated release note row {row_number} with {len(updates)} fields")
            return True
            
        except Exception as e:
            LOGGER.error(f"Error updating release note row {row_number}: {e}")
            return False
    
    async def create_developer_board_task_from_feature(
        self, 
        feature: SynthPMFeatureEntity,
        sprint_info: SprintInfo,
        assignees: Optional[List[str]] = None
    ) -> Optional[str]:
        """Create a Jira task from a feature with sprint.
        
        Args:
            feature: feature entity
            sprint_info: Sprint information for board
            assignees: List of assignee usernames for the task
            
        Returns:
            Jira issue key if successful, None otherwise
        """
        try:
            if not feature.jira_issue_key:
                LOGGER.error("Cannot create task without existing PM Board task")
                return None
            
            # Format due date properly
            due_date = None
            if feature.deadline:
                if isinstance(feature.deadline, str):
                    due_date = feature.deadline
                else:
                    due_date = feature.deadline.strftime("%Y-%m-%d")
            
            # Handle epic link
            epic_link = None
            if feature.epic and feature.epic.strip() and feature.epic != "Select":
                epic_exists, epic_key = self._validate_epic_exists(feature.epic, self.settings.developer_board_project_key)
                if not epic_exists:
                    LOGGER.warning(f"Epic '{feature.epic}' not found in Jira, skipping epic assignment")
                else:
                    # Only set epic link if it exists
                    epic_link = epic_key
            
            # Map components 
            components = self._map_components(feature)
            
            # Determine main assignee (first in list or None)
            main_assignee = assignees[0] if assignees else None
            
            # TODO: add sprint id and name. And set the current date if the dates are from Jalali calendar
            # TODO: set the year dynamically
            sprint = self.jira_repository.get_sprint_by_id(sprint_info.sprint_id, self.developer_board_id)
            
            if sprint is None:
                start_date = sprint_info.start_date
                end_date = sprint_info.end_date
                # LOGGER.error(f"Sprint with ID {sprint_info.sprint_id} not found in Jira")
                start_date = jdatetime.JalaliToGregorian(1404, int(start_date.split("-")[0]), int(start_date.split("-")[1]))
                end_date = jdatetime.JalaliToGregorian(1404, int(end_date.split("-")[0]), int(end_date.split("-")[1]))
                start_date = start_date.getGregorianList()
                end_date = end_date.getGregorianList()
                sprint = self.jira_repository.create_sprint(
                    board_id=self.developer_board_id,
                    sprint_name=f'{"board_id"} Sprint {sprint_info.sprint_id}',
                    start_date=start_date,
                    end_date=end_date,
                )
            
            # Create task with enhanced linking
            developer_board_task_data = TaskData(
                project_key=self.settings.developer_board_project_key,
                summary=f"{feature.task_title} (Sprint: {sprint_info.sprint_id})",
                description=f"🔗 **Linked to PM Board**: {feature.jira_issue_key}\n\n"
                           f"📅 **Sprint**: {sprint_info.sprint_id} ({sprint_info.start_date} - {sprint_info.end_date})\n\n"
                           f"👥 **Assignees**: {', '.join(assignees) if assignees else 'Unassigned'}\n\n"
                           f"📝 **Original ETA**: {feature.eta_hours}h\n\n"
                           f"{feature.description or ''}",
                task_type="Story",  # Use Story for 
                priority=self._map_priority(feature.priority),
                epic_link=epic_link,
                labels=[f"PM Board-{feature.jira_issue_key}", f"Sprint-{sprint_info.sprint_id}"] + (assignees or []), #TODO: check this one later
                components=components,
                assignee=main_assignee,
                due_date=due_date,
                story_points=feature.eta_hours,  # Set story points from ETA hours
            )
            
            # Create the issue
            developer_board_issue = self.jira_repository.create_task(developer_board_task_data)
            LOGGER.info(f"Created task {developer_board_issue.key} for feature: {feature.task_title}")
            
            # Link the issues
            try:
                self._link_issues(feature.jira_issue_key, developer_board_issue.key)
            except Exception as e:
                LOGGER.warning(f"Could not link issues {feature.jira_issue_key} and {developer_board_issue.key}: {e}")
            
            # Add issue key as label to PM Board task
            try:
                await self._add_label_to_issue(feature.jira_issue_key, f"PM-{developer_board_issue.key}")
            except Exception as e:
                LOGGER.warning(f"Could not add label to PM Board issue: {e}")
            
            # Update the sheet with issue key
            await self.update_developer_board_feature(
                feature.row_number,
                {"developer_board_issue_key": developer_board_issue.key}
            )
            
            return developer_board_issue.key
            
        except Exception as e:
            LOGGER.error(f"Error creating task for feature {feature.task_title}: {e}")
            return None
    
    async def update_developer_board_task_from_feature(
        self, 
        feature: SynthPMFeatureEntity,
        assignees: Optional[List[str]] = None
    ) -> bool:
        """Update an existing Jira task from a feature.
        
        Args:
            feature: feature entity
            assignees: List of assignee usernames for the task
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not feature.developer_board_issue_key:
                LOGGER.warning(f"No issue key for feature: {feature.task_title}")
                return False
            
            # Similar to update_jira_task_from_feature but for 
            issue = self.jira_repository.get_issue(feature.developer_board_issue_key)
            if not issue:
                LOGGER.warning(f"issue {feature.developer_board_issue_key} not found")
                return False
            
            # Update issue fields
            update_fields = {}
            
            if feature.task_title:
                # Keep sprint info in summary
                current_summary = issue.fields.summary
                if "(Sprint:" in current_summary:
                    sprint_part = current_summary[current_summary.find("(Sprint:"):]
                    update_fields["summary"] = f"{feature.task_title} {sprint_part}"
                else:
                    update_fields["summary"] = feature.task_title
            
            if feature.description:
                # Preserve linked PM Board info and assignees info
                current_desc = issue.fields.description or ""
                preserved_lines = []
                
                # Keep existing linked info
                lines = current_desc.split("\n")
                for line in lines:
                    if any(keyword in line for keyword in ["🔗 **Linked to PM Board**:", "📅 **Sprint**:", "👥 **Assignees**:", "📝 **Original ETA**:"]):
                        preserved_lines.append(line)
                    elif line.strip() == "":
                        preserved_lines.append(line)
                        if len(preserved_lines) > 5:  # Stop after initial preserved content
                            break
                
                # Update assignees info if provided
                if assignees:
                    # Replace assignees line
                    preserved_lines = [line for line in preserved_lines if "👥 **Assignees**:" not in line]
                    preserved_lines.insert(-1, f"👥 **Assignees**: {', '.join(assignees)}")
                
                update_fields["description"] = "\n".join(preserved_lines) + f"\n{feature.description}"
            
            if feature.priority:
                update_fields["priority"] = {"name": self._map_priority(feature.priority)}
            
            if feature.deadline:
                update_fields["duedate"] = feature.deadline.strftime("%Y-%m-%d")
            
            # Update assignee if provided
            if assignees:
                update_fields["assignee"] = {"name": assignees[0]}  # Assign to first person
                
                # Update labels to include all assignees
                current_labels = [label.name for label in issue.fields.labels]
                # Keep non-person labels
                # FIXME
                new_labels = [label for label in current_labels if not any(person in label for person in ["kazemi", "mousavi", "moradi", "janloo", "hosseini", "ghamari", "zangane", "samei", "aroji", "lotfian", "adabi", "dadjo", "sadraei", "emam", "nasim", "heravi"])]
                # Add new assignees as labels
                new_labels.extend(assignees)
                update_fields["labels"] = [{"add": label} for label in new_labels]
            
            # Update story points based on ETA hours
            if feature.eta_hours:
                update_fields["customfield_10002"] = feature.eta_hours  # Story points field
            
            if update_fields:
                issue.update(fields=update_fields)
                LOGGER.info(f"Updated task {feature.developer_board_issue_key}")
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Error updating task {feature.developer_board_issue_key}: {e}")
            return False
    
    async def track_time_in_developer_board(
        self,
        developer_board_issue_key: str,
        time_spent: int,
        user: str
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
            # Get issue
            developer_board_issue = self.jira_repository.get_issue(developer_board_issue_key)
            if not developer_board_issue:
                LOGGER.error(f"issue {developer_board_issue_key} not found")
                return False
            
            # Find linked PM Board issue from labels
            pm_board_issue_key = None
            for label in developer_board_issue.fields.labels:
                # FIXME
                if label.startswith("PM Board-"):
                    pm_board_issue_key = label.replace("PM Board-", "")
                    break
            
            if not pm_board_issue_key:
                LOGGER.error(f"No linked PM Board issue found for {developer_board_issue_key}")
                return False
            
            # Get PM Board issue
            pm_board_issue = self.jira_repository.get_issue(pm_board_issue_key)
            if not pm_board_issue:
                LOGGER.error(f"Linked PM Board issue {pm_board_issue_key} not found")
                return False
            
            # Log time in developer board
            worklog = self.jira_repository.add_worklog(
                developer_board_issue_key,
                timeSpent=f"{time_spent}h",
                comment=f"Time tracked by {user}"
            )
            
            if worklog:
                # Deduct from PM Board story points
                current_story_points = getattr(pm_board_issue.fields, 'customfield_10002', 0) or 0
                new_story_points = max(0, current_story_points - time_spent)
                
                pm_board_issue.update(fields={"customfield_10002": new_story_points})
                
                LOGGER.info(f"Tracked {time_spent}h for {user} on {developer_board_issue_key}, "
                           f"deducted from PM Board {pm_board_issue_key} story points: {current_story_points} -> {new_story_points}")
                
                # Update Google Sheet with remaining hours
                features = await self.get_developer_board_features()
                for feature in features:
                    if feature.jira_issue_key == pm_board_issue_key:
                        await self.update_developer_board_feature(
                            feature.row_number,
                            {"total_hours": new_story_points}
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
            # Ensure directory exists
            self.sync_status_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.sync_status_file, "w", encoding="utf-8") as f:
                json.dump(status.dict(), f, ensure_ascii=False, indent=2, default=str)
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Error updating sync status: {e}")
            return False
    
    def _create_column_mapping(self, headers: List[str]) -> Dict[str, int]:
        """Create mapping from column names to indices.
        
        Args:
            headers: List of column headers from the sheet
            
        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}
        
        # Define the column name mappings (Persian and English variations)
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
            "implementation_start_date": ["تاریخ شروع پیاده سازی", "Implementation Start", "تاریخ شروع پیاده سازی"],
            "deadline": ["ددلاین", "Deadline", "ددلاین"],
            "sprint": ["اسپرینت", "Sprint", "اسپرینت"],
            "dependencies": ["وابستگی ها", "Dependencies", "وابستگی ها"],
            "initial_delivery_time": ["زمان تحویل اولیه", "Initial Delivery", "زمان تحویل اولیه"],
            "description": ["توضیحات", "Description", "توضیحات"],
            # People columns
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
        }
        
        # Create reverse lookup for headers
        for idx, header in enumerate(headers):
            header_clean = header.strip()
            
            # Find matching field name
            for field_name, possible_names in column_name_mappings.items():
                if header_clean in possible_names:
                    mapping[field_name] = idx
                    break
        
        LOGGER.info(f"Created column mapping with {len(mapping)} fields")
        LOGGER.debug(f"Column mapping: {mapping}")
        
        return mapping
    
    def _parse_row_to_feature_with_mapping(
        self, 
        row_number: int, 
        row: List[str], 
        column_mapping: Dict[str, int]
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
            # Safely get values using column mapping
            def get_mapped_value(field_name: str) -> str:
                col_idx = column_mapping.get(field_name)
                if col_idx is not None and col_idx < len(row):
                    return row[col_idx].strip() if row[col_idx] else ""
                return ""
            
            # Parse dates safely
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
            
            # Parse integers safely
            def parse_int(value_str: str) -> Optional[int]:
                if not value_str or value_str.lower() in ["", "select", "sum:", "count:"]:
                    return None
                try:
                    # Extract number from strings like "Sum: 56"
                    if ":" in value_str:
                        value_str = value_str.split(":")[-1].strip()
                    return int(float(value_str))
                except (ValueError, TypeError):
                    return None
            
            # Check if we have required fields
            task_title = get_mapped_value("task_title")
            if not task_title:
                return None  # Skip rows without task title
            
            return SynthPMFeatureEntity(
                row_number=row_number,
                task_title=task_title,
                epic=get_mapped_value("epic") if get_mapped_value("epic") != "Select" else None,
                release=get_mapped_value("release") if get_mapped_value("release") != "Select" else None,
                necessity=get_mapped_value("necessity") if get_mapped_value("necessity") != "Select" else None,
                priority=get_mapped_value("priority") if get_mapped_value("priority") != "Select" else None,
                status=get_mapped_value("status") if get_mapped_value("status") != "Select" else None,
                eta_hours=parse_int(get_mapped_value("eta_hours")),
                total_hours=parse_int(get_mapped_value("total_hours")),
                departments=get_mapped_value("departments") if get_mapped_value("departments") != "Select" else None,
                involved_people=get_mapped_value("involved_people") if get_mapped_value("involved_people") != "Select" else None,
                ai=get_mapped_value("ai") if get_mapped_value("ai") != "Select" else None,
                backend=get_mapped_value("backend") if get_mapped_value("backend") != "Select" else None,
                frontend=get_mapped_value("frontend") if get_mapped_value("frontend") != "Select" else None,
                devops=get_mapped_value("devops") if get_mapped_value("devops") != "Select" else None,
                ui_ux=get_mapped_value("ui_ux") if get_mapped_value("ui_ux") != "Select" else None,
                creation_date=parse_date(get_mapped_value("creation_date")),
                implementation_start_date=parse_date(get_mapped_value("implementation_start_date")),
                deadline=parse_date(get_mapped_value("deadline")),
                sprint=get_mapped_value("sprint") if get_mapped_value("sprint") != "Select" else None,
                dependencies=get_mapped_value("dependencies") if get_mapped_value("dependencies") != "Select" else None,
                initial_delivery_time=parse_date(get_mapped_value("initial_delivery_time")),
                description=get_mapped_value("description") if get_mapped_value("description") else None,
                jira_issue_key=None,  # Will be populated separately
                developer_board_issue_key=None,  # Will be populated separately
            )
            
        except Exception as e:
            LOGGER.error(f"Error parsing row {row_number}: {e}")
            return None
    
    def _number_to_column_letter(self, col_num: int) -> str:
        """Convert column number to Excel column letter.
        
        Args:
            col_num: Column number (1-based)
            
        Returns:
            Excel column letter (e.g., 1 -> A, 26 -> Z, 27 -> AA)
        """
        result = ""
        while col_num > 0:
            col_num -= 1
            result = chr(col_num % 26 + ord('A')) + result
            col_num //= 26
        return result
    
    def _map_priority(self, priority: Optional[str]) -> str:
        """Map sheet priority to Jira priority.
        
        Args:
            priority: Priority from sheet
            
        Returns:
            Jira priority name
        """
        if not priority:
            return "Medium"
        
        # Standard Jira priority mapping - matching Highest, High, Medium, Low
        priority_mapping = {
            "Highest": "Highest",
            "High": "High", 
            "Medium": "Medium",
            "Low": "Low",
            "Lowest": "Lowest",
            # Persian mappings with full descriptions
            "۱": "Highest",  # ۱. بالاترین
            "۱. بالاترین": "Highest",
            "۲": "High",  # ۲. بالا
            "۲. بالا": "High",
            "۳": "Medium",  # ۳. متوسط
            "۳. متوسط": "Medium",
            "۴": "Low",  # ۴. پایین
            "۴. پایین": "Low",
            "۵": "Lowest",  # ۵. پایین ترین
            "۵. پایین ترین": "Lowest",
            # Legacy mappings for backward compatibility
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
        
        # Map department flags to component names
        if feature.ai != '' and float(feature.ai) > 0:
            components.append("AI")
        if feature.backend != '' and float(feature.backend) > 0:
            components.append("Backend")
        if feature.frontend != '' and float(feature.frontend) > 0:
            components.append("Front-end")
        if feature.devops != '' and float(feature.devops) > 0:
            components.append("DevOps")
        if feature.ui_ux != '' and float(feature.ui_ux) > 0:
            components.append("UI/UX")
        
        return components
    
    def _get_status_mapping(self) -> Dict[str, str]:
        """Get mapping of sheet status to Jira status.
        
        Returns:
            Dictionary mapping sheet status to Jira status
        """
        return {
            # Sheet -> Jira mapping (based on actual Jira workflow)
            "۱": "BACKLOG",  # ۱. ثبت و اولویت بندی
            "۱. ثبت و اولویت بندی": "BACKLOG",
            "۲": "SELECTED FOR DEVELOPMENT",  # ۲. تحلیل مسئله و RFP
            "۲. تحلیل مسئله و RFP": "SELECTED FOR DEVELOPMENT",
            "۳": "TO DO",  # ۳. برری بوردو اسپوری
            "۳. برری بوردو اسپوری": "TO DO",
            "۴": "IN REVIEW",  # ۴. در مرحله طراحی
            "۴. در مرحله طراحی": "IN REVIEW",
            "۵": "REOPENED",  # ۵. پیاده سازی فنی (or OPEN)
            "۵. پیاده سازی فنی": "REOPENED",
            "۶": "IN PROGRESS",  # ۶. در حال پیاده سازی
            "۶. در حال پیاده سازی": "IN PROGRESS",
            "۷": "REVIEW",  # ۷. تست فنی
            "۷. تست فنی": "REVIEW",
            "۸": "RESOLVED",  # ۸. آماده تحویل
            "۸. آماده تحویل": "RESOLVED",
            "۹": "DONE",  # ۹. مستندسازی فنی
            "۹. مستندسازی فنی": "DONE",
            "۱۰": "CLOSED",  # ۱۰. تکمیل شده
            "۱۰. تکمیل شده": "CLOSED",
            # Legacy mappings for backward compatibility
            "بررسی": "REVIEW",
            "تست": "REVIEW",
            "آماده انتشار": "DONE",
        }
    
    def _validate_epic_exists(self, epic_name: str, board_name: str) -> Tuple[bool, Optional[str]]:
        """Validate if an epic exists in Jira.
        
        Args:
            epic_name: Epic name to validate
            
        Returns:
            True if epic exists, False otherwise
            Epic key if exists, None otherwise
        """
        # TODO: clean and modify function name as its not needed this way anymore
        try:
            # Search for epic by name in the project
            jql = f'project = "{board_name}" AND issuetype = Epic AND summary ~ "{epic_name}"'
            issues = self.jira_repository.search_issues(jql, max_results=1)
            if len(issues) == 0:
                task_data = TaskData(
                    project_key=board_name,
                    summary=epic_name,
                    description=f"Epic created for {epic_name}", # TODO: add description from epic spec shet 
                    task_type="Epic"
                )
                issue = self.jira_repository.create_task(task_data)
                issues = [issue]
            
            return len(issues) > 0, issues[0].key if issues else None
        except Exception as e:
            LOGGER.warning(f"Error validating epic '{epic_name}': {e}")
            return False, None
    
    def _get_sprint_id(self, sprint_name: str) -> Optional[int]:
        """Get sprint ID by name.
        
        Args:
            sprint_name: Sprint name
            
        Returns:
            Sprint ID if found, None otherwise
        """
        try:
            # This is a placeholder - implement based on your Jira setup
            # You might need to query active sprints in your board
            LOGGER.info(f"Sprint lookup not implemented for: {sprint_name}")
            return None
        except Exception as e:
            LOGGER.warning(f"Error getting sprint ID for '{sprint_name}': {e}")
            return None
    
    def _get_sprint_id(self, sprint_name: str) -> Optional[int]:
        """Get sprint ID from sprint name.
        
        Args:
            sprint_name: Name of the sprint
            
        Returns:
            Sprint ID or None if not found
        """
        try:
            # This would need to be implemented based on your Jira repository
            # For now, return None
            return None
        except Exception as e:
            LOGGER.error(f"Error getting sprint ID for {sprint_name}: {e}")
            return None
    
    def _determine_jira_status(self, feature: SynthPMFeatureEntity) -> str:
        """Determine the appropriate Jira status based on feature properties.
        
        Args:
            feature: feature entity
            
        Returns:
            Jira status name
        """
        # Check if this is a UI/UX task and it's in progress
        if feature.ui_ux and feature.status == "۶. در حال پیاده سازی":  # در حال پیاده سازی # FIXME: use constants instead
            return "In Progress"  # ۴. در مرحله طراحی
        
        # Map other statuses
        status_mapping = self._get_status_mapping()
        jira_status = status_mapping.get(feature.status, "To Do")
        
        # Special handling for "Selected for Development" fallback
        if jira_status == "Selected for Development":
            # If "Selected for Development" doesn't exist, use "To Do"
            return "To Do"
        
        return jira_status
    
    def _link_issues(self, pm_board_issue_key: str, developer_board_issue_key: str):
        """Link PM Board and issues.
        
        Args:
            pm_board_issue_key: PM Board issue key
            developer_board_issue_key: issue key
        """
        try:
            # This would need to be implemented based on your Jira repository
            # For now, we use labels to indicate the relationship
            LOGGER.info(f"Issues linked via labels: {pm_board_issue_key} <-> {developer_board_issue_key}")
        except Exception as e:
            LOGGER.error(f"Error linking issues {pm_board_issue_key} and {developer_board_issue_key}: {e}")
    
    def _transition_issue_to_status(self, issue_key: str, target_status: str):
        """Transition an issue to the target status.
        
        Args:
            issue_key: Jira issue key
            target_status: Target status name
        """
        try:
            # Get available transitions
            transitions = self.jira_repository.get_transitions(issue_key)
            transitioned = False
            # Find the transition to target status
            for transition in transitions:
                if transition["to"]["name"].lower() == target_status.lower():
                    self.jira_repository.transition_issue(issue_key, transition["id"])
                    LOGGER.info(f"Transitioned {issue_key} to {target_status}")
                    transitioned = True
                    return

            LOGGER.warning(f"No transition found to {target_status} for {issue_key}")
        except Exception as e:
            LOGGER.error(f"Error transitioning {issue_key} to {target_status}: {e}")
    
    def _get_reverse_status_mapping(self) -> Dict[str, str]:
        """Get mapping of Jira status to sheet status.
        
        Returns:
            Dictionary mapping Jira status to sheet status
        """
        return {
            # Jira -> Sheet mapping (based on actual Jira workflow)
            "BACKLOG": "۱",  # ثبت و اولویت بندی
            "SELECTED FOR DEVELOPMENT": "۲",  # تحلیل مسئله و RFP
            "TO DO": "۳",  # برری بوردو اسپوری 
            "IN REVIEW": "۴",  # در مرحله طراحی
            "REOPENED": "۵",  # پیاده سازی فنی
            "OPEN": "۵",  # پیاده سازی فنی
            "IN PROGRESS": "۶",  # در حال پیاده سازی
            "REVIEW": "۷",  # تست فنی
            "RESOLVED": "۸",  # آماده تحویل
            "DONE": "۹",  # مستندسازی فنی
            "CLOSED": "۱۰",  # تکمیل شده
        }
    
    async def _add_label_to_issue(self, issue_key: str, label: str):
        """Add a label to an existing Jira issue.
        
        Args:
            issue_key: Jira issue key
            label: Label to add
        """
        try:
            issue = self.jira_repository.get_issue(issue_key)
            if issue:
                current_labels = [label.name for label in issue.fields.labels]
                if label not in current_labels:
                    current_labels.append(label)
                    issue.update(fields={"labels": [{"set": current_labels}]})
                    LOGGER.info(f"Added label '{label}' to issue {issue_key}")
        except Exception as e:
            LOGGER.error(f"Error adding label to issue {issue_key}: {e}")
    
    def _create_release_notes_column_mapping(self, headers: List[str]) -> Dict[str, int]:
        """Create column mapping for Release Notes sheet.
        
        Args:
            headers: List of column headers from the Release Notes sheet
            
        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}
        
        # Define the column name mappings for Release Notes
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
        
        # Create reverse lookup for headers
        for idx, header in enumerate(headers):
            header_clean = header.strip()
            
            # Find matching field name
            for field_name, possible_names in column_name_mappings.items():
                if header_clean in possible_names:
                    mapping[field_name] = idx
                    break
        
        return mapping
    
    def _parse_row_to_release_note(
        self, 
        row_number: int, 
        row: List[str], 
        column_mapping: Dict[str, int]
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
            # Safely get values using column mapping
            def get_mapped_value(field_name: str) -> str:
                col_idx = column_mapping.get(field_name)
                if col_idx is not None and col_idx < len(row):
                    return row[col_idx].strip() if row[col_idx] else ""
                return ""
            
            # Parse dates safely
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
            
            # Check if we have required fields
            release_version = get_mapped_value("release_version")
            release_components = get_mapped_value("release_components")
            description = get_mapped_value("description")
            
            if not release_version or not release_components or not description:
                return None  # Skip rows without required fields
            
            return ReleaseNoteEntity(
                row_number=row_number,
                release_version=release_version,
                release_components=release_components,
                description=description,
                goals=get_mapped_value("goals") if get_mapped_value("goals") else None,
                delivery_process=get_mapped_value("delivery_process") if get_mapped_value("delivery_process") else None,
                test_process=get_mapped_value("test_process") if get_mapped_value("test_process") else None,
                telegram_message_id=get_mapped_value("telegram_message_id") if get_mapped_value("telegram_message_id") else None,
                last_updated=parse_date(get_mapped_value("last_updated")),
            )
            
        except Exception as e:
            LOGGER.error(f"Error parsing release note row {row_number}: {e}")
            return None
