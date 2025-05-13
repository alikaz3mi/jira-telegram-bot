"""Jira Cloud Repository implementation.

This module provides a repository implementation for interacting with Jira Cloud.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue
from jira import JIRA

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
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
            server=self.settings.domain,
            basic_auth=(self.settings.email, self.settings.token),
        )
        
        self.cache = {}
        
        # Custom field IDs - may differ between Jira Cloud instances
        # These are common defaults for Jira Cloud, but they might need configuration
        self.jira_story_point_id = "customfield_10016"  # Different from server
        self.jira_original_estimate_id = "customfield_10014"
        self.jira_sprint_id = "customfield_10020"  # Different from server
        self.jira_epic_link_id = "customfield_10014"  # Different from server

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
            if hasattr(board, 'type'):
                self.board_type = board.type
                self._set_cache(cache_key, board.id)
                return board.id
            # Fallback if board doesn't have type
            if hasattr(board, 'name') and project_key in board.name:
                self.board_type = "scrum"  # Assume scrum by default
                self._set_cache(cache_key, board.id)
                return board.id
        return None

    def get_sprints(self, board_id):
        """Get sprints for a board.
        
        Args:
            board_id: Jira board ID.
            
        Returns:
            List of sprints for the board.
        """
        cache_key = ("get_sprints", board_id)
        result = self._get_from_cache(cache_key, 8 * 3600)  # Cache for 8 hours
        if result is not None:
            return result

        if not hasattr(self, 'board_type') or self.board_type == "scrum":
            try:
                # In cloud, we need to filter out closed sprints
                result = self.jira.sprints(board_id=board_id, state='active,future')
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
            if hasattr(metadata, 'issueTypes'):
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
                if hasattr(issue.fields, 'assignee') and issue.fields.assignee:
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
        if hasattr(self, 'board_type'):
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