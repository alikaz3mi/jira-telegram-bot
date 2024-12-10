from __future__ import annotations

from typing import Dict
from typing import List

from jira_telegram_bot.entities.task import TaskData


class ITaskGrouper:
    def group_tasks(
        self,
        tasks: List[TaskData],
    ) -> Dict[str, Dict[str, List[TaskData]]]:
        pass
