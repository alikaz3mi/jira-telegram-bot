"""Short-lived cache in front of the user's daily task lookup."""
from __future__ import annotations

import time
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.use_cases.daily_task_tracking.get_user_daily_tasks_use_case import (
    GetUserDailyTasksUseCase,
)

# A conversation is a burst of messages seconds apart; a task list does not
# meaningfully change inside one. Long enough to cover the burst, short enough
# that a status change in Jira shows up while the person is still talking.
DEFAULT_TTL_SECONDS = 120


class CachedUserTasksUseCase:
    """Reuse a user's task list across the messages of one conversation.

    The underlying JQL takes five to seven seconds against this Jira, and it
    ran on every message — twice for a single worklog report, since parsing
    and confirming each asked for the list. Caching per user for a couple of
    minutes removes that from the common path without letting the bot answer
    from a stale board.
    """

    def __init__(
        self,
        get_user_daily_tasks_use_case: GetUserDailyTasksUseCase,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        """Initialize the cache.

        Args:
            get_user_daily_tasks_use_case: The lookup being cached
            ttl_seconds: How long an entry stays usable
        """
        self._inner = get_user_daily_tasks_use_case
        self._ttl = ttl_seconds
        self._entries: Dict[str, Tuple[float, List[DailyTaskCheck]]] = {}

    async def execute(
        self,
        jira_username: str,
        project_keys: Optional[List[str]] = None,
    ) -> List[DailyTaskCheck]:
        """Return the user's tasks, from cache when it is still fresh.

        Args:
            jira_username: User's Jira username
            project_keys: Optional project filter; a filtered lookup is not
                cached, since the cache key is the user alone

        Returns:
            The user's tasks needing attention.
        """
        if project_keys:
            return await self._inner.execute(jira_username, project_keys)

        cached = self._entries.get(jira_username)
        if cached and (time.monotonic() - cached[0]) < self._ttl:
            LOGGER.info(f"Using cached task list for {jira_username}")
            return cached[1]

        tasks = await self._inner.execute(jira_username)
        self._entries[jira_username] = (time.monotonic(), tasks)
        return tasks

    def invalidate(self, jira_username: str) -> None:
        """Drop a user's cached list after their tasks are written to.

        Args:
            jira_username: User whose entry should be discarded
        """
        self._entries.pop(jira_username, None)
