from __future__ import annotations

from typing import Any

from jira import JIRA

from jira_telegram_bot.settings import JIRA_SETTINGS


class JiraRepository:
    def __init__(self):
        self.jira = JIRA(
            server=JIRA_SETTINGS.domain,
            basic_auth=(JIRA_SETTINGS.username, JIRA_SETTINGS.password),
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.jira(args, kwargs)
