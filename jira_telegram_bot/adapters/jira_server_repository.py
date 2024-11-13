from __future__ import annotations

import time

from jira import JIRA

from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class JiraRepository(TaskManagerRepositoryInterface):
    def __init__(self):
        self.jira = JIRA(
            server=JIRA_SETTINGS.domain,
            basic_auth=(JIRA_SETTINGS.username, JIRA_SETTINGS.password),
        )
        self.cache = {}

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
        result = self._get_from_cache(cache_key, 4 * 3600)  # Cache for 4 hours
        if result is not None:
            return result

        result = self.jira.projects()
        self._set_cache(cache_key, result)
        return result

    def get_project_components(self, project_key):
        # No caching for this method
        return self.jira.project_components(project_key)

    def get_epics(self, project_key: str):
        cache_key = ("get_epics", project_key)
        result = self._get_from_cache(cache_key, 1 * 3600)  # Cache for 1 hour
        if result is not None:
            return result

        result = self.jira.search_issues(
            f'project={project_key} AND issuetype=Epic AND status in ("Backlog", "To Do", "In Progress")',
        )
        self._set_cache(cache_key, result)
        return result

    def get_boards(self):
        # Assuming no caching required as per your instructions (since it's not listed)
        return self.jira.boards()

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

    def create_issue(self, fields):
        return self.jira.create_issue(fields=fields)

    def add_attachment(self, issue, attachment, filename):
        self.jira.add_attachment(issue=issue, attachment=attachment, filename=filename)
