from __future__ import annotations

import time
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue
from jira import JIRA

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings.jira_board_config import JiraBoardSettings
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
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
        self.jira_sprint_id = "customfield_10104"
        self.jira_epic_link_id = "customfield_10100"

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
                self._set_cache(cache_key, board.id)
                return board.id
        return None

    def get_sprints(self, board_id):
        cache_key = ("get_sprints", board_id)
        result = self._get_from_cache(cache_key, 8 * 3600)  # Cache for 8 hours
        if result is not None:
            return result

        result = self.jira.sprints(board_id=board_id)
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

    def build_issue_fields(self, task_data: TaskData) -> dict:
        issue_fields = {
            "project": {"key": task_data.project_key},
            "summary": task_data.summary,
            "description": task_data.description or "No Description Provided",
            "issuetype": {"name": task_data.task_type or "Task"},
        }

        if task_data.component:
            issue_fields["components"] = [{"name": task_data.component}]
        if task_data.story_points is not None:
            issue_fields[self.jira_story_point_id] = task_data.story_points
        if task_data.sprint_id:
            issue_fields[self.jira_sprint_id] = task_data.sprint_id
        if task_data.epic_link:
            issue_fields[self.jira_epic_link_id] = task_data.epic_link
        if task_data.release:
            issue_fields["fixVersions"] = [{"name": task_data.release}]
        if task_data.assignee:
            issue_fields["assignee"] = {"name": task_data.assignee}
        if task_data.priority:
            issue_fields["priority"] = {"name": task_data.priority}

        return issue_fields

    def handle_attachments(self, issue: Issue, attachments: Dict[str, List]):
        for media_type, files in attachments.items():
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

    def create_task_data_from_jira_issue(self, issue) -> TaskData:
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
