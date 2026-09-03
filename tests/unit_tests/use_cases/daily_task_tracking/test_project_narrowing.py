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


class TestAudienceIsNotAProject(unittest.IsolatedAsyncioTestCase):
    """A team named as who the work was for is not the board it lives on.

    Reported: "توی برد خودم ینی علی کاظمی ... یکی روی تسک توضیح وظایف به تیم
    پارسچت" narrowed to PARSCHAT's 24 issues, because the scanner found
    «پارسچت» inside the description of the work and preferred it for being
    the longest match. The user had said, in the same sentence, that the
    tasks were on their own board — and AK-13, the issue they meant, was
    never shown to the model at all.
    """

    def setUp(self):
        aliases = []
        for written in ("پارسچت", "AK", "alikaz3mi"):
            entry = Mock()
            entry.alias = written
            aliases.append(entry)
        self.repository = Mock()
        self.repository.all_of.return_value = aliases

        self.use_case = ParseWorklogReportUseCase(
            ai_service=AsyncMock(),
            prompt_catalog=Mock(),
            alias_repository=self.repository,
        )

    def test_a_team_the_work_was_for_does_not_narrow(self):
        spoken = self.use_case._spoken_project(
            "دیروز روی تسک توضیح وظایف به تیم پارسچت کار کردم",
        )

        self.assertIsNone(spoken)

    def test_the_reported_message_does_not_narrow_to_parschat(self):
        spoken = self.use_case._spoken_project(
            "من میخوام برای تسکهایی که توی برد خودم ینی علی کاظمی هست تایم "
            "ثبت کنم. دیروز من یکی روی تسک توضیح وظایف به تیم پارسچت تایم "
            "گذاشتم",
        )

        self.assertIsNone(spoken)

    def test_a_project_the_work_is_on_still_narrows(self):
        """The fix must not cost the case narrowing was built for."""
        spoken = self.use_case._spoken_project("برای پارسچت ۴ ساعت وقت گذاشتم")

        self.assertEqual(spoken, "پارسچت")

    def test_the_project_named_first_wins(self):
        """The board is stated before the work is described."""
        spoken = self.use_case._spoken_project(
            "توی AK کار کردم روی گزارش تیم پارسچت",
        )

        self.assertEqual(spoken, "AK")

    def test_an_english_audience_marker_is_recognised(self):
        spoken = self.use_case._spoken_project(
            "explaining the tasks to the parschat team",
        )

        self.assertIsNone(spoken)


class TestRankingSeesWhatTheModelSaw(unittest.IsolatedAsyncioTestCase):
    """One report must not draw its splits from two different lists.

    Reported: the model chose from 24 narrowed candidates while the reranker
    ranked against all 30, so one split resolved to a PARSCHAT issue and the
    next to an AK issue — in a single report, from a single sentence.
    """

    def setUp(self):
        self.candidates = [
            _task("AK-13", "شرح وظایف تیم پارسچت", "AK"),
            _task("AK-16", "گزارش خودکار کلی", "AK"),
            _task("PARSCHAT-5807", "گیت سرویس بر پایه Plan DB", "PARSCHAT"),
        ]
        alias = Mock()
        alias.alias = "AK"
        self.aliases = Mock()
        self.aliases.all_of.return_value = [alias]
        self.aliases.resolve.return_value = Mock(
            resolved=Mock(canonical="AK", display_name="AK"),
        )

        self.ai = AsyncMock()
        self.ai.run.return_value = {
            "total_hours": 4,
            "project_hint": "AK",
            "splits": [{
                "hours": 4, "description": "شرح وظایف",
                "candidate_indices": [], "confidence": 0.2,
            }],
        }
        self.ranker = AsyncMock()
        self.catalog = AsyncMock()
        self.catalog.get_prompt.return_value = "prompt"

    async def test_ranking_is_confined_to_the_narrowed_list(self):
        self.ranker.execute.return_value = [(self.candidates[0], 0.7)]
        use_case = ParseWorklogReportUseCase(
            ai_service=self.ai, prompt_catalog=self.catalog,
            alias_repository=self.aliases,
            rank_candidates_use_case=self.ranker,
        )

        await use_case.execute("توی AK کار کردم", self.candidates)

        ranked_against = self.ranker.execute.await_args.args[1]
        self.assertEqual(
            [task.issue_key for task in ranked_against], ["AK-13", "AK-16"],
        )
