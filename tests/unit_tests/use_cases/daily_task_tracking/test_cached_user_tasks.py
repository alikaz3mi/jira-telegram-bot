"""Unit tests for CachedUserTasksUseCase."""
import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.cached_user_tasks import (
    CachedUserTasksUseCase,
)


def _task(key="PARSCHAT-1"):
    return DailyTaskCheck(
        issue_key=key,
        summary="کار",
        status="In Progress",
        assignee="ali",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key="PARSCHAT",
    )


class TestCachedUserTasksUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for CachedUserTasksUseCase."""

    def setUp(self):
        self.inner = AsyncMock()
        self.inner.execute.return_value = [_task()]
        self.use_case = CachedUserTasksUseCase(self.inner, ttl_seconds=60)

    async def test_second_call_is_served_from_cache(self):
        """The slow JQL runs once per user per window."""
        await self.use_case.execute("ali")
        await self.use_case.execute("ali")

        self.inner.execute.assert_awaited_once()

    async def test_users_do_not_share_an_entry(self):
        """One user's list must never be served to another."""
        await self.use_case.execute("ali")
        await self.use_case.execute("sara")

        self.assertEqual(self.inner.execute.await_count, 2)

    async def test_expiry_refetches(self):
        """A stale entry is replaced rather than returned."""
        use_case = CachedUserTasksUseCase(self.inner, ttl_seconds=0)

        await use_case.execute("ali")
        await use_case.execute("ali")

        self.assertEqual(self.inner.execute.await_count, 2)

    async def test_invalidate_forces_a_refetch(self):
        """After writing worklogs the next read sees fresh data."""
        await self.use_case.execute("ali")
        self.use_case.invalidate("ali")
        await self.use_case.execute("ali")

        self.assertEqual(self.inner.execute.await_count, 2)

    async def test_project_filtered_lookups_are_not_cached(self):
        """A filtered query must not populate or read the unfiltered entry."""
        await self.use_case.execute("ali", ["PARSCHAT"])
        await self.use_case.execute("ali", ["PARSCHAT"])

        self.assertEqual(self.inner.execute.await_count, 2)

    async def test_invalidating_an_unknown_user_is_harmless(self):
        """Invalidation is safe to call unconditionally."""
        self.use_case.invalidate("nobody")


if __name__ == "__main__":
    unittest.main()
