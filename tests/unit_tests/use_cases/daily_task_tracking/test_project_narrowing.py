"""A stated project must narrow what the model is allowed to pick from.

"برای پارسچت ۴ ساعت" once produced two buttons, both from the AK project,
while twenty real PARSCHAT issues sat in the candidate list unoffered. The
project the user named was parsed into `project_hint` and never used.

Filtering the model's answer afterwards is not enough: if it shortlisted only
out-of-project rows there is nothing left to keep. The list it sees is what
gets narrowed.
"""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.assistant_entities import EntityKind
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.parse_worklog_report_use_case import (
    ParseWorklogReportUseCase,
)


def _task(key, summary, project):
    return DailyTaskCheck(
        issue_key=key,
        summary=summary,
        status="In Progress",
        assignee="a_kazemi",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key=project,
    )


class TestProjectNarrowing(unittest.IsolatedAsyncioTestCase):
    """The named project decides which issues the model is shown."""

    def setUp(self):
        self.candidates = [
            _task("AK-13", "شرح وظایف تیم پارسچت", "AK"),
            _task("AK-16", "گزارش خودکار کلی", "AK"),
            _task("PARSCHAT-5636", "بهبود فیلترهای صفحه تاریخچه", "PARSCHAT"),
            _task("PARSCHAT-5980", "حذف فراخوانی os.getenv", "PARSCHAT"),
        ]

        alias = Mock()
        alias.alias = "پارسچت"
        self.aliases = Mock()
        self.aliases.all_of.return_value = [alias]
        self.aliases.resolve.return_value = Mock(
            resolved=Mock(canonical="PARSCHAT", display_name="ParsChat"),
        )

        self.ai = AsyncMock()
        self.ai.run.return_value = {
            "total_hours": 4,
            "project_hint": "پارس‌چت",
            "splits": [{
                "hours": 4,
                "description": "کار",
                "candidate_indices": [0, 1],
                "confidence": 0.9,
            }],
        }
        self.catalog = AsyncMock()
        self.catalog.get_prompt.return_value = "prompt"

        self.use_case = ParseWorklogReportUseCase(
            ai_service=self.ai,
            prompt_catalog=self.catalog,
            alias_repository=self.aliases,
        )

    def _shown_to_model(self):
        """The candidate block the model actually received."""
        return self.ai.run.call_args.args[1]["candidates"]

    async def test_named_project_hides_other_projects_from_the_model(self):
        await self.use_case.execute("برای پارسچت ۴ ساعت", self.candidates)

        shown = self._shown_to_model()
        self.assertIn("PARSCHAT-5636", shown)
        self.assertNotIn("AK-13", shown)

    async def test_indices_are_mapped_back_onto_the_full_list(self):
        """The caller confirms against the full list, so indices must match it."""
        self.ai.run.return_value["splits"][0]["candidate_indices"] = [0]

        report = await self.use_case.execute("برای پارسچت ۴ ساعت", self.candidates)

        self.assertEqual(report.splits[0].candidate_indices, [2])
        self.assertEqual(report.splits[0].issue_key, "PARSCHAT-5636")

    async def test_no_project_named_shows_everything(self):
        self.aliases.all_of.return_value = []

        await self.use_case.execute("۲ ساعت کار کردم", self.candidates)

        shown = self._shown_to_model()
        self.assertIn("AK-13", shown)
        self.assertIn("PARSCHAT-5636", shown)

    async def test_project_with_no_open_work_falls_back_to_everything(self):
        """No options at all is worse than a wider list."""
        only_ak = [self.candidates[0], self.candidates[1]]

        await self.use_case.execute("برای پارسچت ۴ ساعت", only_ak)

        self.assertIn("AK-13", self._shown_to_model())

    async def test_unresolvable_name_does_not_narrow(self):
        self.aliases.resolve.return_value = Mock(resolved=None)

        await self.use_case.execute("برای پارسچت ۴ ساعت", self.candidates)

        self.assertIn("AK-13", self._shown_to_model())

    async def test_alias_lookup_failure_is_survivable(self):
        self.aliases.all_of.side_effect = Exception("storage gone")

        report = await self.use_case.execute("برای پارسچت ۴ ساعت", self.candidates)

        self.assertIn("AK-13", self._shown_to_model())
        self.assertEqual(len(report.splits), 1)

    async def test_zero_width_non_joiner_still_matches(self):
        """«پارس‌چت» and «پارسچت» are the same word to a person."""
        await self.use_case.execute("برای پارس‌چت ۴ ساعت", self.candidates)

        self.assertNotIn("AK-13", self._shown_to_model())

    async def test_the_alias_table_is_asked_for_projects_only(self):
        await self.use_case.execute("برای پارسچت ۴ ساعت", self.candidates)

        self.aliases.all_of.assert_called_with(EntityKind.PROJECT)


if __name__ == "__main__":
    unittest.main()
