"""Jira adapter for SynthPM operations."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.synth_pm.mixins.jira_operations_mixin import (
    JiraOperationsMixin,
)
from jira_telegram_bot.entities.release_notes import SprintInfo
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.services import SynthPMComponentService
from jira_telegram_bot.entities.synth_pm.services import SynthPMStatusService
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class SynthPMJiraAdapter(JiraOperationsMixin):
    """Adapter for SynthPM Jira operations."""

    def __init__(
        self,
        jira_repository: TaskManagerRepositoryInterface,
        settings: SynthPMSettings,
    ):
        """Initialize the adapter.

        Args:
            jira_repository: Jira repository interface
            settings: SynthPM settings
        """
        self.jira_repository = jira_repository
        self.settings = settings
        self.developer_board_id = self.jira_repository.get_board_id(
            self.settings.developer_board_project_key,
        )
        self.pm_board_id = self.jira_repository.get_board_id(
            self.settings.pm_project_key,
        )

    async def create_pm_board_task(
        self,
        feature: SynthPMFeatureEntity,
    ) -> Optional[str]:
        """Create a PM Board Jira task from a feature.

        Args:
            feature: Feature entity

        Returns:
            PM Board Jira issue key if successful, None otherwise
        """
        try:
            task_data = self.build_task_data_from_feature(
                feature,
                self.settings.pm_project_key,
                task_type="Task",
            )

            if feature.sprint:
                task_data.sprint_id = self.get_sprint_id("Active", self.pm_board_id)

            pm_board_issue = self.jira_repository.create_task(task_data)
            issue_url = self.jira_repository.get_issue_url(pm_board_issue)
            LOGGER.info(
                f"Created PM Board task {pm_board_issue.key} for feature: "
                f"{feature.task_title}: {issue_url}",
            )

            # Transition to appropriate status
            jira_status = SynthPMStatusService.determine_jira_status(feature)
            self.transition_issue_to_status(pm_board_issue.key, jira_status)

            return pm_board_issue.key

        except Exception as e:
            LOGGER.error(
                f"Error creating PM Board task for feature {feature.task_title}: {e}",
            )
            return None

    async def create_developer_board_task(
        self,
        feature: SynthPMFeatureEntity,
        sprint_info: SprintInfo,
        assignees: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Create a Developer Board Jira task from a feature.

        Args:
            feature: Feature entity
            sprint_info: Sprint information
            assignees: List of assignee usernames

        Returns:
            Developer Board Jira issue key if successful, None otherwise
        """
        try:
            if not feature.jira_issue_key:
                LOGGER.error(
                    "Cannot create developer board task without existing PM Board task",
                )
                return None

            # Determine task type based on assignees
            task_type = "Story" if assignees and len(assignees) > 1 else "Task"

            task_data = self.build_task_data_from_feature(
                feature,
                self.settings.developer_board_project_key,
                task_type=task_type,
                assignee=assignees[0] if assignees and len(assignees) == 1 else None,
            )

            # Handle sprint assignment
            sprint = await self._get_or_create_sprint_from_info(feature, sprint_info)
            if sprint and sprint.get("state") != "closed":
                task_data.sprint_id = sprint.get("id")
                task_data.sprint_name = sprint.get("name")

            # Adjust task data for stories vs tasks
            if task_type == "Story":
                task_data.labels = [
                    f"PM-{feature.jira_issue_key}",
                    feature.involved_people,
                ]
                task_data.description = self._build_story_description(
                    feature,
                    assignees,
                )
                task_data.story_points = None
            else:
                task_data.story_points = (
                    feature.total_hours / 8 if feature.total_hours else 0
                )

            developer_board_issue = self.jira_repository.create_task(task_data)
            issue_url = self.jira_repository.get_issue_url_by_key(
                developer_board_issue.key,
            )
            LOGGER.info(
                f"Created Developer Board task {issue_url} "
                f"for feature: {feature.task_title}",
            )

            # Create subtasks for stories
            if task_type == "Story" and assignees:
                await self._create_subtasks_for_assignees(
                    developer_board_issue.key,
                    assignees,
                    feature,
                )

            # Link to PM Board task
            self.link_issues(feature.jira_issue_key, developer_board_issue.key)

            return developer_board_issue.key

        except Exception as e:
            LOGGER.error(
                f"Error creating Developer Board task for feature "
                f"{feature.task_title}: {e}",
            )
            return None

    async def update_pm_board_task(self, feature: SynthPMFeatureEntity) -> bool:
        """Update an existing PM Board Jira task from a feature.

        Args:
            feature: Feature entity

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

            update_fields = self._build_update_fields_for_pm_task(feature, issue)

            if update_fields:
                update_fields["project"] = {"key": self.settings.pm_project_key}
                issue.update(fields=update_fields)
                LOGGER.info(f"Updated PM Board task {feature.jira_issue_key}")

            # Handle status transitions separately
            if feature.status:
                jira_status = SynthPMStatusService.determine_jira_status(feature)
                current_status = issue.fields.status.name
                if current_status.lower() != jira_status.lower():
                    self.transition_issue_to_status(issue.key, jira_status)

            return True

        except Exception as e:
            LOGGER.error(f"Error updating PM Board task {feature.jira_issue_key}: {e}")
            return False

    async def update_developer_board_task(
        self,
        feature: SynthPMFeatureEntity,
        assignees: Optional[List[str]] = None,
    ) -> bool:
        """Update an existing Developer Board Jira task from a feature.

        Args:
            feature: Feature entity
            assignees: List of assignee usernames

        Returns:
            True if successful, False otherwise
        """
        try:
            if not feature.developer_board_issue_key:
                LOGGER.warning(
                    f"No developer board issue key for feature: {feature.task_title}",
                )
                return False

            issue = self.jira_repository.get_issue(feature.developer_board_issue_key)
            if not issue:
                LOGGER.warning(
                    f"Developer board issue {feature.developer_board_issue_key} "
                    "not found",
                )
                return False

            update_fields = self._build_update_fields_for_developer_task(
                feature,
                issue,
                assignees,
            )

            if update_fields:
                issue.update(fields=update_fields)
                LOGGER.info(
                    f"Updated Developer Board task {feature.developer_board_issue_key} with {update_fields.keys()}",
                )

            # Handle assignee changes and task type conversions
            await self._handle_assignee_changes(feature, issue, assignees)

            # Update subtask deadlines if deadline changed
            await self._update_subtask_deadlines(issue.key, feature)

            return True

        except Exception as e:
            LOGGER.error(
                f"Error updating Developer Board task "
                f"{feature.developer_board_issue_key}: {e}",
            )
            return False

    def _build_story_description(
        self,
        feature: SynthPMFeatureEntity,
        assignees: List[str],
    ) -> str:
        """Build description for story-type tasks.

        Args:
            feature: Feature entity
            assignees: List of assignees

        Returns:
            Formatted description
        """
        return (
            f"🔗 *Linked to PM Board*: "
            f"{self.jira_repository.get_issue_url_by_key(feature.jira_issue_key)}\n\n"
            f"👥 *Assignees*: {', '.join(assignees) if assignees else 'Unassigned'}\n\n"
            f"📝 *Original Time*: {feature.total_hours}h\n\n"
            f"✍️ *Description*: {feature.description}"
        )

    def _build_update_fields_for_pm_task(
        self,
        feature: SynthPMFeatureEntity,
        issue,
    ) -> Dict:
        """Build update fields for PM Board task.

        Args:
            feature: Feature entity
            issue: Jira issue object

        Returns:
            Dictionary of fields to update
        """
        update_fields = {}

        # Update basic fields
        if feature.task_title and feature.task_title != issue.fields.summary:
            update_fields["summary"] = feature.task_title

        if feature.description and feature.description != issue.fields.description:
            update_fields["description"] = feature.description

        # Update priority
        if feature.priority:
            feature_priority = SynthPMStatusService.map_priority(feature.priority)
            if feature_priority != issue.fields.priority.name:
                update_fields["priority"] = {"name": feature_priority}

        # Add more field updates as needed...

        return update_fields

    def _build_update_fields_for_developer_task(
        self,
        feature: SynthPMFeatureEntity,
        issue,
        assignees: Optional[List[str]],
    ) -> Dict:
        """Build update fields for Developer Board task.

        Args:
            feature: Feature entity
            issue: Jira issue object
            assignees: List of assignees

        Returns:
            Dictionary of fields to update
        """
        update_fields = {}

        # Update basic fields
        if feature.task_title and feature.task_title != issue.fields.summary:
            update_fields["summary"] = feature.task_title

        # Handle priority updates
        if feature.priority:
            feature_priority = SynthPMStatusService.map_priority(feature.priority)
            if feature_priority.lower() != issue.fields.priority.name.lower():
                update_fields["priority"] = {"name": feature_priority}

        # Handle description updates
        if feature.description and feature.description != issue.fields.description:
            update_fields["description"] = feature.description

        # Handle fix versions (release/version updates)
        if feature.release is not None or feature.version is not None:
            current_versions = {field.name for field in issue.fields.fixVersions}
            new_versions = {feature.release, feature.version} - {None}
            if new_versions != current_versions:
                update_fields["fixVersions"] = [
                    {"name": version} for version in new_versions if version
                ]

        # Handle sprint updates
        if hasattr(issue.fields, self.jira_repository.jira_sprint_id):
            current_sprint = getattr(
                issue.fields,
                self.jira_repository.jira_sprint_id,
                None,
            )
            if feature.sprint and current_sprint != feature.sprint:
                # Get or create the sprint and update the field
                sprint_id = self._get_or_create_sprint(feature.sprint)
                if sprint_id:
                    update_fields[self.jira_repository.jira_sprint_id] = sprint_id
            elif feature.sprint is None and current_sprint is not None:
                # Remove from sprint
                update_fields[self.jira_repository.jira_sprint_id] = None

        # Handle component updates based on departments
        components = SynthPMComponentService.map_components(feature)
        current_components = [comp.name for comp in issue.fields.components]
        if set(current_components) != set(components):
            update_fields["components"] = [{"name": comp} for comp in components]

        # Handle due date updates
        if feature.deadline:
            feature_duedate = feature.deadline.strftime("%Y-%m-%d")
            if feature_duedate != issue.fields.duedate:
                update_fields["duedate"] = feature_duedate

        # Handle target start and end dates
        if hasattr(self.jira_repository, "jira_target_start_id"):
            current_target_start = getattr(
                issue.fields,
                self.jira_repository.jira_target_start_id,
                None,
            )
            if feature.deadline:  # Using deadline as target_end for now
                feature_target_end = feature.deadline.strftime("%Y-%m-%d")
                if hasattr(
                    self.jira_repository,
                    "jira_target_end_id",
                ) and feature_target_end != getattr(
                    issue.fields,
                    self.jira_repository.jira_target_end_id,
                    None,
                ):
                    update_fields[
                        self.jira_repository.jira_target_end_id
                    ] = feature_target_end

        # Handle time estimates for tasks
        if feature.total_hours and issue.fields.issuetype.name == "Task":
            # Safely get the original estimate using getattr, handle None timetracking
            timetracking = getattr(issue.fields, "timetracking", None)
            original_estimate_seconds = (
                getattr(
                    timetracking,
                    "originalEstimateSeconds",
                    0,
                )
                if timetracking
                else 0
            )
            original_estimate_hours = (
                original_estimate_seconds / 3600 if original_estimate_seconds else 0
            )
            if feature.total_hours != original_estimate_hours:
                # IMPORTANT: Get logged time to preserve worklog data
                # This ensures we don't lose any existing work hours when updating estimates
                logged_time_seconds = (
                    self.jira_repository.get_issue_spent_time_in_seconds(issue.key)
                    if hasattr(self.jira_repository, "get_issue_spent_time_in_seconds")
                    else 0
                )
                logged_time_hours = logged_time_seconds / 3600

                # Calculate remaining estimate while preserving logged work
                # If logged time exceeds new estimate, remaining should be 0
                remaining_estimate_hours = max(
                    0,
                    feature.total_hours - logged_time_hours,
                )

                # Warn if logged time exceeds new estimate
                if logged_time_hours > feature.total_hours:
                    LOGGER.warning(
                        f"Logged time ({logged_time_hours}h) exceeds new estimate "
                        f"({feature.total_hours}h) for {issue.key}. "
                        "Remaining estimate will be set to 0.",
                    )

                update_fields["timetracking"] = {
                    "originalEstimate": f"{feature.total_hours}h",
                    "remainingEstimate": f"{remaining_estimate_hours}h",
                }

                LOGGER.debug(
                    f"Updating time tracking for {issue.key}: "
                    f"original={feature.total_hours}h, "
                    f"remaining={remaining_estimate_hours}h, "
                    f"logged={logged_time_hours}h",
                )

        # Handle involved_people labels
        if feature.involved_people:
            current_labels = [label for label in issue.fields.labels]
            involved_label = feature.involved_people.replace(" ", "-")

            # Check if involved_people label needs updating
            needs_label_update = False
            new_labels = current_labels[:]

            # Remove any existing involved_people labels and add the new one
            for i, label in enumerate(current_labels):
                if any(name in label for name in feature.involved_people.split(" ")):
                    new_labels.pop(i)
                    needs_label_update = True
                    break

            if involved_label not in new_labels:
                new_labels.append(involved_label)
                needs_label_update = True

            if needs_label_update:
                update_fields["labels"] = new_labels

        return update_fields

    async def _handle_assignee_changes(
        self,
        feature: SynthPMFeatureEntity,
        issue,
        assignees: Optional[List[str]],
    ):
        """Handle assignee changes and task type conversions.

        Args:
            feature: Feature entity
            issue: Jira issue object
            assignees: List of assignees
        """
        if not assignees:
            return

        current_type = issue.fields.issuetype.name
        target_type = "Story" if len(assignees) > 1 else "Task"

        if current_type != target_type:
            # Handle task type conversion
            issue.update(fields={"issuetype": {"name": target_type}})
            LOGGER.info(f"Converted {issue.key} from {current_type} to {target_type}")

        if target_type == "Task" and len(assignees) == 1:
            # Simple task assignment
            current_assignee = (
                issue.fields.assignee.name if issue.fields.assignee else None
            )
            if current_assignee != assignees[0]:
                issue.update(fields={"assignee": {"name": assignees[0]}})

        elif target_type == "Story":
            # Handle story with subtasks
            await self._update_assignees_and_subtasks(issue.key, assignees, feature)

    async def _get_or_create_sprint_from_info(
        self,
        feature: SynthPMFeatureEntity,
        sprint_info: SprintInfo,
    ) -> Optional[Dict]:
        """Get or create a sprint from sprint info.

        Args:
            feature: Feature entity
            sprint_info: Sprint information

        Returns:
            Sprint dictionary with state, id, name if successful
        """
        sprint_name = None
        try:
            sprint_name = sprint_info.sprint_id if sprint_info else feature.sprint
            if not sprint_name:
                LOGGER.debug(
                    f"No sprint name available - sprint_info: {sprint_info}, "
                    f"feature.sprint: {getattr(feature, 'sprint', 'not set')}",
                )
                return None

            LOGGER.debug(f"Attempting to get or create sprint: {sprint_name}")

            # First try to find existing sprint
            board_id = getattr(
                self.jira_repository.settings,
                "JIRA_BOARD_ID",
                None,
            )

            if not board_id:
                LOGGER.warning("No JIRA_BOARD_ID found in settings")
                return None

            LOGGER.debug(f"Using board_id: {board_id}")

            if board_id:
                sprints = self.jira_repository.jira.sprints(board_id, extended=True)
                for sprint in sprints:
                    if sprint.name == sprint_name:
                        LOGGER.debug(
                            f"Found existing sprint: {sprint.name} (ID: {sprint.id})",
                        )
                        return {
                            "id": sprint.id,
                            "name": sprint.name,
                            "state": getattr(sprint, "state", "active"),
                        }

                LOGGER.debug(f"Sprint {sprint_name} not found, creating new one")
                # If not found, create new sprint
                new_sprint = self.jira_repository.jira.create_sprint(
                    name=sprint_name,
                    board_id=board_id,
                    startDate=None,
                    endDate=None,
                )
                LOGGER.info(
                    f"Created new sprint: {new_sprint.name} (ID: {new_sprint.id})",
                )
                return {
                    "id": new_sprint.id,
                    "name": new_sprint.name,
                    "state": "active",
                }

        except Exception as e:
            sprint_identifier = sprint_name or "unknown sprint"
            LOGGER.error(f"Failed to get or create sprint {sprint_identifier}: {e}")
            # Add more detailed error information
            LOGGER.error(
                f"Sprint info: {sprint_info}, Feature sprint: {getattr(feature, 'sprint', 'not set')}",
            )

        return None

    def _get_or_create_sprint(self, sprint_name: str) -> str:
        """Get or create a sprint by name.

        Args:
            sprint_name: Name of the sprint

        Returns:
            Sprint ID string
        """
        try:
            # First try to find existing sprint
            board_id = getattr(
                self.jira_repository.settings,
                "JIRA_BOARD_ID",
                None,
            )
            if board_id:
                sprints = self.jira_repository.jira.sprints(board_id, extended=True)
                for sprint in sprints:
                    if sprint.name == sprint_name:
                        return str(sprint.id)

            # If not found, create new sprint
            if board_id:
                new_sprint = self.jira_repository.jira.create_sprint(
                    name=sprint_name,
                    board_id=board_id,
                    startDate=None,
                    endDate=None,
                )
                return str(new_sprint.id)

        except Exception as e:
            LOGGER.warning(f"Failed to get or create sprint {sprint_name}: {e}")

        return ""

    async def _create_subtasks_for_assignees(
        self,
        parent_issue_key: str,
        assignees: List[str],
        feature: SynthPMFeatureEntity,
    ) -> List[str]:
        """Create subtasks for each assignee.

        Args:
            parent_issue_key: Parent issue key
            assignees: List of assignee usernames
            feature: Feature entity

        Returns:
            List of created subtask keys
        """
        created_subtask_keys = []

        try:
            parent_issue = self.jira_repository.jira.issue(parent_issue_key)
            estimated_hours = (
                feature.total_hours / len(assignees) if feature.total_hours else 0
            )

            for assignee in assignees:
                try:
                    task_title = feature.task_title or parent_issue.fields.summary
                    subtask_fields = {
                        "project": {"key": parent_issue.fields.project.key},
                        "summary": f"{task_title} - {assignee}",
                        "issuetype": {"name": "Sub-task"},
                        "parent": {"key": parent_issue_key},
                        "assignee": {"name": assignee},
                    }

                    # Add description from feature
                    if feature.description:
                        subtask_fields["description"] = feature.description

                    # Add time tracking if provided
                    if estimated_hours > 0:
                        subtask_fields["timetracking"] = {
                            "originalEstimate": f"{estimated_hours}h",
                            "remainingEstimate": f"{estimated_hours}h",
                        }

                    # Create the subtask
                    subtask = self.jira_repository.jira.create_issue(
                        fields=subtask_fields,
                    )
                    created_subtask_keys.append(subtask.key)
                    LOGGER.info(f"Created subtask {subtask.key} for {assignee}")

                except Exception as e:
                    LOGGER.error(f"Failed to create subtask for {assignee}: {e}")

        except Exception as e:
            LOGGER.error(f"Failed to create subtasks for {parent_issue_key}: {e}")

        return created_subtask_keys

    async def _update_assignees_and_subtasks(
        self,
        issue_key: str,
        assignees: List[str],
        feature: SynthPMFeatureEntity,
    ):
        """Update assignees and manage subtasks.

        Args:
            issue_key: Issue key
            assignees: List of assignee usernames
            feature: Feature entity
        """
        try:
            issue = self.jira_repository.jira.issue(issue_key, expand="subtasks")

            # Get current subtasks
            current_subtasks = getattr(issue.fields, "subtasks", [])
            current_assignees = set()

            for subtask in current_subtasks:
                subtask_obj = self.jira_repository.jira.issue(subtask.key)
                if subtask_obj.fields.assignee:
                    current_assignees.add(subtask_obj.fields.assignee.name)

            new_assignees = set(assignees)

            # If assignees haven't changed, update existing subtasks
            if current_assignees == new_assignees and current_subtasks:
                await self._update_subtask_deadlines(issue_key, feature)
                return

            # Remove subtasks for assignees no longer needed
            assignees_to_remove = current_assignees - new_assignees
            for subtask in current_subtasks:
                subtask_obj = self.jira_repository.jira.issue(subtask.key)
                assignee_in_remove = (
                    subtask_obj.fields.assignee
                    and subtask_obj.fields.assignee.name in assignees_to_remove
                )
                if assignee_in_remove:
                    try:
                        subtask_obj.delete()
                        LOGGER.info(f"Deleted subtask {subtask.key}")
                    except Exception as e:
                        LOGGER.error(f"Failed to delete subtask {subtask.key}: {e}")

            # Create subtasks for new assignees
            assignees_to_add = new_assignees - current_assignees
            if assignees_to_add:
                await self._create_subtasks_for_assignees(
                    issue_key,
                    list(assignees_to_add),
                    feature,
                )

            # Update main issue assignee if single assignee
            if len(assignees) == 1:
                main_assignee = assignees[0]
                current_assignee = (
                    issue.fields.assignee.name if issue.fields.assignee else None
                )
                if current_assignee != main_assignee:
                    issue.update(fields={"assignee": {"name": main_assignee}})
                    LOGGER.info(f"Updated main assignee to {main_assignee}")
            else:
                # For multiple assignees, clear main assignee
                if issue.fields.assignee:
                    issue.update(fields={"assignee": None})
                    LOGGER.info("Cleared main assignee for multi-assignee story")

        except Exception as e:
            LOGGER.error(
                f"Failed to update assignees and subtasks for {issue_key}: {e}",
            )

    async def _update_subtask_deadlines(
        self,
        issue_key: str,
        feature: SynthPMFeatureEntity,
    ):
        """Update deadlines and related fields for all subtasks of the given issue.

        IMPORTANT: This method preserves existing worklogs by:
        1. Reading current logged time before updating time estimates
        2. Calculating remaining estimate as: max(0, new_estimate - logged_time)
        3. Only updating fields that actually need changes
        4. Using JIRA's standard update API which doesn't affect worklogs

        Args:
            issue_key: Parent issue key
            feature: Feature entity containing deadline information
        """
        try:
            issue = self.jira_repository.jira.issue(issue_key, expand="subtasks")
            current_subtasks = getattr(issue.fields, "subtasks", [])

            for subtask in current_subtasks:
                try:
                    subtask_obj = self.jira_repository.jira.issue(subtask.key)
                    update_fields = {}

                    # Update deadline (due date)
                    if feature.deadline:
                        feature_duedate = feature.deadline.strftime("%Y-%m-%d")
                        if subtask_obj.fields.duedate != feature_duedate:
                            update_fields["duedate"] = feature_duedate

                    # Update target dates if available
                    if hasattr(self.jira_repository, "jira_target_start_id"):
                        target_start_field = self.jira_repository.jira_target_start_id
                        current_target_start = getattr(
                            subtask_obj.fields,
                            target_start_field,
                            None,
                        )
                        # Set target_start from deadline for now (can be enhanced)
                        if feature.deadline:
                            feature_target_start = feature.deadline.strftime("%Y-%m-%d")
                            if current_target_start != feature_target_start:
                                update_fields[target_start_field] = feature_target_start

                    if hasattr(self.jira_repository, "jira_target_end_id"):
                        target_end_field = self.jira_repository.jira_target_end_id
                        current_target_end = getattr(
                            subtask_obj.fields,
                            target_end_field,
                            None,
                        )
                        if feature.deadline:
                            feature_target_end = feature.deadline.strftime("%Y-%m-%d")
                            if current_target_end != feature_target_end:
                                update_fields[target_end_field] = feature_target_end

                    # Update summary to match parent
                    if (
                        feature.task_title
                        and subtask_obj.fields.summary != feature.task_title
                    ):
                        update_fields["summary"] = feature.task_title

                    # Update time estimates if needed
                    if feature.total_hours and subtask_obj.fields.assignee:
                        assignee = subtask_obj.fields.assignee.name
                        # Calculate story points per assignee
                        # This is a simplified version - could be enhanced with component mapping
                        timetracking = getattr(subtask_obj.fields, "timetracking", None)
                        current_estimate_seconds = (
                            getattr(timetracking, "originalEstimateSeconds", 0)
                            if timetracking
                            else 0
                        )
                        current_estimate_hours = current_estimate_seconds / 3600

                        # For now, divide total hours equally among assignees
                        # This could be enhanced with proper story point calculation
                        parent_issue = self.jira_repository.jira.issue(
                            issue_key,
                            expand="subtasks",
                        )
                        total_assignees = len(
                            getattr(parent_issue.fields, "subtasks", []),
                        )
                        if total_assignees > 0:
                            assignee_hours = feature.total_hours / total_assignees
                            if abs(current_estimate_hours - assignee_hours) > 0.01:
                                # IMPORTANT: Get logged time to preserve worklog data
                                # This ensures we don't lose any existing work hours
                                logged_time_seconds = (
                                    self.jira_repository.get_issue_spent_time_in_seconds(
                                        subtask.key,
                                    )
                                    if hasattr(
                                        self.jira_repository,
                                        "get_issue_spent_time_in_seconds",
                                    )
                                    else 0
                                )
                                logged_time_hours = logged_time_seconds / 3600

                                # Calculate remaining estimate while preserving logged work
                                # If logged time exceeds new estimate, remaining should be 0
                                remaining_hours = max(
                                    0,
                                    assignee_hours - logged_time_hours,
                                )

                                # Warn if logged time exceeds new estimate
                                if logged_time_hours > assignee_hours:
                                    LOGGER.warning(
                                        f"Logged time ({logged_time_hours}h) exceeds new estimate "
                                        f"({assignee_hours}h) for subtask {subtask.key}. "
                                        "Remaining estimate will be set to 0.",
                                    )

                                # Only update time tracking if we have valid estimates
                                if assignee_hours > 0:
                                    update_fields["timetracking"] = {
                                        "originalEstimate": f"{assignee_hours}h",
                                        "remainingEstimate": f"{remaining_hours}h",
                                    }
                                    LOGGER.debug(
                                        f"Updating time tracking for {subtask.key}: "
                                        f"original={assignee_hours}h, "
                                        f"remaining={remaining_hours}h, "
                                        f"logged={logged_time_hours}h",
                                    )

                    # Apply updates if any
                    if update_fields:
                        subtask_obj.update(fields=update_fields)
                        LOGGER.info(
                            f"Updated subtask {subtask.key} with fields: {list(update_fields.keys())}",
                        )

                except Exception as e:
                    LOGGER.error(f"Failed to update subtask {subtask.key}: {e}")

        except Exception as e:
            LOGGER.error(f"Error updating subtask deadlines for {issue_key}: {e}")
