from __future__ import annotations

import json
import os
import time
from typing import Dict
from typing import List
from typing import Optional
from typing import Any

from jira import Issue
from jira import JIRA

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.task import TaskData, JiraIssueReference
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings.jira_board_config import JiraBoardSettings
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class JiraRepository(TaskManagerRepositoryInterface):
    def __init__(self, settings: JiraBoardSettings = JIRA_SETTINGS):
        self.settings = settings
        self.jira = JIRA(
            server=self.settings.domain,
            basic_auth=(self.settings.username, self.settings.password),
        )
        self.cache = {}
        self.jira_story_point_id = "customfield_10106"
        self.jira_original_estimate_id = "customfield_10111"
        self.jira_sprint_id = "customfield_10104"
        self.jira_epic_link_id = "customfield_10100"
        self.board_type = "scrum"  # Default board type

    def _get_from_cache(self, cache_key: Any, max_age_seconds: int) -> Optional[Any]:
        """Get a cached result if it exists and is not expired.
        
        Args:
            cache_key: Key to lookup in cache
            max_age_seconds: Maximum age of cache entry in seconds
            
        Returns:
            Cached result if available and valid, None otherwise
        """
        entry = self.cache.get(cache_key)
        if entry:
            timestamp, result = entry
            if time.time() - timestamp < max_age_seconds:
                return result
        return None

    def _set_cache(self, cache_key: Any, result: Any) -> None:
        """Store a result in the cache.
        
        Args:
            cache_key: Key to store result under
            result: Value to cache
        """
        self.cache[cache_key] = (time.time(), result)

    def get_projects(self) -> List[Any]:
        """Get all available projects.
        
        Returns:
            List of project objects
        """
        cache_key = ("get_projects", None)
        result = self._get_from_cache(cache_key, 48 * 3600)
        if result is not None:
            return result

        result = self.jira.projects()
        self._set_cache(cache_key, result)
        return result

    def get_project_components(self, project_key: str) -> List[Any]:
        """Get components for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of component objects
        """
        return self.jira.project_components(project_key)

    def get_epics(self, project_key: str) -> List[Any]:
        """Get epics for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of epic objects
        """
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
        """Get board ID for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            Board ID if exists, None otherwise
        """
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

    def get_sprints(self, board_id: int) -> List[Any]:
        """Get sprints for a board.
        
        Args:
            board_id: Board identifier
            
        Returns:
            List of sprint objects
        """
        cache_key = ("get_sprints", board_id)
        result = self._get_from_cache(cache_key, 8 * 3600)  # Cache for 8 hours
        if result is not None:
            return result

        if self.board_type == "scrum":
            result = self.jira.sprints(board_id=board_id)
        else:
            result = []
        self._set_cache(cache_key, result)
        return result

    def get_project_versions(self, project_key: str) -> List[Any]:
        """Get versions for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of version objects
        """
        cache_key = ("get_project_versions", project_key)
        result = self._get_from_cache(cache_key, 2 * 86400)  # Cache for 2 days
        if result is not None:
            return result

        result = self.jira.project_versions(project_key)
        self._set_cache(cache_key, result)
        return result

    def get_issue_types_for_project(self, project_key: str) -> List[Any]:
        """Get issue types for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of issue type objects
        """
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

    def get_priorities(self) -> List[Any]:
        """Get available priorities.
        
        Returns:
            List of priority objects
        """
        cache_key = "priorities"
        result = self._get_from_cache(cache_key, 1200 * 3600)
        if result is not None:
            return result

        result = self.jira.priorities()
        self._set_cache(cache_key, result)
        return result

    def get_assignees(self, project_key: str) -> List[str]:
        """Get available assignees for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of assignee usernames
        """
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
        """Search for users by username.
        
        Args:
            username: Search term
            
        Returns:
            List of matching usernames
        """
        cache_key = ("search_users", username)
        result = self._get_from_cache(cache_key, 1 * 3600)  # Cache for 1 hour
        if result is not None:
            return result

        users = self.jira.search_users(username, maxResults=50)
        user_list = [user.name for user in users]
        self._set_cache(cache_key, user_list)
        return user_list

    def search_for_issues(self, query: str, max_results: int = 1000) -> List[Issue]:
        """Search for issues with a JQL query.
        
        Args:
            query: JQL query string
            max_results: Maximum number of results to return
            
        Returns:
            List of issue objects
        """
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

    def get_stories_by_epic(self, epic_key: str) -> List[JiraIssueReference]:
        """Get stories for an epic.
        
        Args:
            epic_key: Epic identifier
            
        Returns:
            List of story issue references
        """
        query = (
            f'issue in linkedIssues("{epic_key}") OR '
            f'"Epic Link" = {epic_key} AND issuetype = Story'
        )
        issues = self.search_for_issues(query)
        return [self._convert_issue_to_reference(issue) for issue in issues]

    def get_stories_by_project(
        self,
        project_key: str,
        epic_link: str = None,
        status: str = None,
    ) -> List[JiraIssueReference]:
        """Get stories for a project.
        
        Args:
            project_key: Project identifier
            epic_link: Optional epic link filter
            status: Optional status filter
            
        Returns:
            List of story issue references
        """
        query = f'project = "{project_key}" AND issuetype = Story'
        if status:
            query += f" AND status in ({status})"
        if epic_link:
            query += f' AND "Epic Link" = {epic_link}'
        
        issues = self.search_for_issues(query)
        return [self._convert_issue_to_reference(issue) for issue in issues]

    def _convert_issue_to_reference(self, issue: Issue) -> JiraIssueReference:
        """Convert a Jira Issue object to a JiraIssueReference domain entity.
        
        Args:
            issue: Jira Issue object
            
        Returns:
            JiraIssueReference domain entity
        """
        components = []
        if hasattr(issue.fields, 'components') and issue.fields.components:
            components = [c.name for c in issue.fields.components]
            
        labels = []
        if hasattr(issue.fields, 'labels') and issue.fields.labels:
            labels = issue.fields.labels
            
        return JiraIssueReference(
            key=issue.key,
            summary=issue.fields.summary,
            description=issue.fields.description,
            issue_type=issue.fields.issuetype.name if hasattr(issue.fields, 'issuetype') else None,
            priority=issue.fields.priority.name if hasattr(issue.fields, 'priority') else None,
            status=issue.fields.status.name if hasattr(issue.fields, 'status') else None,
            assignee=issue.fields.assignee.displayName if hasattr(issue.fields, 'assignee') and issue.fields.assignee else None,
            labels=labels,
            components=components,
        )

    def build_issue_fields(self, task_data: TaskData) -> dict:
        """Build issue fields dictionary from task data.
        
        Args:
            task_data: Task data entity
            
        Returns:
            Dictionary of issue fields
        """
        return task_data.to_jira_fields()

    def handle_attachments(self, issue: Any, attachments: Dict[str, List]) -> None:
        """Handle attachments for an issue.
        
        Args:
            issue: Issue object
            attachments: Dictionary of attachment data
        """
        for _, files in attachments.items():
            for filename, file_buffer in files:
                self.add_attachment(
                    issue=issue,
                    attachment=file_buffer,
                    filename=filename,
                )
        LOGGER.info("Attachments attached to Jira issue")

    def create_issue(self, fields: Dict[str, Any]) -> Any:
        """Create a new issue with the specified fields.
        
        Args:
            fields: Issue fields dictionary
            
        Returns:
            Created issue
        """
        return self.jira.create_issue(fields=fields)

    def add_attachment(self, issue: Any, attachment: Any, filename: str) -> None:
        """Add attachment to an issue.
        
        Args:
            issue: Issue object
            attachment: Attachment data
            filename: Attachment filename
        """
        self.jira.add_attachment(issue=issue, attachment=attachment, filename=filename)

    def create_task(self, task_data: TaskData) -> JiraIssueReference:
        """Create a new task from task data.
        
        Args:
            task_data: Task data entity
            
        Returns:
            Created issue reference
        """
        issue_fields = self.build_issue_fields(task_data)
        LOGGER.debug(f"Issue fields = {issue_fields}")
        new_issue = self.create_issue(issue_fields)
        self.handle_attachments(new_issue, task_data.attachments)
        return self._convert_issue_to_reference(new_issue)

    def add_comment(self, issue_key: str, comment: str) -> None:
        """Add a comment to an issue.
        
        Args:
            issue_key: Issue identifier
            comment: Comment text
        """
        self.jira.add_comment(issue_key, comment)

    def assign_issue(self, issue_key: str, assignee: str) -> None:
        """Assign an issue to a user.
        
        Args:
            issue_key: Issue identifier
            assignee: Username to assign to
        """
        self.jira.assign_issue(issue_key, assignee)

    def update_issue(self, issue_key: str, task_data: TaskData) -> None:
        """Update an issue with task data.
        
        Args:
            issue_key: Issue identifier
            task_data: Task data entity with updated fields
        """
        issue = self.jira.issue(issue_key)
        issue_fields = self.build_issue_fields(task_data)
        issue.update(fields=issue_fields)

    def update_issue_from_fields(self, issue_key: str, fields: dict) -> None:
        """Update an issue with raw fields.
        
        Args:
            issue_key: Issue identifier
            fields: Dictionary of fields to update
        """
        issue = self.jira.issue(issue_key)
        issue.update(fields=fields)

    def get_issue(self, issue_key: str) -> Optional[JiraIssueReference]:
        """Get an issue by key.
        
        Args:
            issue_key: Issue identifier
            
        Returns:
            Issue reference if exists, None otherwise
        """
        try:
            issue = self.jira.issue(issue_key)
            return self._convert_issue_to_reference(issue)
        except Exception as e:
            LOGGER.error(f"Error fetching issue {issue_key}: {e}")
            return None

    def create_task_data_from_jira_issue(self, issue: Any) -> TaskData:
        """Convert a Jira issue to TaskData entity.
        
        Args:
            issue: Jira issue object
            
        Returns:
            TaskData entity
        """
        if self.board_type == "kanban":
            sprint_name = "kanban"
        else:
            last_sprint_of_task = (
                getattr(issue.fields, self.jira_sprint_id)[-1]
                if getattr(issue.fields, self.jira_sprint_id)
                else None
            )
            sprint_name = None
            if last_sprint_of_task:
                name_position = last_sprint_of_task.find("name=")
                sprint_name = (
                    last_sprint_of_task[name_position:].split(",")[0].strip("name=")
                )
        
        components = []
        if hasattr(issue.fields, 'components') and issue.fields.components:
            components = [component.name for component in issue.fields.components]
            
        return TaskData(
            project_key=getattr(issue.fields.project, "key", None),
            summary=issue.fields.summary,
            description=issue.fields.description,
            component=(
                issue.fields.components[0].name if hasattr(issue.fields, 'components') and issue.fields.components else None
            ),
            components=components,
            task_type=getattr(issue.fields.issuetype, "name", None),
            story_points=getattr(issue.fields, self.jira_story_point_id, None),
            sprint_name=sprint_name,
            epic_link=getattr(issue.fields, self.jira_epic_link_id, None),
            release=(
                issue.fields.fixVersions[0].name if hasattr(issue.fields, 'fixVersions') and issue.fields.fixVersions else None
            ),
            assignee=getattr(issue.fields.assignee, "displayName", None) if hasattr(issue.fields, 'assignee') else None,
            priority=getattr(issue.fields.priority, "name", None) if hasattr(issue.fields, 'priority') else None,
        )

    def get_labels(self, project_key: str) -> List[str]:
        """Get labels for a project.
        
        Args:
            project_key: Project identifier
            
        Returns:
            List of label strings
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
        """Set labels for a project.
        
        Args:
            project_key: Project identifier
            labels: List of labels
            
        Returns:
            True if successful, False otherwise
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
