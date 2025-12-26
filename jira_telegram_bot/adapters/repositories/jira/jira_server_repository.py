from __future__ import annotations

import json
import os
import time
from datetime import datetime
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
from jira_telegram_bot.entities.team_evaluation import ChangeLogEvent
from jira_telegram_bot.entities.team_evaluation import IssueSnapshot
from jira_telegram_bot.entities.team_evaluation import WorklogSlice
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
        self.jira_target_end_id = "customfield_10110"
        self.jira_target_start_id = "customfield_10109"
        self.jira_delay_reason_id = "customfield_10600"

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

        # Get board type for this specific board
        board_type = None
        try:
            boards = self.jira.boards()
            for board in boards:
                if board.id == board_id:
                    board_type = board.type if hasattr(board, 'type') else None
                    break
        except Exception as e:
            LOGGER.warning(f"Error fetching boards to determine type for board {board_id}: {e}")

        if board_type == "scrum":
            # Get all sprints with pagination to handle boards with many sprints
            result = []
            start_at = 0
            max_results = 50  # Jira default
            
            while True:
                try:
                    sprint_page = self.jira.sprints(
                        board_id=board_id, 
                        startAt=start_at, 
                        maxResults=max_results
                    )
                    if not sprint_page:
                        break
                    
                    result.extend(sprint_page)
                    
                    # If we got fewer than max_results, we're at the end
                    if len(sprint_page) < max_results:
                        break
                        
                    start_at += max_results
                    
                except Exception as e:
                    LOGGER.warning(f"Error fetching sprint page starting at {start_at}: {e}")
                    break
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

        if task_data.target_start:
            issue_fields[self.jira_target_start_id] = task_data.target_start
        if task_data.target_end:
            issue_fields[self.jira_target_end_id] = task_data.target_end
        if task_data.reporter:
            issue_fields["reporter"] = {"name": task_data.reporter}

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
                issue.fields.fixVersions[0].name
                if issue.fields.fixVersions
                else None  # TODO: only one relesase is set:-?
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

            label_list = sorted(labels)
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
                if str(sprint.id) == str(sprint_id):
                    return {
                        "id": sprint.id,
                        "name": sprint.name,
                        "state": sprint.state,
                        "startDate": getattr(sprint, "startDate", None),
                        "endDate": getattr(sprint, "endDate", None),
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
            LOGGER.debug(f"Found {len(sprints)} total sprints on board {board_id}")
            LOGGER.debug(f"Looking for sprint name: '{sprint_name}'")
            
            matching_sprints = []
            for sprint in sprints:
                if sprint.name.lower() == sprint_name.lower():
                    matching_sprints.append(sprint.name)
                    return {
                        "id": sprint.id,
                        "name": sprint.name,
                        "state": sprint.state,
                        "startDate": sprint.startDate,
                        "endDate": sprint.endDate,
                    }
            
            # Log some sprint names for debugging
            if sprints:
                sample_names = [s.name for s in sprints[:5]]  # First 5 sprint names
                LOGGER.debug(f"Sample sprint names: {sample_names}")
                
            LOGGER.debug(f"No exact match found for '{sprint_name}'")
            return None
        except Exception as e:
            LOGGER.error(
                f"Error fetching sprint {sprint_name} for board {board_id}: {e}",
            )
            return None

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
        LOGGER.debug(f"Created release for {project_key}: {name}")
        return Release(project=project_key, **version.raw)

    def update_release(
        self,
        project_key: str,
        release_name: str,
        description: Optional[str] = None,
        released: Optional[bool] = None,
        release_date: Optional[str] = None,
    ) -> bool:
        """Update an existing release for a Jira project.

        Args:
            project_key: Key of the Jira project.
            release_name: Name of the release to update.
            description: Optional new description.
            released: Optional released status.
            release_date: Optional release date (YYYY-MM-DD).

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Find the version by name
            versions = self.jira.project_versions(project_key)
            target_version = None
            for version in versions:
                if version.name == release_name:
                    target_version = version
                    break

            if not target_version:
                LOGGER.error(
                    f"Release '{release_name}' not found in project {project_key}",
                )
                return False

            # Prepare update payload
            update_payload = {}
            if description is not None:
                update_payload["description"] = description
            if released is not None:
                update_payload["released"] = released
            if release_date is not None:
                update_payload["releaseDate"] = release_date

            if not update_payload:
                LOGGER.warning("No fields to update for release")
                return True

            # Update the version
            target_version.update(**update_payload)
            LOGGER.info(
                f"Successfully updated release '{release_name}' in project {project_key}",
            )
            return True

        except Exception as e:
            LOGGER.error(
                f"Error updating release '{release_name}' in project {project_key}: {e}",
            )
            return False

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

    def create_issue_link(
        self,
        link_type: str,
        outward_issue: str,
        inward_issue: str,
    ) -> bool:
        """Create a link between two issues.

        Args:
            link_type: Type of link (e.g., "Blocks", "Relates")
            outward_issue: Outward issue key
            inward_issue: Inward issue key

        Returns:
            True if successful, False otherwise
        """
        try:
            self.jira.create_issue_link(
                type=link_type,
                outwardIssue=outward_issue,
                inwardIssue=inward_issue,
            )
            LOGGER.info(
                f"Successfully linked {outward_issue} to {inward_issue} ({link_type})",
            )
            return True
        except Exception as e:
            LOGGER.error(f"Error linking {outward_issue} to {inward_issue}: {e}")
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
            return list(issue.fields.subtasks)
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
            issue = self.get_issue(issue_key)
            issue.delete()
            LOGGER.info(f"Successfully deleted issue {issue_key}")
            return True
        except Exception as e:
            LOGGER.error(f"Error deleting issue {issue_key}: {e}")
            return False

    async def get_sprint(self, sprint_id: int):
        """Get sprint information by ID.

        Args:
            sprint_id: The sprint ID

        Returns:
            Sprint object with dates, name, and ID
        """
        try:
            # Use Jira API to get sprint by ID
            sprint = self.jira.sprint(sprint_id)
            return sprint
        except Exception as e:
            LOGGER.error(f"Error fetching sprint {sprint_id}: {e}")
            return None

    async def get_sprint_issues(self, project_keys: List[str], sprint_id: int) -> List:
        """Get all issues for a sprint across projects.

        Args:
            project_keys: List of project keys to search
            sprint_id: The sprint ID

        Returns:
            List of IssueSnapshot objects
        """

        try:
            # Build JQL to get issues for the sprint
            if project_keys:
                projects_filter = " OR ".join(
                    [f'project = "{key}"' for key in project_keys],
                )
                jql = f"({projects_filter}) AND sprint = {sprint_id}"
            else:
                # No project filter, just get all issues in the sprint
                jql = f"sprint = {sprint_id}"

            issues = self.search_for_issues(jql)

            # Convert to IssueSnapshot objects
            snapshots = []
            for issue in issues:
                try:
                    # Get linked issues
                    linked_issues = []
                    if hasattr(issue.fields, "issuelinks"):
                        for link in issue.fields.issuelinks:
                            if hasattr(link, "outwardIssue"):
                                linked_issues.append(link.outwardIssue.key)
                            if hasattr(link, "inwardIssue"):
                                linked_issues.append(link.inwardIssue.key)

                    # Get epic information
                    epic_key = getattr(issue.fields, self.jira_epic_link_id, None)
                    epic_name = None
                    if epic_key:
                        epic_name = await self.get_issue_epic(epic_key)

                    snapshot = IssueSnapshot(
                        key=issue.key,
                        issue_type=issue.fields.issuetype.name,
                        priority=getattr(issue.fields.priority, "name", None)
                        if issue.fields.priority
                        else None,
                        labels=getattr(issue.fields, "labels", []),
                        components=[
                            c.name for c in getattr(issue.fields, "components", [])
                        ],
                        epic_key=epic_key,
                        epic_name=epic_name,
                        due_date=self._parse_jira_date(
                            getattr(issue.fields, "duedate", None),
                        ),
                        status=issue.fields.status.name,
                        assignee=getattr(issue.fields.assignee, "name", None)
                        if issue.fields.assignee
                        else None,
                        project_key=issue.fields.project.key,
                        project_name=issue.fields.project.name,
                        resolution_date=self._parse_jira_date(
                            getattr(issue.fields, "resolutiondate", None),
                        ),
                        created_date=self._parse_jira_date(issue.fields.created),
                        updated_date=self._parse_jira_date(issue.fields.updated),
                        linked_issues=linked_issues,
                        time_estimate_hours=(
                            issue.fields.timeoriginalestimate / 3600.0
                            if issue.fields.timeoriginalestimate
                            else 0.0
                        )
                    )
                    snapshots.append(snapshot)
                except Exception as e:
                    LOGGER.warning(
                        f"Error converting issue {issue.key} to snapshot: {e}",
                    )
                    continue

            return snapshots

        except Exception as e:
            LOGGER.error(f"Error fetching sprint issues: {e}")
            return []

    async def get_issue_worklogs(self, issue_keys: List[str]) -> List:
        """Get worklogs for multiple issues.

        Args:
            issue_keys: List of issue keys

        Returns:
            List of WorklogSlice objects
        """

        worklogs = []

        for issue_key in issue_keys:
            try:
                issue_worklogs = self.jira.worklogs(issue_key)

                for worklog in issue_worklogs:
                    try:
                        worklog_slice = WorklogSlice(
                            issue_key=issue_key,
                            author=worklog.author.name,
                            started_at=self._parse_jira_date(worklog.started),
                            hours=worklog.timeSpentSeconds / 3600.0,
                        )
                        worklogs.append(worklog_slice)
                    except Exception as e:
                        LOGGER.warning(f"Error parsing worklog for {issue_key}: {e}")
                        continue

            except Exception as e:
                LOGGER.warning(f"Error fetching worklogs for {issue_key}: {e}")
                continue

        return worklogs

    async def get_issue_changelogs(self, issue_keys: List[str]) -> Dict[str, List]:
        """Get changelogs for multiple issues.

        Args:
            issue_keys: List of issue keys

        Returns:
            Dictionary mapping issue keys to list of ChangeLogEvent objects
        """

        changelogs = {}

        for issue_key in issue_keys:
            try:
                issue = self.jira.issue(issue_key, expand="changelog")
                issue_events = []

                if hasattr(issue, "changelog") and hasattr(
                    issue.changelog,
                    "histories",
                ):
                    for history in issue.changelog.histories:
                        for item in history.items:
                            try:
                                event = ChangeLogEvent(
                                    issue_key=issue_key,
                                    field=item.field,
                                    from_status=item.fromString,
                                    to_status=item.toString,
                                    changed_at=self._parse_jira_date(history.created),
                                    author=history.author.name,
                                )
                                issue_events.append(event)
                            except Exception as e:
                                LOGGER.warning(
                                    f"Error parsing changelog item for {issue_key}: {e}",
                                )
                                continue

                changelogs[issue_key] = issue_events

            except Exception as e:
                LOGGER.warning(f"Error fetching changelog for {issue_key}: {e}")
                changelogs[issue_key] = []

        return changelogs

    async def get_issue_epic(self, issue_key: str) -> Optional[str]:
        """Get epic name for an issue.

        Args:
            issue_key: The issue key

        Returns:
            Epic name if found, None otherwise
        """
        try:
            issue = self.get_issue(issue_key)
            if issue and issue.fields.issuetype.name == "Epic":
                return getattr(issue.fields, self.jira_epic_name_id, None)
            return None
        except Exception as e:
            LOGGER.warning(f"Error fetching epic name for {issue_key}: {e}")
            return None

    def _parse_jira_date(self, date_str):
        """Parse Jira date string to datetime.

        Args:
            date_str: Jira date string

        Returns:
            datetime object or None
        """
        if not date_str:
            return None

        try:
            # Jira typically returns dates in ISO format

            if isinstance(date_str, str):
                if "T" in date_str:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    return datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except Exception as e:
            LOGGER.warning(f"Error parsing date '{date_str}': {e}")
            return None

    def get_time_tracking(self, issue: Issue) -> tuple[float, float]:
        """Get ETA and total hours from time tracking.

        Args:
            issue: Jira issue object.

        Returns:
            Tuple of (eta_hours, total_hours).
        """
        eta_hours = 0.0
        total_hours = 0.0

        try:
            if hasattr(issue.fields, "timetracking"):
                time_tracking = issue.fields.timetracking
                if time_tracking:
                    original_estimate_seconds = getattr(
                        time_tracking,
                        "originalEstimateSeconds",
                        0,
                    ) or 0
                    eta_hours = original_estimate_seconds / 3600.0
                    total_hours = original_estimate_seconds / 3600.0

            original_estimate = getattr(
                issue.fields,
                "timeoriginalestimate",
                0,
            ) or 0
            if original_estimate > 0:
                eta_hours = original_estimate / 3600.0
                total_hours = original_estimate / 3600.0

        except Exception as e:
            LOGGER.error(f"Error getting time tracking for {issue.key}: {e}")

        return eta_hours, total_hours

    def get_worklog_data(
        self,
        issue: Issue,
    ) -> tuple[float, List[str], Dict[str, float], Dict[str, float]]:
        """Get worklog data including progress hours and individual hours.

        This method requires user_config to be available. It will attempt to import
        and use UserConfig directly if not provided via dependency injection.

        Args:
            issue: Jira issue object.

        Returns:
            Tuple of (progress_hours, involved_people, department_hours, individual_hours).
        """
        from jira_telegram_bot.adapters.user_config import UserConfig
        from jira_telegram_bot.entities.story_synchronization.constants import (
            DEPARTMENT_MAPPING,
        )

        user_config = UserConfig()

        progress_hours = 0.0
        involved_people = set()
        department_hours = {
            "ai_hours": 0.0,
            "backend_hours": 0.0,
            "frontend_hours": 0.0,
            "devops_hours": 0.0,
            "ui_ux_hours": 0.0,
            "qa_pm_hours": 0.0,
        }
        individual_hours = {}

        try:
            issue_with_worklog = self.get_issue_with_expand(issue.key, "worklog")
            if issue_with_worklog and hasattr(issue_with_worklog.fields, "worklog"):
                worklogs = issue_with_worklog.fields.worklog.worklogs
                for worklog in worklogs:
                    time_spent_seconds = getattr(worklog, "timeSpentSeconds", 0) or 0
                    hours = time_spent_seconds / 3600.0
                    progress_hours += hours

                    author = getattr(worklog, "author", None)
                    if author:
                        author_name = getattr(author, "name", None)
                        if author_name:
                            display_name = self._get_google_sheet_name(
                                author_name,
                                user_config,
                            )
                            if display_name:
                                involved_people.add(display_name)

                                if display_name not in individual_hours:
                                    individual_hours[display_name] = 0.0
                                individual_hours[display_name] += hours

                                user_dept = self._get_user_department(
                                    author_name,
                                    user_config,
                                    DEPARTMENT_MAPPING,
                                )
                                if user_dept:
                                    department_hours[user_dept] = (
                                        department_hours.get(user_dept, 0.0) + hours
                                    )

        except Exception as e:
            LOGGER.error(f"Error getting worklog data for {issue.key}: {e}")

        return (
            progress_hours,
            sorted(list(involved_people)),
            department_hours,
            individual_hours,
        )

    def _get_google_sheet_name(
        self,
        jira_username: str,
        user_config,
    ) -> Optional[str]:
        """Get Google Sheet display name for a Jira username.

        Args:
            jira_username: Jira username.
            user_config: UserConfigInterface instance.

        Returns:
            Google Sheet display name or jira_username as fallback.
        """
        try:
            user = user_config.get_user_config_by_jira_username(jira_username)
            if user and user.google_sheet_name:
                return user.google_sheet_name
            return jira_username
        except Exception as e:
            LOGGER.debug(f"Error getting Google Sheet name for {jira_username}: {e}")
            return jira_username

    def _get_user_department(
        self,
        jira_username: str,
        user_config,
        department_mapping: Dict[str, str],
    ) -> Optional[str]:
        """Get department field name for a user.

        Args:
            jira_username: Jira username.
            user_config: UserConfigInterface instance.
            department_mapping: Mapping from department names to field names.

        Returns:
            Department field name (e.g., 'ai_hours', 'backend_hours') or None.
        """
        try:
            user = user_config.get_user_config_by_jira_username(jira_username)
            if user and hasattr(user, "department"):
                dept = user.department
                return department_mapping.get(dept)
        except Exception as e:
            LOGGER.debug(f"Error getting department for {jira_username}: {e}")
        return None
