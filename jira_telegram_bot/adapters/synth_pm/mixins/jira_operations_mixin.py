"""Mixin for Jira operations in SynthPM."""
from __future__ import annotations

from typing import Optional
from typing import Tuple

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.entities.synth_pm.services import SynthPMComponentService
from jira_telegram_bot.entities.synth_pm.services import SynthPMDateService
from jira_telegram_bot.entities.synth_pm.services import SynthPMStatusService
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class JiraOperationsMixin:
    """Mixin for Jira operations."""

    jira_repository: TaskManagerRepositoryInterface
    settings: SynthPMSettings

    def create_epic_if_not_exists(
        self,
        epic_name: str,
        project_key: str,
    ) -> Tuple[bool, Optional[str]]:
        """Create epic if it doesn't exist.

        Args:
            epic_name: Name of the epic
            project_key: Jira project key

        Returns:
            Tuple of (created, epic_key)
        """
        try:
            # Check if epic already exists
            existing_epic = self.jira_repository.search_issues(
                f'project = "{project_key}" AND issuetype = Epic AND summary ~ "{epic_name}"',
            )

            if existing_epic:
                return False, existing_epic[0].key

            # Create new epic
            epic_data = TaskData(
                project_key=project_key,
                summary=epic_name,
                description=f"Epic for {epic_name}",
                task_type="Epic",
                priority="Medium",
            )

            epic_issue = self.jira_repository.create_task(epic_data)
            LOGGER.info(f"Created epic {epic_issue.key}: {epic_name}")
            return True, epic_issue.key

        except Exception as e:
            LOGGER.error(f"Error creating epic {epic_name}: {e}")
            return False, None

    def get_sprint_id(self, sprint_name: str, board_id: int) -> Optional[int]:
        """Get sprint ID by name and board.

        Args:
            sprint_name: Name of the sprint
            board_id: Board ID

        Returns:
            Sprint ID if found, None otherwise
        """
        try:
            sprints = self.jira_repository.get_board_sprints(board_id)
            for sprint in sprints:
                if sprint_name.lower() in sprint.get("name", "").lower():
                    return sprint.get("id")
            return None
        except Exception as e:
            LOGGER.error(f"Error getting sprint ID for {sprint_name}: {e}")
            return None

    def create_release_if_not_exist(
        self,
        feature: SynthPMFeatureEntity,
        task_data: TaskData,
        project_key: str,
    ) -> None:
        """Create releases if they don't exist and add to task data.

        Args:
            feature: SynthPM feature entity
            task_data: Task data to update with releases
            project_key: Jira project key
        """
        releases = []

        if feature.release:
            if not self.jira_repository.release_exist(project_key, feature.release):
                self.jira_repository.create_release(
                    project_key=project_key,
                    name=feature.release,
                )
            releases.append(feature.release)

        if feature.version:
            if not self.jira_repository.release_exist(project_key, feature.version):
                self.jira_repository.create_release(
                    project_key=project_key,
                    name=feature.version,
                )
            releases.append(feature.version)

        if releases:
            task_data.releases = releases

    def transition_issue_to_status(self, issue_key: str, target_status: str) -> bool:
        """Transition Jira issue to target status.

        Args:
            issue_key: Jira issue key
            target_status: Target status name

        Returns:
            True if successful, False otherwise
        """
        try:
            issue = self.jira_repository.get_issue(issue_key)
            if not issue:
                LOGGER.error(f"Issue {issue_key} not found")
                return False

            current_status = issue.fields.status.name
            if current_status.lower() == target_status.lower():
                return True

            # Get available transitions
            transitions = self.jira_repository.get_transitions(issue_key)
            target_transition = None

            for transition in transitions:
                if transition["to"]["name"].lower() == target_status.lower():
                    target_transition = transition
                    break

            if not target_transition:
                LOGGER.warning(
                    f"No transition available from {current_status} to {target_status} for {issue_key}",
                )
                return False

            # Perform transition
            self.jira_repository.transition_issue(issue_key, target_transition["id"])
            LOGGER.info(
                f"Transitioned {issue_key} from {current_status} to {target_status}",
            )
            return True

        except Exception as e:
            LOGGER.error(f"Error transitioning {issue_key} to {target_status}: {e}")
            return False

    def link_issues(
        self,
        outward_issue: str,
        inward_issue: str,
        link_type: str = "Relates",
    ) -> bool:
        """Link two Jira issues.

        Args:
            outward_issue: Outward issue key
            inward_issue: Inward issue key
            link_type: Type of link

        Returns:
            True if successful, False otherwise
        """
        try:
            self.jira_repository.create_issue_link(
                link_type,
                outward_issue,
                inward_issue,
            )
            LOGGER.info(f"Linked {outward_issue} to {inward_issue} with {link_type}")
            return True
        except Exception as e:
            LOGGER.error(f"Error linking {outward_issue} to {inward_issue}: {e}")
            return False

    def build_task_data_from_feature(
        self,
        feature: SynthPMFeatureEntity,
        project_key: str,
        task_type: str = "Task",
        assignee: Optional[str] = None,
    ) -> TaskData:
        """Build TaskData object from SynthPM feature.

        Args:
            feature: SynthPM feature entity
            project_key: Jira project key
            task_type: Type of Jira task
            assignee: Assignee username

        Returns:
            TaskData object
        """
        feature_dates = SynthPMDateService.extract_dates_from_feature(feature)
        components = SynthPMComponentService.map_components(feature)
        priority = SynthPMStatusService.map_priority(feature.priority or "Medium")

        labels = []
        if feature.involved_people:
            labels.append(feature.involved_people)
        labels.append(f"PM-{feature.row_number}")

        epic_link = None
        if feature.epic and feature.epic.strip() and feature.epic != "Select":
            _, epic_key = self.create_epic_if_not_exists(feature.epic, project_key)
            epic_link = epic_key

        task_data = TaskData(
            project_key=project_key,
            summary=feature.task_title,
            description=feature.description or "",
            task_type=task_type,
            priority=priority,
            epic_link=epic_link,
            labels=labels,
            components=components,
            story_points=feature.total_hours / 8 if feature.total_hours else 0,
            assignee=assignee,
            due_date=feature_dates.get("due_date"),
            target_start=feature_dates.get("target_start"),
            target_end=feature_dates.get("target_end"),
        )

        self.create_release_if_not_exist(feature, task_data, project_key)
        return task_data
