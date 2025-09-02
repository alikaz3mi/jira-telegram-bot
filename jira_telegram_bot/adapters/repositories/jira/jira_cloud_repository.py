"""Jira Cloud Repository implementation.

This module provides a repository implementation for interacting with Jira Cloud.
"""
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
from jira_telegram_bot.settings.jira_board_config import JiraBoardSettings
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class JiraCloudRepository(TaskManagerRepositoryInterface):
    """Repository for interacting with Jira Cloud instances.

    This class provides implementation for all operations defined in the
    TaskManagerRepositoryInterface, specifically tailored for Jira Cloud instances.
    """

    def __init__(self, settings: JiraBoardSettings):
        """Initialize the Jira Cloud repository.

        Args:
            settings: Settings for connecting to Jira Cloud.
        """
        self.settings = settings

        # Jira Cloud always uses API token authentication
        self.jira = JIRA(
            server=f"{self.settings.domain.scheme}://{self.settings.domain.host}",
            basic_auth=(self.settings.email, self.settings.token),
        )

        self.cache = {}

        # Custom field IDs - may differ between Jira Cloud instances
        # These are common defaults for Jira Cloud, but they might need configuration
        self.jira_story_point_id = "customfield_10016"  # Different from server
        self.jira_original_estimate_id = "customfield_10014"
        self.jira_sprint_id = "customfield_10020"  # Different from server
        self.jira_epic_link_id = "customfield_10014"  # Different from server
        self.jira_epic_name_id = "customfield_10011"  # Epic Name field for cloud
        self.jira_target_end_id = "customfield_10015"  # Target End for cloud
        self.jira_target_start_id = "customfield_10013"  # Target Start for cloud

    def _get_from_cache(self, cache_key, max_age_seconds):
        """Get data from cache if not expired.

        Args:
            cache_key: The unique key for the cached item.
            max_age_seconds: Maximum cache age in seconds.

        Returns:
            Cached value or None if expired or not present.
        """
        entry = self.cache.get(cache_key)
        if entry:
            timestamp, result = entry
            if time.time() - timestamp < max_age_seconds:
                return result
        return None

    def _set_cache(self, cache_key, result):
        """Store data in cache.

        Args:
            cache_key: The unique key for the cached item.
            result: The value to cache.
        """
        self.cache[cache_key] = (time.time(), result)

    def get_projects(self):
        """Get all projects accessible to the user.

        Returns:
            List of Jira projects.
        """
        cache_key = ("get_projects", None)
        result = self._get_from_cache(cache_key, 48 * 3600)
        if result is not None:
            return result

        result = self.jira.projects()
        self._set_cache(cache_key, result)
        return result

    def get_project_components(self, project_key):
        """Get components for a given project.

        Args:
            project_key: Jira project key.

        Returns:
            List of components for the project.
        """
        return self.jira.project_components(project_key)

    def get_epics(self, project_key: str):
        """Get all epics for a project.

        Args:
            project_key: Jira project key.

        Returns:
            List of epics for the project.
        """
        cache_key = ("get_epics", project_key)
        result = self._get_from_cache(cache_key, 72 * 3600)
        if result is not None:
            return result

        # Cloud JQL uses different syntax
        result = self.jira.search_issues(
            f'project="{project_key}" AND issuetype=Epic AND statusCategory != Done',
        )
        self._set_cache(cache_key, result)
        return result

    def get_board_id(self, project_key: str) -> Optional[int]:
        """Get board ID for a project.

        Args:
            project_key: Jira project key.

        Returns:
            Board ID or None if not found.
        """
        cache_key = ("get_board_id", project_key)
        result = self._get_from_cache(cache_key, 48 * 3600)
        if result is not None:
            return result

        boards = self.jira.boards(projectKeyOrID=project_key)
        for board in boards:
            if hasattr(board, "type"):
                self.board_type = board.type
                self._set_cache(cache_key, board.id)
                return board.id
            # Fallback if board doesn't have type
            if hasattr(board, "name") and project_key in board.name:
                self.board_type = "scrum"  # Assume scrum by default
                self._set_cache(cache_key, board.id)
                return board.id
        return None

    def get_sprints(self, board_id, get_from_cache: bool = True):
        """Get sprints for a board.

        Args:
            board_id: Jira board ID.
            get_from_cache: Whether to use cached results.

        Returns:
            List of sprints for the board.
        """
        cache_key = ("get_sprints", board_id)
        if get_from_cache:
            result = self._get_from_cache(cache_key, 8 * 3600)  # Cache for 8 hours
        else:
            result = None
        if result is not None:
            return result

        if not hasattr(self, "board_type") or self.board_type == "scrum":
            try:
                # In cloud, we need to filter out closed sprints
                result = self.jira.sprints(board_id=board_id, state="active,future")
            except Exception as e:
                LOGGER.warning(f"Failed to get sprints: {e}, defaulting to empty list")
                result = []
        else:
            result = []
        self._set_cache(cache_key, result)
        return result

    def get_project_versions(self, project_key):
        """Get versions for a project.

        Args:
            project_key: Jira project key.

        Returns:
            List of project versions.
        """
        cache_key = ("get_project_versions", project_key)
        result = self._get_from_cache(cache_key, 2 * 86400)  # Cache for 2 days
        if result is not None:
            return result

        result = self.jira.project_versions(project_key)
        self._set_cache(cache_key, result)
        return result

    def get_issue_types_for_project(self, project_key):
        """Get issue types available for a project.

        Args:
            project_key: Jira project key.

        Returns:
            List of issue type names.
        """
        cache_key = ("issue_types_for_project", project_key)
        result = self._get_from_cache(cache_key, 4 * 3600)  # Cache for 4 hours
        if result is not None:
            return result

        try:
            result = [
                issue_type.name
                for issue_type in self.jira.issue_types_for_project(project_key)
            ]
        except Exception as e:
            LOGGER.error(f"Error getting issue types for project {project_key}: {e}")
            metadata = self.jira.project(project_key)
            if hasattr(metadata, "issueTypes"):
                result = [it.name for it in metadata.issueTypes]
            else:
                # Fallback to generic issue types
                result = ["Task", "Bug", "Story", "Epic", "Subtask"]

        self._set_cache(cache_key, result)
        return result

    def get_priorities(self):
        """Get all available priorities.

        Returns:
            List of priorities.
        """
        cache_key = "priorities"
        result = self._get_from_cache(cache_key, 1200 * 3600)
        if result is not None:
            return result

        result = self.jira.priorities()
        self._set_cache(cache_key, result)
        return result

    def get_assignees(self, project_key: str) -> List[str]:
        """Get all assignees for a project.

        Args:
            project_key: Jira project key.

        Returns:
            List of assignee usernames.
        """
        try:
            cache_key = ("get_assignees", project_key)
            result = self._get_from_cache(cache_key, 2 * 3600)  # Cache for 2 hours
            if result is not None:
                return result

            assignees = set()
            # Cloud API has different JQL syntax
            recent_issues = self.jira.search_issues(
                f'project = "{project_key}" AND created >= -30d',
                maxResults=100,
            )
            for issue in recent_issues:
                if hasattr(issue.fields, "assignee") and issue.fields.assignee:
                    # In Cloud, we use accountId instead of name
                    assignees.add(issue.fields.assignee.accountId)

            assignee_list = sorted(assignees) if assignees else []
            self._set_cache(cache_key, assignee_list)
            return assignee_list
        except Exception as e:
            LOGGER.error(f"Error fetching assignees for project {project_key}: {e}")
            return []

    def search_users(self, username: str) -> List[str]:
        """Search for users by username.

        Args:
            username: Partial username to search for.

        Returns:
            List of matching usernames.
        """
        cache_key = ("search_users", username)
        result = self._get_from_cache(cache_key, 1 * 3600)  # Cache for 1 hour
        if result is not None:
            return result

        # Cloud API uses different parameters
        try:
            users = self.jira.search_users(query=username, maxResults=50)
            # In Cloud, we use accountId instead of name
            user_list = [user.accountId for user in users]
        except Exception as e:
            LOGGER.error(f"Error searching users with {username}: {e}")
            user_list = []

        self._set_cache(cache_key, user_list)
        return user_list

    def search_for_issues(self, query: str, max_results: int = 1000) -> List[Issue]:
        """Search for issues using JQL.

        Args:
            query: JQL query string.
            max_results: Maximum number of results to return.

        Returns:
            List of matching issues.
        """
        all_issues = []
        block_size = 100
        block_num = 0
        while True:
            start_idx = block_num * block_size
            issues_block = self.jira.search_issues(
                query,
                startAt=start_idx,
                maxResults=block_size,
            )
            all_issues.extend(issues_block)
            if len(issues_block) < block_size or len(all_issues) >= max_results:
                break
            block_num += 1
        return all_issues[:max_results]

    def get_stories_by_epic(self, epic_key: str, project_key: str) -> List[Issue]:
        """Get stories linked to an epic.

        Args:
            epic_key: Epic issue key.
            project_key: Jira project key.

        Returns:
            List of stories linked to the epic.
        """
        # Cloud uses different approach for epic links
        query = (
            f'project = "{project_key}" AND issuetype = Story AND '
            f'"Epic Link" = {epic_key}'
        )
        return self.search_for_issues(query)

    def get_stories_by_project(
        self,
        project_key: str,
        epic_link: str = None,
        status: str = None,
        filters: str = None,
    ) -> List[Issue]:
        """Get stories for a project with optional filtering.

        Args:
            project_key: Jira project key.
            epic_link: Optional epic key to filter by.
            status: Optional status to filter by.
            filters: Optional additional JQL filters.

        Returns:
            List of matching stories.
        """
        query = f'project = "{project_key}" AND issuetype = Story'
        if status:
            query += f" AND status in ({status})"
        if epic_link:
            query += f' AND "Epic Link" = {epic_link}'
        if filters:
            query += f" AND {filters}"
        return self.search_for_issues(query)

    def build_issue_fields(self, task_data: TaskData) -> dict:
        """Build issue fields dictionary from task data.

        Args:
            task_data: Task data model.

        Returns:
            Dictionary of issue fields ready for API use.
        """
        issue_fields = {
            "project": {"key": task_data.project_key},
            "summary": task_data.summary,
            "description": task_data.description or "No Description Provided",
            "issuetype": {"name": task_data.task_type or "Task"},
        }

        if task_data.components:
            issue_fields["components"] = [
                {"name": component} for component in task_data.components
            ]
        if task_data.story_points is not None:
            # Cloud uses the Story Points field directly
            issue_fields[self.jira_story_point_id] = task_data.story_points
        if task_data.sprint_id:
            issue_fields[self.jira_sprint_id] = task_data.sprint_id
        if task_data.epic_link:
            issue_fields[self.jira_epic_link_id] = task_data.epic_link
        if task_data.releases:
            issue_fields["fixVersions"] = [
                {"name": release} for release in task_data.releases
            ]
        if task_data.release:
            issue_fields["fixVersions"] = [{"name": task_data.release}]
        if task_data.assignee:
            # Cloud API uses accountId
            issue_fields["assignee"] = {"id": task_data.assignee}
        if task_data.priority:
            issue_fields["priority"] = {"name": task_data.priority}

        if task_data.due_date:
            issue_fields["duedate"] = task_data.due_date

        if task_data.labels:
            issue_fields["labels"] = [
                label.replace(" ", "-") for label in task_data.labels
            ]

        if task_data.task_type == "Sub-task":
            issue_fields["parent"] = {"key": task_data.parent_issue_key}
            # Remove sprint field for subtasks if present
            if issue_fields.get(self.jira_sprint_id):
                del issue_fields[self.jira_sprint_id]

        if task_data.task_type == "Epic":
            # For Epics, we need to set the epic name field
            issue_fields[self.jira_epic_name_id] = task_data.summary

        if task_data.target_start:
            issue_fields[self.jira_target_start_id] = task_data.target_start
        if task_data.target_end:
            issue_fields[self.jira_target_end_id] = task_data.target_end

        return issue_fields

    def build_task_data_from_issue(self, issue: Issue) -> TaskData:
        """Build a TaskData model from a Jira issue.

        Args:
            issue: Jira issue object.

        Returns:
            TaskData representation of the issue.
        """
        # In Cloud, assignee uses accountId
        assignee = getattr(issue.fields.assignee, "displayName", None)
        if not assignee and hasattr(issue.fields.assignee, "accountId"):
            assignee = issue.fields.assignee.accountId

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
            sprint_name=None,  # Will be set in create_task_data_from_jira_issue
            epic_link=getattr(issue.fields, self.jira_epic_link_id, None),
            release=(
                issue.fields.fixVersions[0].name if issue.fields.fixVersions else None
            ),
            assignee=assignee,
            priority=getattr(issue.fields.priority, "name", None),
        )

    def handle_attachments(self, issue: Issue, attachments: Dict[str, List]):
        """Add attachments to a Jira issue.

        Args:
            issue: Jira issue object.
            attachments: Dictionary of attachment files.
        """
        for _, files in attachments.items():
            for filename, file_buffer in files:
                self.add_attachment(
                    issue=issue,
                    attachment=file_buffer,
                    filename=filename,
                )
        LOGGER.info("Attachments attached to Jira issue")

    def create_issue(self, fields):
        """Create a new Jira issue.

        Args:
            fields: Issue fields dictionary.

        Returns:
            Created Jira issue object.
        """
        return self.jira.create_issue(fields=fields)

    def add_attachment(self, issue, attachment, filename):
        """Add an attachment to a Jira issue.

        Args:
            issue: Jira issue object.
            attachment: File content to attach.
            filename: Name for the attached file.
        """
        self.jira.add_attachment(issue=issue, attachment=attachment, filename=filename)

    def create_task(self, task_data: TaskData) -> Issue:
        """Create a new task in Jira.

        Args:
            task_data: Task data model.

        Returns:
            Created Jira issue object.
        """
        issue_fields = self.build_issue_fields(task_data)
        LOGGER.debug(f"Issue fields = {issue_fields}")
        new_issue = self.create_issue(issue_fields)
        self.handle_attachments(new_issue, task_data.attachments)
        return new_issue

    def add_comment(self, issue_key: str, comment: str):
        """Add a comment to a Jira issue.

        Args:
            issue_key: Jira issue key.
            comment: Comment text to add.
        """
        self.jira.add_comment(issue_key, comment)

    def create_task_data_from_jira_issue(self, issue) -> TaskData:
        """Create a TaskData object from a Jira issue.

        Args:
            issue: Jira issue object.

        Returns:
            TaskData representation of the issue.
        """
        sprint_name = None
        # Handle sprints differently in cloud
        if hasattr(self, "board_type"):
            if self.board_type == "kanban":
                sprint_name = "kanban"
            else:
                sprint_data = getattr(issue.fields, self.jira_sprint_id, None)
                if sprint_data:
                    # Sprint format is different in cloud
                    if isinstance(sprint_data, list) and len(sprint_data) > 0:
                        if hasattr(sprint_data[-1], "name"):
                            sprint_name = sprint_data[-1].name
                        elif isinstance(sprint_data[-1], str):
                            # Parse the string representation
                            parts = sprint_data[-1].split(",")
                            for part in parts:
                                if part.strip().startswith("name="):
                                    sprint_name = part.split("=")[1].strip()
                                    break

        # In Cloud, assignee uses accountId
        assignee = getattr(issue.fields.assignee, "displayName", None)
        if not assignee and hasattr(issue.fields.assignee, "accountId"):
            assignee = issue.fields.assignee.accountId

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
            assignee=assignee,
            priority=getattr(issue.fields.priority, "name", None),
        )

    def get_labels(self, project_key: str) -> List[str]:
        """Get all labels used in a project.

        Args:
            project_key: Jira project key.

        Returns:
            List of label strings.
        """
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
        """Save project labels to configuration.

        Args:
            project_key: Jira project key.
            labels: List of labels to save.

        Returns:
            True if successful, False otherwise.
        """
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
        """Transition a task to a different status.

        Args:
            issue_key: Jira issue key.
            status: Target status name.
        """
        transitions = self.jira.transitions(issue_key)
        for t in transitions:
            if t["name"].lower() == status.lower():
                self.jira.transition_issue(issue_key, t["id"])
                break

    def assign_issue(self, issue_key: str, assignee: str) -> None:
        """Assign an issue to a user.

        Args:
            issue_key: Jira issue key.
            assignee: User accountId to assign to.
        """
        # Cloud API expects accountId
        self.jira.assign_issue(issue_key, assignee)

    def update_issue(self, issue_key: str, task_data: TaskData) -> None:
        """Update an issue with new task data.

        Args:
            issue_key: Jira issue key.
            task_data: New task data.
        """
        fields = self.build_issue_fields(task_data)
        issue = self.jira.issue(issue_key)
        issue.update(fields=fields)
        LOGGER.info(f"Updated issue {issue_key} with fields: {fields}")

    def update_issue_from_fields(self, issue_key: str, fields: dict) -> None:
        """Update an issue with provided fields.

        Args:
            issue_key: Jira issue key.
            fields: Dictionary of fields to update.
        """
        issue = self.jira.issue(issue_key)
        issue.update(fields=fields)
        LOGGER.info(f"Updated issue {issue_key} with fields: {fields}")

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get a Jira issue by key.

        Args:
            issue_key: Jira issue key.

        Returns:
            Issue object or None if not found.
        """
        try:
            issue = self.jira.issue(issue_key)
            return issue
        except Exception as e:
            LOGGER.error(f"Error fetching issue {issue_key}: {e}")
            return None

    def get_issues_by_status(
        self,
        project_key: str,
        statuses: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """Get issues by status for a project.

        Args:
            project_key: Jira project key.
            statuses: Statuses to filter by.

        Returns:
            Dictionary of issue keys and their counts.
        """
        if statuses:
            query = f'project = "{project_key}" AND status IN ({",".join([f"{status}" for status in statuses])})'
        else:
            query = f'project = "{project_key}"'

        issues = self.search_for_issues(query)
        return {issue.key: issue.fields.status.name for issue in issues}

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
            from datetime import datetime, timedelta

            # Calculate date range
            today = datetime.now().date()
            future_date = today + timedelta(days=lookahead_days)

            # Build JQL query
            jql_parts = [
                "statusCategory != Done",
                f"(duedate <= '{future_date}' OR customfield_10110 <= '{future_date}')",
                "assignee is not EMPTY",
            ]

            if additional_jql:
                jql_parts.append(f"({additional_jql})")

            jql = " AND ".join(jql_parts)
            jql += " ORDER BY duedate ASC, customfield_10110 ASC"

            LOGGER.info(f"Searching for deadline issues with JQL: {jql}")

            # Search for issues
            issues = self.search_for_issues(jql, max_results=500)

            LOGGER.info(f"Found {len(issues)} issues with approaching deadlines")
            return issues

        except Exception as e:
            LOGGER.error(f"Error searching for deadline issues: {e}")
            return []

    def get_available_transitions(self, issue_key: str) -> List[Dict[str, str]]:
        """Get available transitions for an issue.

        Args:
            issue_key: The issue key

        Returns:
            List of transitions with id and name
        """
        try:
            transitions = self.jira.transitions(issue_key)
            return [{"id": t["id"], "name": t["name"]} for t in transitions]
        except Exception as e:
            LOGGER.error(f"Error getting transitions for issue {issue_key}: {e}")
            return []

    def get_issue_with_expand(self, issue_key: str, expand: str) -> Optional[Issue]:
        """Get a single issue with expanded fields.

        Args:
            issue_key: The issue key
            expand: Comma-separated list of fields to expand

        Returns:
            Jira issue with expanded fields or None
        """
        try:
            issue = self.jira.issue(issue_key, expand=expand)
            return issue
        except Exception as e:
            LOGGER.error(f"Error fetching issue {issue_key} with expand {expand}: {e}")
            return None

    def is_user_jira_admin(self, username: str) -> bool:
        """Check if a user has Jira administrator privileges.

        Args:
            username: Jira username to check

        Returns:
            True if user is Jira admin, False otherwise
        """
        try:
            # In Jira Cloud, check if user has admin permissions
            # This is a simplified check - in practice you might need to check specific permissions
            user = self.jira.user(username)
            if user:
                # Check if user has admin group membership or permissions
                # Note: The exact implementation depends on your Jira Cloud configuration
                # This is a basic implementation that might need adjustment
                return (
                    user.active
                    and hasattr(user, "groups")
                    and any(
                        "admin" in group.lower()
                        for group in getattr(user, "groups", [])
                    )
                )
            return False
        except Exception as e:
            LOGGER.error(f"Error checking admin status for user {username}: {e}")
            return False

    def search_issues(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 100,
        expand: Optional[str] = None,
    ) -> List[Issue]:
        """Search for issues using JQL.

        Args:
            jql: JQL query string
            start_at: Starting index for pagination
            max_results: Maximum number of results to return
            expand: Comma-separated list of fields to expand

        Returns:
            List of matching Jira issues
        """
        try:
            search_kwargs = {
                "jql_str": jql,
                "startAt": start_at,
                "maxResults": max_results,
            }
            if expand:
                search_kwargs["expand"] = expand

            issues = self.jira.search_issues(**search_kwargs)
            return issues
        except Exception as e:
            LOGGER.error(f"Error searching issues with JQL '{jql}': {e}")
            return []

    def update_time_estimate(self, issue_key: str, remaining_estimate: str) -> None:
        """Update the remaining time estimate for an issue.

        Args:
            issue_key: The issue key
            remaining_estimate: New remaining estimate (e.g., "0h", "2d")
        """
        try:
            issue = self.jira.issue(issue_key)
            # Update the remaining estimate field
            fields = {
                "timetracking": {
                    "remainingEstimate": remaining_estimate,
                },
            }
            issue.update(fields=fields)
            LOGGER.info(
                f"Updated time estimate for issue {issue_key} to {remaining_estimate}"
            )
        except Exception as e:
            LOGGER.error(f"Error updating time estimate for issue {issue_key}: {e}")

    def get_issue_spent_time_in_seconds(self, issue_key: str) -> int:
        """Get the total time spent on an issue in seconds.

        Args:
            issue_key: The issue key

        Returns:
            Total time spent in seconds
        """
        try:
            worklogs = self.jira.worklogs(issue_key)
            total_seconds = sum(worklog.timeSpentSeconds for worklog in worklogs)
            return total_seconds
        except Exception as e:
            LOGGER.error(f"Error fetching worklogs for issue {issue_key}: {e}")
            return 0

    def get_issue_by_summary(self, summary: str, board: str) -> Issue | None:
        """Get a Jira issue by its summary and board.

        Args:
            summary: The summary of the issue
            board: The board/project key

        Returns:
            Jira issue or None
        """
        query = f'project = "{board}" AND summary ~ "{summary}"'
        results = self.search_issues(query)
        for result in results:
            if result.fields.summary == summary:
                return result
        return None

    def get_issue_url(self, issue: Issue) -> str:
        """Get the URL for a Jira issue.

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
        """Get the URL for a Jira issue by its key.

        Args:
            issue_key: The key of the Jira issue

        Returns:
            URL string for the issue
        """
        return f"{self.settings.domain.scheme}://{self.settings.domain.host}/browse/{issue_key}"

    def get_transitions(self, issue_key: str) -> List[Dict[str, str]]:
        """Get available transitions for an issue.

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
        """Transition an issue to a new status.

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
        """Get sprint details by ID.

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
        """Get sprint details by name.

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
                        "startDate": getattr(sprint, "startDate", None),
                        "endDate": getattr(sprint, "endDate", None),
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
        """Create a new sprint.

        Args:
            board_id: The ID of the board to create the sprint in
            sprint_name: The name of the new sprint
            start_date: The start date of the sprint in ISO format
            end_date: The end date of the sprint in ISO format
            goal: The goal of the sprint (optional)

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
                "start_date": getattr(sprint, "startDate", None),
                "end_date": getattr(sprint, "endDate", None),
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
            if issue and hasattr(issue.fields, "subtasks"):
                return [subtask for subtask in issue.fields.subtasks]
            return []
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
            if issue:
                issue.delete()
                LOGGER.info(f"Successfully deleted issue {issue_key}")
                return True
            return False
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
        from jira_telegram_bot.entities.team_evaluation import IssueSnapshot

        try:
            # Build JQL to get issues for the sprint
            projects_filter = " OR ".join(
                [f'project = "{key}"' for key in project_keys]
            )
            jql = f"({projects_filter}) AND sprint = {sprint_id}"

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
                            getattr(issue.fields, "duedate", None)
                        ),
                        status=issue.fields.status.name,
                        assignee=getattr(issue.fields.assignee, "accountId", None)
                        if issue.fields.assignee
                        else None,
                        project_key=issue.fields.project.key,
                        project_name=issue.fields.project.name,
                        resolution_date=self._parse_jira_date(
                            getattr(issue.fields, "resolutiondate", None)
                        ),
                        created_date=self._parse_jira_date(issue.fields.created),
                        updated_date=self._parse_jira_date(issue.fields.updated),
                        linked_issues=linked_issues,
                    )
                    snapshots.append(snapshot)
                except Exception as e:
                    LOGGER.warning(
                        f"Error converting issue {issue.key} to snapshot: {e}"
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
        from jira_telegram_bot.entities.team_evaluation import WorklogSlice

        worklogs = []

        for issue_key in issue_keys:
            try:
                issue_worklogs = self.jira.worklogs(issue_key)

                for worklog in issue_worklogs:
                    try:
                        # In Cloud, author uses accountId
                        author = getattr(worklog.author, "accountId", None)
                        if not author:
                            author = getattr(worklog.author, "name", None)

                        worklog_slice = WorklogSlice(
                            issue_key=issue_key,
                            author=author,
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
        from jira_telegram_bot.entities.team_evaluation import ChangeLogEvent

        changelogs = {}

        for issue_key in issue_keys:
            try:
                issue = self.jira.issue(issue_key, expand="changelog")
                issue_events = []

                if hasattr(issue, "changelog") and hasattr(
                    issue.changelog, "histories"
                ):
                    for history in issue.changelog.histories:
                        for item in history.items:
                            try:
                                # In Cloud, author uses accountId
                                author = getattr(history.author, "accountId", None)
                                if not author:
                                    author = getattr(history.author, "name", None)

                                event = ChangeLogEvent(
                                    issue_key=issue_key,
                                    field=item.field,
                                    from_status=item.fromString,
                                    to_status=item.toString,
                                    changed_at=self._parse_jira_date(history.created),
                                    author=author,
                                )
                                issue_events.append(event)
                            except Exception as e:
                                LOGGER.warning(
                                    f"Error parsing changelog item for {issue_key}: {e}"
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
            from datetime import datetime

            if isinstance(date_str, str):
                if "T" in date_str:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    return datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except Exception as e:
            LOGGER.warning(f"Error parsing date '{date_str}': {e}")
            return None
