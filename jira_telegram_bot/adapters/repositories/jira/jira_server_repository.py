from __future__ import annotations

import json
import os
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue
from jira import JIRA

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.release import Release
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class JiraServerRepository(TaskManagerRepositoryInterface):
    def __init__(self, settings: JiraConnectionSettings):
        self.settings = settings
        if self.settings.password:
            # Use basic authentication if password is provided
            self.jira = JIRA(
                server=f"{self.settings.domain.scheme}://{self.settings.domain.host}",
                basic_auth=(self.settings.username, self.settings.password),
                # options={"verify": False}
            )
        else:
            # Use API token authentication if password is empty
            self.jira = JIRA(
                server=f"{self.settings.domain.scheme}://{self.settings.domain.host}",
                token_auth=self.settings.api_token,
            )
        self.cache = {}
        self.jira_story_point_id = "customfield_10106"
        self.jira_original_estimate_id = "customfield_10111"
        self.jira_sprint_id = "customfield_10104"
        self.jira_epic_link_id = "customfield_10100"
        self.jira_epic_name_id = "customfield_10102"

    def _get_from_cache(self, cache_key, max_age_seconds):
        entry = self.cache.get(cache_key)
        if entry:
            timestamp, result = entry
            if time.time() - timestamp < max_age_seconds:
                return result
        return None

    def _set_cache(self, cache_key, result):
        self.cache[cache_key] = (time.time(), result)

    def get_projects(self):
        cache_key = ("get_projects", None)
        result = self._get_from_cache(cache_key, 48 * 3600)
        if result is not None:
            return result

        result = self.jira.projects()
        self._set_cache(cache_key, result)
        return result

    def get_project_components(self, project_key):
        return self.jira.project_components(project_key)

    def get_epics(self, project_key: str):
        cache_key = ("get_epics", project_key)
        result = self._get_from_cache(cache_key, 72 * 3600)
        if result is not None:
            return result

        result = self.jira.search_issues(
            f'project="{project_key}" AND issuetype=Epic AND status in ("To Do", "In Progress")',
        )
        self._set_cache(cache_key, result)
        return result

    def get_board_id(self, project_key: str) -> Optional[int]:
        cache_key = ("get_board_id", project_key)
        result = self._get_from_cache(cache_key, 48 * 3600)
        if result is not None:
            return result

        boards = self.jira.boards()
        for board in boards:
            if project_key in board.name:
                self.board_type = board.type
                self._set_cache(cache_key, board.id)
                return board.id
        return None

    def get_sprints(self, board_id, get_from_cache: bool = True):
        cache_key = ("get_sprints", board_id)
        if get_from_cache:
            result = self._get_from_cache(cache_key, 8 * 3600)  # Cache for 8 hours
        else:
            result = None
        if result is not None:
            return result

        if self.board_type == "scrum":
            result = self.jira.sprints(board_id=board_id)
        else:
            result = []
        self._set_cache(cache_key, result)
        return result

    def get_project_versions(self, project_key):
        cache_key = ("get_project_versions", project_key)
        result = self._get_from_cache(cache_key, 2 * 86400)  # Cache for 2 days
        if result is not None:
            return result

        result = self.jira.project_versions(project_key)
        self._set_cache(cache_key, result)
        return result

    def get_issue_types_for_project(self, project_key):
        cache_key = ("issue_types_for_project", project_key)
        result = self._get_from_cache(cache_key, 4 * 3600)  # Cache for 4 hours
        if result is not None:
            return result

        result = [
            issue_type.name
            for issue_type in self.jira.issue_types_for_project(project_key)
        ]
        self._set_cache(cache_key, result)
        return result

    def get_priorities(self):
        cache_key = "priorities"
        result = self._get_from_cache(cache_key, 1200 * 3600)
        if result is not None:
            return result

        result = self.jira.priorities()
        self._set_cache(cache_key, result)
        return result

    def get_assignees(self, project_key: str) -> List[str]:
        try:
            cache_key = ("get_assignees", project_key)
            result = self._get_from_cache(cache_key, 2 * 3600)  # Cache for 2 hours
            if result is not None:
                return result

            assignees = set()
            recent_issues = self.jira.search_issues(
                f"project = {project_key} AND createdDate > startOfMonth(-1)",
            )
            for issue in recent_issues:
                if issue.fields.assignee:
                    assignees.add(issue.fields.assignee.name)

            assignee_list = sorted(assignees) if assignees else []
            self._set_cache(cache_key, assignee_list)
            return assignee_list
        except Exception as e:
            LOGGER.error(f"Error fetching assignees for project {project_key}: {e}")
            return []

    def search_users(self, username: str) -> List[str]:
        cache_key = ("search_users", username)
        result = self._get_from_cache(cache_key, 1 * 3600)  # Cache for 1 hour
        if result is not None:
            return result

        users = self.jira.search_users(username, maxResults=50)
        user_list = [user.name for user in users]
        self._set_cache(cache_key, user_list)
        return user_list

    def search_for_issues(self, query: str, max_results: int = 1000) -> List[Issue]:
        all_issues = []
        block_size = 100  # You can adjust the block size as needed.
        block_num = 0
        while True:
            start_idx = block_num * block_size
            issues_block = self.jira.search_issues(
                query,
                startAt=start_idx,
                maxResults=block_size,
            )
            all_issues.extend(issues_block)
            if len(issues_block) < block_size:
                break
            block_num += 1
        return all_issues

    def get_stories_by_epic(self, epic_key: str, project_key: str) -> List[Issue]:
        query = (
            f'issue in linkedIssues("{epic_key}") OR '
            f'"Epic Link" = {epic_key} AND '
            f'project = "{project_key}" AND issuetype = Story'
        )
        return self.search_for_issues(query)

    def get_stories_by_project(
        self,
        project_key: str,
        epic_link: str = None,
        status: str = None,
        filters: str = None,
    ) -> List[Issue]:
        query = f'project = "{project_key}" AND issuetype = Story'
        if status:
            query += f" AND status in ({status})"
        if epic_link:
            query += f' AND "Epic Link" = {epic_link}'
        if filters:
            query += f" AND {filters}"
        return self.search_for_issues(query)

    def build_issue_fields(self, task_data: TaskData) -> dict:
        issue_fields = {
            "project": {"key": task_data.project_key},
            "summary": task_data.summary,
            "description": task_data.description or "No Description Provided",
            "issuetype": {"name": task_data.task_type or "Task"},
        }

        if task_data.components:
            issue_fields["components"] = [
                {"name": component} for component in task_data.components
            ]  # TODO: components / component
        if task_data.story_points is not None:
            issue_fields["timetracking"] = {
                "originalEstimate": f"{int(task_data.story_points * 8)}h",
                "remainingEstimate": f"{int(task_data.story_points * 8)}h",
            }
        if task_data.sprint_id:
            issue_fields[self.jira_sprint_id] = task_data.sprint_id
        if task_data.epic_link:
            issue_fields[self.jira_epic_link_id] = task_data.epic_link
        if task_data.releases:
            issue_fields["fixVersions"] = [
                {"name": release} for release in task_data.releases
            ]
        if task_data.release:
            issue_fields["fixVersions"] = {"name": task_data.release}
        if task_data.assignee:
            issue_fields["assignee"] = {"name": task_data.assignee}
        if task_data.priority:
            issue_fields["priority"] = {"name": task_data.priority}

        if task_data.due_date:
            issue_fields["duedate"] = task_data.due_date

        if task_data.labels:
            issue_fields["labels"] = [
                label.replace(" ", "-") for label in task_data.labels
            ]

        # FIXME: task_type must be literal
        if task_data.task_type == "Sub-task":
            issue_fields["parent"] = {"key": task_data.parent_issue_key}
            if issue_fields.get(self.jira_sprint_id):
                del issue_fields[self.jira_sprint_id]

        if task_data.task_type == "Epic":
            # For Epics, we need to set the epic name field
            issue_fields[self.jira_epic_name_id] = task_data.summary

        return issue_fields

    def build_task_data_from_issue(self, issue: Issue) -> TaskData:
        return TaskData(
            project_key=issue.fields.project.key,
            summary=issue.fields.summary,
            description=issue.fields.description,
            component=(
                issue.fields.components[0].name if issue.fields.components else None
            ),
            components=[
                component.name
                for component in issue.fields.components
                if issue.fields.components
            ],
            task_type=getattr(issue.fields.issuetype, "name", None),
            story_points=getattr(issue.fields, self.jira_story_point_id, None),
            sprint_name=None,
            epic_link=getattr(issue.fields, self.jira_epic_link_id, None),
            release=(
                issue.fields.fixVersions[0].name if issue.fields.fixVersions else None
            ),
            assignee=getattr(issue.fields.assignee, "displayName", None),
            priority=getattr(issue.fields.priority, "name", None),
        )

    def handle_attachments(self, issue: Issue, attachments: Dict[str, List]):
        for _, files in attachments.items():
            for filename, file_buffer in files:
                self.add_attachment(
                    issue=issue,
                    attachment=file_buffer,
                    filename=filename,
                )
        LOGGER.info("Attachments attached to Jira issue")

    def create_issue(self, fields):
        return self.jira.create_issue(fields=fields)

    def add_attachment(self, issue, attachment, filename):
        self.jira.add_attachment(issue=issue, attachment=attachment, filename=filename)

    def create_task(self, task_data: TaskData) -> Issue:
        issue_fields = self.build_issue_fields(task_data)
        LOGGER.debug(f"Issue fields = {issue_fields}")
        new_issue = self.create_issue(issue_fields)
        self.handle_attachments(new_issue, task_data.attachments)
        return new_issue

    def add_comment(self, issue_key: str, comment: str):
        """
        Add a comment to an existing Jira issue.
        """
        self.jira.add_comment(issue_key, comment)

    def create_task_data_from_jira_issue(self, issue) -> TaskData:
        if self.board_type == "kanban":
            sprint_name = "kanban"
        else:
            last_sprint_of_task = (
                getattr(issue.fields, self.jira_sprint_id)[-1]
                if getattr(issue.fields, self.jira_sprint_id)
                else None
            )
            sprint_name = None
            if not last_sprint_of_task:
                name_position = last_sprint_of_task.find("name=")
                sprint_name = (
                    last_sprint_of_task[name_position:].split(",")[0].strip("name=")
                )
        return TaskData(
            project_key=getattr(issue.fields.project, "key", None),
            summary=issue.fields.summary,
            description=issue.fields.description,
            component=(
                issue.fields.components[0].name if issue.fields.components else None
            ),
            components=[
                component.name
                for component in issue.fields.components
                if issue.fields.components
            ],
            task_type=getattr(issue.fields.issuetype, "name", None),
            story_points=getattr(issue.fields, self.jira_story_point_id, None),
            sprint_name=sprint_name,
            epic_link=getattr(issue.fields, self.jira_epic_link_id, None),
            release=(
                issue.fields.fixVersions[0].name if issue.fields.fixVersions else None
            ),
            assignee=getattr(issue.fields.assignee, "displayName", None),
            priority=getattr(issue.fields.priority, "name", None),
        )

    def get_labels(self, project_key: str) -> List[str]:
        try:
            filepath = os.path.join(
                DEFAULT_PATH,
                "jira_telegram_bot/settings/project_labels.json",
            )
            labels = set()
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    data = json.load(f)
                    if project_key in data:
                        labels.update(data[project_key])
            if not labels:
                issues = self.jira.search_issues(
                    f'project = "{project_key}"',
                    maxResults=1000,
                )
                for issue in issues:
                    if issue.fields.labels:
                        labels.update(issue.fields.labels)

            label_list = sorted(list(labels))
            return label_list
        except Exception as e:
            LOGGER.error(f"Error fetching labels for project {project_key}: {e}")
            return []

    def set_labels(self, project_key: str, labels: List[str]) -> bool:
        try:
            filepath = os.path.join(
                DEFAULT_PATH,
                "jira_telegram_bot/settings/project_labels.json",
            )
            data = {}
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    data = json.load(f)

            data[project_key] = labels

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            LOGGER.error(f"Error saving labels for project {project_key}: {e}")
            return False

    def transition_task(self, issue_key: str, status: str) -> None:
        """
        Transition a task to a new status.
        """
        transitions = self.jira.transitions(issue_key)
        for t in transitions:
            if t["name"].lower() == status.lower():
                self.jira.transition_issue(issue_key, t["id"])
                break

    def assign_issue(
        self,
        issue_key: str,
        assignee: str,
    ) -> None:
        """
        Assign an issue to a user.
        """
        self.jira.assign_issue(issue_key, assignee)

    def update_issue(
        self,
        issue_key: str,
        task_data: TaskData,
    ) -> None:
        """
        Update an existing issue with new fields.
        """
        fields = self.build_issue_fields(task_data)
        issue = self.jira.issue(issue_key)
        issue.update(fields=fields)
        LOGGER.info(f"Updated issue {issue_key} with fields: {fields}")

    def update_issue_from_fields(
        self,
        issue_key: str,
        fields: dict,
    ) -> None:
        """
        Update an existing issue with new fields.
        """
        issue = self.jira.issue(issue_key)
        issue.update(fields=fields)
        LOGGER.info(
            f"Updated issue {issue_key} with fields: {fields}",
        )

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """
        Get a Jira issue by its key.
        """
        try:
            issue = self.jira.issue(issue_key)
            return issue
        except Exception as e:
            LOGGER.error(f"Error fetching issue {issue_key}: {e}")
            return None

    def is_user_jira_admin(self, username: str) -> bool:
        """
        Check if a user has Jira administrator privileges.
        """
        try:
            groups = self.jira.groups_for_user(username)
            admin_groups = [
                "jira-administrators",
                "jira-software-users",
                "administrators",
            ]
            return any(
                group.get("name", "").lower() in [g.lower() for g in admin_groups]
                for group in groups
            )
        except Exception as e:
            LOGGER.error(f"Error checking admin status for user {username}: {e}")
            return False

    def get_available_transitions(self, issue_key: str) -> List[Dict[str, str]]:
        """
        Get available transitions for an issue.
        """
        try:
            transitions = self.jira.transitions(issue_key)
            return [{"id": t["id"], "name": t["name"]} for t in transitions]
        except Exception as e:
            LOGGER.error(f"Error getting transitions for issue {issue_key}: {e}")
            return []

    def update_time_estimate(self, issue_key: str, remaining_estimate: str) -> None:
        """
        Update the remaining time estimate for an issue.
        """
        try:
            fields = {
                "timetracking": {
                    "remainingEstimate": remaining_estimate,
                },
            }
            self.update_issue_from_fields(issue_key, fields)
            LOGGER.info(
                f"Updated remaining estimate for {issue_key} to {remaining_estimate}",
            )
        except Exception as e:
            LOGGER.error(f"Error updating time estimate for issue {issue_key}: {e}")

    def get_issue_spent_time_in_seconds(self, issue_key: str) -> int:
        """
        Get the total time spent on an issue in seconds.
        """
        try:
            worklogs = self.jira.worklogs(issue_key)
            total_seconds = sum(worklog.timeSpentSeconds for worklog in worklogs)
            return total_seconds
        except Exception as e:
            LOGGER.error(f"Error fetching worklogs for issue {issue_key}: {e}")
            return 0

    def get_issues_with_approaching_deadlines(
        self,
        lookahead_days: int = 7,
        additional_jql: Optional[str] = None,
    ) -> List[Issue]:
        """
        Get issues with deadlines within the specified lookahead period.

        Args:
            lookahead_days: Number of days to look ahead for deadlines
            additional_jql: Additional JQL filter to apply

        Returns:
            List of Jira issues with approaching deadlines
        """
        try:
            jql = f"duedate <= {lookahead_days}d AND resolution = Unresolved"
            if additional_jql:
                jql += f" AND {additional_jql}"

            return self.search_for_issues(jql)
        except Exception as e:
            LOGGER.error(f"Error fetching issues with approaching deadlines: {e}")
            return []

    def search_issues(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 100,
        expand: Optional[str] = None,
    ) -> List[Issue]:
        """
        Search for issues using JQL.

        Args:
            jql: JQL query string
            start_at: Starting index for pagination
            max_results: Maximum number of results to return
            expand: Comma-separated list of fields to expand

        Returns:
            List of matching Jira issues
        """
        try:
            return self.jira.search_issues(
                jql,
                startAt=start_at,
                maxResults=max_results,
                expand=expand,
            )
        except Exception as e:
            LOGGER.error(f"Error searching issues with JQL '{jql}': {e}")
            return []

    def get_issue_with_expand(self, issue_key: str, expand: str) -> Optional[Issue]:
        """
        Get a single issue with expanded fields.

        Args:
            issue_key: The issue key
            expand: Comma-separated list of fields to expand

        Returns:
            Jira issue with expanded fields or None
        """
        try:
            return self.jira.issue(issue_key, expand=expand)
        except Exception as e:
            LOGGER.error(
                f"Error fetching issue {issue_key} with expand '{expand}': {e}",
            )
            return None

    def get_issue_by_summary(self, summary: str, board: str) -> Issue | None:
        query = f'project = {board} AND summary ~ "{summary}"'
        results = self.search_issues(query)
        for result in results:
            if result.field.summary == summary:
                return result
        return None

    def get_issue_url(self, issue: Issue) -> str:
        """
        Get the URL for a Jira issue.

        Args:
            issue: The Jira issue object

        Returns:
            URL string for the issue
        """
        return (
            f"{self.settings.domain.scheme}://{self.settings.domain.host}/browse/{issue.key}"
            if issue
            else ""
        )

    def get_issue_url_by_key(self, issue_key: str) -> str:
        """
        Get the URL for a Jira issue by its key.

        Args:
            issue_key: The key of the Jira issue

        Returns:
            URL string for the issue
        """
        return f"{self.settings.domain.scheme}://{self.settings.domain.host}/browse/{issue_key}"

    def get_transitions(self, issue_key: str) -> List[Dict[str, str]]:
        """
        Get available transitions for an issue.

        Args:
            issue_key: The key of the Jira issue

        Returns:
            List of available transitions with their IDs and names
        """
        try:
            transitions = self.jira.transitions(issue_key)
            return transitions
        except Exception as e:
            LOGGER.error(f"Error fetching transitions for issue {issue_key}: {e}")
            return []

    def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """
        Transition an issue to a new status.

        Args:
            issue_key: The key of the Jira issue
            transition_id: The ID of the transition to apply

        Raises:
            Exception if the transition fails
        """
        try:
            self.jira.transition_issue(issue_key, transition_id)
            LOGGER.info(f"Issue {issue_key} transitioned to {transition_id}")
        except Exception as e:
            LOGGER.error(
                f"Error transitioning issue {issue_key} to {transition_id}: {e}",
            )
            raise e

    def get_sprint_by_id(
        self,
        sprint_id: str,
        board_id: str,
    ) -> Optional[Dict[str, any]]:
        """
        Get sprint details by ID.

        Args:
            sprint_id: The ID of the sprint
            board_id: The ID of the board

        Returns:
            Sprint details as a dictionary or None if not found
        """
        try:
            sprints = self.get_sprints(board_id, get_from_cache=False)
            for sprint in sprints:
                if int(sprint.name.split(" ")[-1]) == int(sprint_id):
                    return {
                        "id": sprint.id,
                        "name": sprint.name,
                        "state": sprint.state,
                        "startDate": sprint.startDate,
                        "endDate": sprint.endDate,
                    }
            return None
        except Exception as e:
            LOGGER.error(f"Error fetching sprint {sprint_id} for board {board_id}: {e}")
            return None

    def get_sprint_by_name(
        self,
        sprint_name: str,
        board_id: str,
    ) -> Optional[Dict[str, any]]:
        """
        Get sprint details by name.

        Args:
            sprint_name: The name of the sprint
            board_id: The ID of the board

        Returns:
            Sprint details as a dictionary or None if not found
        """
        try:
            sprints = self.get_sprints(board_id, get_from_cache=False)
            for sprint in sprints:
                if sprint.name == sprint_name:
                    return {
                        "id": sprint.id,
                        "name": sprint.name,
                        "state": sprint.state,
                        "startDate": sprint.startDate,
                        "endDate": sprint.endDate,
                    }
            return {
                "id": None,
                "name": None,
                "state": None,
                "startDate": None,
                "endDate": None,
            }
        except Exception as e:
            LOGGER.error(
                f"Error fetching sprint {sprint_name} for board {board_id}: {e}",
            )
            return {
                "id": None,
                "name": None,
                "state": None,
                "startDate": None,
                "endDate": None,
            }

    def create_sprint(
        self,
        board_id: int,
        sprint_name: str,
        start_date: str,
        end_date: str,
        goal: str = None,
    ) -> Optional[Dict[str, any]]:
        """
        Create a new sprint.

        Args:
            board_id: The ID of the board to create the sprint in
            sprint_name: The name of the new sprint
            start_date: The start date of the sprint in ISO format
            end_date: The end date of the sprint in ISO format

        Returns:
            Sprint details as a dictionary or None if creation fails
        """
        try:
            sprint = self.jira.create_sprint(
                name=sprint_name,
                board_id=board_id,
                startDate=start_date,
                endDate=end_date,
                goal=goal,
            )
            return {
                "id": sprint.id,
                "name": sprint.name,
                "state": sprint.state,
                "start_date": sprint.startDate,
                "end_date": sprint.endDate,
                "goal": goal,
            }
        except Exception as e:
            LOGGER.error(f"Error creating sprint '{sprint_name}': {e}")
            return None

    def get_releases(self, project_key: str) -> List[Release]:
        """Get all releases for a Jira project.

        Args:
            project_key: Key of the Jira project.

        Returns:
            List of Release entities.
        """
        versions = self.jira.project_versions(project_key)
        return [Release(project=project_key, **v.raw) for v in versions]

    def release_exist(self, project_key: str, name: str) -> bool:
        """Check if a release exists for a Jira project.

        Args:
            project_key: Key of the Jira project.
            name: Name of the release.

        Returns:
            True if the release exists, False otherwise.
        """
        releases = self.get_releases(project_key)
        return any(release.name == name for release in releases)

    def create_release(
        self,
        project_key: str,
        name: str,
        description: Optional[str] = None,
        release_date: Optional[str] = None,
        released: bool = False,
    ) -> Release:
        """Create a new release for a Jira project.

        Args:
            project_key: Key of the Jira project.
            name: Name of the release.
            description: Optional description.
            release_date: Optional release date (YYYY-MM-DD).
            released: Whether the release is marked as released.

        Returns:
            The created Release entity.
        """
        payload: Dict[str, Any] = {
            "project": project_key,
            "name": name,
            "released": released,
        }
        if description:
            payload["description"] = description
        if release_date:
            payload["releaseDate"] = release_date
        version = self.jira.create_version(**payload)
        return Release(project=project_key, **version.raw)

    def get_issue_link_types(self) -> List[Dict[str, str]]:
        """Get available issue link types in Jira.

        Returns:
            List of link types with their names and descriptions
        """
        try:
            link_types = self.jira.issue_link_types()
            return [
                {
                    "name": link_type.name,
                    "inward": link_type.inward,
                    "outward": link_type.outward,
                }
                for link_type in link_types
            ]
        except Exception as e:
            LOGGER.error(f"Error getting issue link types: {e}")
            return []

    def link_issues(
        self,
        dependent_issue_key: str,
        dependency_issue_key: str,
        link_type: str = "Dependency",
    ) -> bool:
        """Link two Jira issues with a specified relationship.

        Args:
            dependent_issue_key: The issue that depends on another (outward issue)
            dependency_issue_key: The issue that is depended upon (inward issue)
            link_type: The type of link (e.g., "Dependency", "Blocks", "Relates")

        Returns:
            True if linking was successful, False otherwise
        """
        try:
            # Get available link types to find a suitable one
            available_link_types = self.get_issue_link_types()

            # First try to find the exact link type requested
            selected_link_type = None
            for link in available_link_types:
                if link["name"].lower() == link_type.lower():
                    selected_link_type = link["name"]
                    break

            # If requested link type not found, try common alternatives
            if not selected_link_type:
                fallback_types = [
                    "Blocks",
                    "Relates to",
                    "Relates",
                    "Clones",
                    "Duplicates",
                ]
                for fallback in fallback_types:
                    for link in available_link_types:
                        if link["name"].lower() == fallback.lower():
                            selected_link_type = link["name"]
                            LOGGER.warning(
                                f"Link type '{link_type}' not found, using '{selected_link_type}' instead",
                            )
                            break
                    if selected_link_type:
                        break

            # If still no link type found, use the first available one
            if not selected_link_type and available_link_types:
                selected_link_type = available_link_types[0]["name"]
                LOGGER.warning(
                    f"Link type '{link_type}' not found, using first available: '{selected_link_type}'",
                )

            if not selected_link_type:
                LOGGER.error("No issue link types available in Jira")
                return False

            # Create the issue link
            self.jira.create_issue_link(
                type=selected_link_type,
                inwardIssue=dependency_issue_key,
                outwardIssue=dependent_issue_key,
            )
            LOGGER.info(
                f"Successfully linked issues: {dependent_issue_key} -> {dependency_issue_key} ({selected_link_type})",
            )
            return True
        except Exception as e:
            LOGGER.error(
                f"Error linking issues {dependent_issue_key} -> {dependency_issue_key}: {e}",
            )
            return False

    def get_issue_subtasks(self, issue_key: str) -> List[Issue]:
        """Get all subtasks for a given Jira issue.

        Args:
            issue_key: The key of the parent issue

        Returns:
            List of subtask issues
        """
        try:
            issue = self.get_issue(issue_key)
            return [subtask for subtask in issue.fields.subtasks]
        except Exception as e:
            LOGGER.error(f"Error getting subtasks for issue {issue_key}: {e}")
            return []

    def delete_issue(self, issue_key: str) -> bool:
        """Delete a Jira issue.

        Args:
            issue_key: The key of the issue to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            self.jira.delete_issue(issue_key)
            LOGGER.info(f"Successfully deleted issue {issue_key}")
            return True
        except Exception as e:
            LOGGER.error(f"Error deleting issue {issue_key}: {e}")
            return False
