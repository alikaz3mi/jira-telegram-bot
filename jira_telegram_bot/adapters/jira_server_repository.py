from __future__ import annotations

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

    def get_projects(self):
        return self.jira.projects()

    def get_project_components(self, project_key):
        return self.jira.project_components(project_key)

    def get_epics(self, project_key: str):
        return self.jira.search_issues(
            f'project={project_key} AND issuetype=Epic AND status in ("Backlog", "To Do", "In Progress")',
        )

    def get_boards(self):
        return self.jira.boards()

    def get_sprints(self, board_id):
        return self.jira.sprints(board_id=board_id)

    def get_project_versions(self, project_key):
        return self.jira.project_versions(project_key)

    def create_issue(self, fields):
        return self.jira.create_issue(fields=fields)

    def add_attachment(self, issue, attachment, filename):
        self.jira.add_attachment(issue=issue, attachment=attachment, filename=filename)
