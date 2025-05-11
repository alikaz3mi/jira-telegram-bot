from __future__ import annotations

from typing import Dict
from typing import List

from jira_telegram_bot.entities.task import TaskData


class ISummaryGenerator:
    def generate_summary(
        self,
        grouped_tasks: Dict[str, Dict[str, List[TaskData]]],
    ) -> str:
        pass
