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
            LOGGER.info(
                f"Created PM Board task {pm_board_issue.key} for feature: "
                f"{feature.task_title}: {self.jira_repository.get_issue_url(pm_board_issue)}",
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
            sprint = await self._get_or_create_sprint(feature, sprint_info)
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
            LOGGER.info(
                f"Created Developer Board task {self.jira_repository.get_issue_url_by_key(developer_board_issue.key)} "
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
                f"Error creating Developer Board task for feature {feature.task_title}: {e}",
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
                    f"Developer board issue {feature.developer_board_issue_key} not found",
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
                    f"Updated Developer Board task {feature.developer_board_issue_key}",
                )

            # Handle assignee changes and task type conversions
            await self._handle_assignee_changes(feature, issue, assignees)

            return True

        except Exception as e:
            LOGGER.error(
                f"Error updating Developer Board task {feature.developer_board_issue_key}: {e}",
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
            f"🔗 *Linked to PM Board*: {self.jira_repository.get_issue_url_by_key(feature.jira_issue_key)}\n\n"
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

        # Add more field updates as needed...

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

    async def _get_or_create_sprint(
        self,
        feature: SynthPMFeatureEntity,
        sprint_info: SprintInfo,
    ):
        """Get existing sprint or create new one.

        Args:
            feature: Feature entity
            sprint_info: Sprint information

        Returns:
            Sprint dictionary or None
        """
        # Implementation for getting or creating sprints
        # This would involve checking feature.sprint_list and creating sprints as needed
        pass

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
        # Implementation for creating subtasks
        pass

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
        # Implementation for updating assignees and subtasks
        pass
