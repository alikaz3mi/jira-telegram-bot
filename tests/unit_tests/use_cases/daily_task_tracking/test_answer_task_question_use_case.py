"""Unit tests for AnswerTaskQuestionUseCase."""
import unittest
from datetime import datetime
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.answer_task_question_use_case import (
    AnswerTaskQuestionUseCase,
)

BASE = "https://jira.example.com"


def _task(key, summary, project, **kw):
    return DailyTaskCheck(
        issue_key=key,
        summary=summary,
        status=kw.pop("status", "In Progress"),
        assignee="ali",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key=project,
        **kw,
    )


class TestAnswerTaskQuestionUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for AnswerTaskQuestionUseCase."""

    def setUp(self):
        self.ai_service = AsyncMock()
        self.use_case = AnswerTaskQuestionUseCase(
            ai_service=self.ai_service,
            prompt_catalog=AsyncMock(),
            base_url=f"{BASE}/",
        )
        self.tasks = [
            _task("PARSCHAT-1", "درگاه پرداخت", "PARSCHAT"),
            _task("AK-2", "کار شخصی", "AK"),
        ]

    async def test_base_url_is_passed_without_trailing_slash(self):
        """The prompt gets a clean base so links are not doubled up."""
        self.ai_service.run.return_value = {"answer": "ok"}

        await self.use_case.execute("چه تسکی دارم؟", self.tasks)

        self.assertEqual(self.ai_service.run.call_args[0][1]["base_url"], BASE)

    async def test_every_task_and_project_reaches_the_model(self):
        """Filtering happens in the answer, so the model must see them all."""
        self.ai_service.run.return_value = {"answer": "ok"}

        await self.use_case.execute("...", self.tasks)

        rendered = self.ai_service.run.call_args[0][1]["tasks"]
        self.assertIn("PARSCHAT-1", rendered)
        self.assertIn("project=PARSCHAT", rendered)
        self.assertIn("project=AK", rendered)

    async def test_optional_fields_are_rendered_when_present(self):
        """Dates and blockers are available for timing questions."""
        self.ai_service.run.return_value = {"answer": "ok"}
        task = _task(
            "PARSCHAT-9", "کار", "PARSCHAT",
            target_end=datetime(2026, 9, 1),
            dependencies=["PARSCHAT-8"],
        )

        await self.use_case.execute("...", [task])

        rendered = self.ai_service.run.call_args[0][1]["tasks"]
        self.assertIn("due=2026-09-01", rendered)
        self.assertIn("blocked_by=PARSCHAT-8", rendered)

    async def test_no_tasks_is_stated_explicitly(self):
        """An empty list is described, not sent as a blank block."""
        self.ai_service.run.return_value = {"answer": "ok"}

        await self.use_case.execute("...", [])

        self.assertIn(
            "no open tasks", self.ai_service.run.call_args[0][1]["tasks"],
        )

    async def test_failure_returns_empty_string(self):
        """A failed call yields nothing, so the caller can say so."""
        self.ai_service.run.side_effect = Exception("openai down")

        self.assertEqual(await self.use_case.execute("...", self.tasks), "")


if __name__ == "__main__":
    unittest.main()
