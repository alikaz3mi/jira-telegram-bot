"""A briefing answers "what should I do?" per project, framed by releases.

Asked without naming a project, the old briefing picked the single busiest
one and listed issue keys under it. Someone carrying work in three products
got one product's list and no way to tell it was partial — and nothing in it
carried a date, because a date lives on a release, not on a task.

So the order is the feature: urgent bugs first, then each project in turn,
and inside a project the release asking most of them, the tasks due soonest,
and a link to the rest.
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.assistant_entities import UserRole
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext
from jira_telegram_bot.use_cases.assistant.assistant_tools import AssistantTools


def _task(key, project="PARSCHAT", sprint="S-1", status="In Progress",
          target_end=None):
    return DailyTaskCheck(
        issue_key=key, summary=f"کار {key}", status=status,
        assignee="z_lotfian", check_status=TaskCheckStatus.IN_PROGRESS,
        project_key=project, sprint_name=sprint, target_end=target_end,
    )


def _bug(key, priority="Highest", status="Backlog", attachments=()):
    bug = Mock()
    bug.key = key
    bug.fields.summary = f"باگ {key}"
    bug.fields.status.name = status
    bug.fields.priority.name = priority
    bug.fields.attachment = list(attachments)
    return bug


def _file(name, mime="image/png"):
    item = Mock()
    item.filename = name
    item.mimeType = mime
    return item


def _named(name):
    """A mock whose ``.name`` is the string — ``Mock(name=...)`` is not."""
    version = Mock()
    version.name = name
    return version


def _issue(key, versions=()):
    """An issue as the release-grouping query returns it."""
    issue = Mock()
    issue.key = key
    issue.fields.summary = f"کار {key}"
    issue.fields.fixVersions = [_named(name) for name in versions]
    return issue


def _version(name, release_date=None, released=False):
    version = Mock()
    version.name = name
    version.releaseDate = release_date
    version.released = released
    return version


def _alias(display):
    resolution = Mock()
    resolution.resolved = Mock(display_name=display, canonical="PARSCHAT")
    return resolution


class TestMyBriefing(unittest.IsolatedAsyncioTestCase):
    """The shape of the answer when somebody asks what they should do."""

    def setUp(self):
        self.bugs = [_bug("PARSCHAT-764", attachments=[_file("shot.png")])]
        self.owned = [_issue("PARSCHAT-5840", versions=["پلن‌ها و سهمیه‌بندی"])]
        self.versions = [
            _version("پلن‌ها و سهمیه‌بندی", "2026-09-15"),
        ]

        self.repo = Mock()
        self.repo.search_issues = Mock(side_effect=self._search)
        self.repo.get_project_versions = Mock(
            side_effect=lambda key: self.versions,
        )

        self.tasks = AsyncMock()
        self.tasks.execute.return_value = [_task("PARSCHAT-5840")]
        self.aliases = Mock()
        self.aliases.resolve = Mock(return_value=_alias("پارس‌چت"))
        self.sink = []

    def _search(self, jql, **kwargs):
        return self.bugs if "issuetype = Bug" in jql else self.owned

    def _resolve_lotfian(self, name, kind):
        """Resolve «خانوم لطفیان» to her Jira name, projects to themselves."""
        resolution = Mock()
        resolution.is_ambiguous = False
        resolution.matches = []
        if "لطفیان" in str(name):
            resolution.resolved = Mock(
                display_name="خانم لطفیان", canonical="z_lotfian",
            )
        else:
            resolution.resolved = Mock(
                display_name="پارس‌چت", canonical="PARSCHAT",
            )
        return resolution

    def _tools(self, who="z_lotfian"):
        return AssistantTools(
            context=AssistantContext(
                jira_username=who, telegram_username=who, role=UserRole.CTO,
            ),
            get_user_daily_tasks_use_case=self.tasks,
            alias_repository=self.aliases,
            base_url="https://jira.example.com",
            task_manager_repository=self.repo,
            user_config_repository=Mock(),
            media_sink=self.sink,
        )

    async def test_urgent_bugs_come_first(self):
        result = await self._tools().my_briefing()

        self.assertLess(result.index("PARSCHAT-764"), result.index("پروژه"))

    async def test_every_project_the_person_touches_is_covered(self):
        """The old briefing showed one project and gave no sign of the rest."""
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", project="PARSCHAT"),
            _task("FOLLOWUP-1", project="FOLLOWUP"),
        ]

        result = await self._tools().my_briefing()

        self.assertIn("PARSCHAT-1", result)
        self.assertIn("FOLLOWUP-1", result)

    async def test_projects_are_ordered_by_sprint_commitment(self):
        """A big backlog is not the same as a promise for this fortnight."""
        self.tasks.execute.return_value = [
            _task("BACK-1", project="BACKLOGGY", sprint=None),
            _task("BACK-2", project="BACKLOGGY", sprint=None),
            _task("BACK-3", project="BACKLOGGY", sprint=None),
            _task("PARSCHAT-1", project="PARSCHAT", sprint="S-1"),
        ]

        result = await self._tools().my_briefing()

        self.assertLess(result.index("PARSCHAT-1"), result.index("BACK-1"))

    async def test_the_release_and_its_delivery_date_are_named(self):
        result = await self._tools().my_briefing()

        self.assertIn("پلن‌ها و سهمیه‌بندی", result)
        self.assertIn("۲۴ شهریور", result)

    async def test_the_soonest_release_leads(self):
        """Which release is asking for something first is the whole point."""
        self.owned = [
            _issue("PARSCHAT-1", versions=["دیرتر"]),
            _issue("PARSCHAT-2", versions=["زودتر"]),
        ]
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1"), _task("PARSCHAT-2"),
        ]
        self.versions = [
            _version("دیرتر", "2026-11-20"),
            _version("زودتر", "2026-09-15"),
        ]

        result = await self._tools().my_briefing()

        self.assertLess(result.index("زودتر"), result.index("دیرتر"))

    async def test_the_number_of_releases_the_work_spans_is_stated(self):
        self.owned = [
            _issue("PARSCHAT-1", versions=["الف"]),
            _issue("PARSCHAT-2", versions=["ب"]),
            _issue("PARSCHAT-3", versions=["ج"]),
        ]
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1"), _task("PARSCHAT-2"), _task("PARSCHAT-3"),
        ]
        self.versions = [
            _version("الف", "2026-09-15"),
            _version("ب", "2026-10-01"),
            _version("ج", "2026-11-01"),
        ]

        result = await self._tools().my_briefing()

        self.assertIn("۳ ریلیز".replace("۳", "3"), result.replace("۳", "3"))

    async def test_tasks_are_ordered_by_their_committed_date(self):
        self.tasks.execute.return_value = [
            _task("PARSCHAT-LATE", target_end=datetime(2026, 10, 30)),
            _task("PARSCHAT-SOON", target_end=datetime(2026, 9, 3)),
        ]

        result = await self._tools().my_briefing()

        self.assertLess(
            result.index("PARSCHAT-SOON"), result.index("PARSCHAT-LATE"),
        )

    async def test_a_dated_task_outranks_an_undated_one(self):
        """An absent Target end must not silently sort ahead of a real date.

        The dated task is what "due soonest" means, so an undated one does
        not appear in that section at all while a dated one exists — it is
        still reachable through the link to the rest of the project.
        """
        self.tasks.execute.return_value = [
            _task("PARSCHAT-NODATE", target_end=None),
            _task("PARSCHAT-DATED", target_end=datetime(2026, 9, 3)),
        ]

        result = await self._tools().my_briefing()

        due = result.split("نزدیک‌ترین تسک‌ها برای تحویل")[1]
        self.assertIn("PARSCHAT-DATED", due)
        self.assertNotIn("PARSCHAT-NODATE", due)

    async def test_undated_tasks_still_show_when_nothing_carries_a_date(self):
        """A project where nobody sets dates must not render an empty list."""
        self.tasks.execute.return_value = [_task("PARSCHAT-NODATE")]

        result = await self._tools().my_briefing()

        self.assertIn("PARSCHAT-NODATE", result)

    async def test_the_deadline_is_shown_next_to_the_task(self):
        """Dates are spoken in Jalali — nobody here plans in Gregorian."""
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", target_end=datetime(2026, 9, 3)),
        ]

        result = await self._tools().my_briefing()

        self.assertIn("۱۲ شهریور", result)
        self.assertNotIn("2026-09-03", result)

    async def test_an_unparsable_date_is_left_alone_rather_than_guessed(self):
        self.versions = [_version("پلن‌ها و سهمیه‌بندی", "not-a-date")]

        result = await self._tools().my_briefing()

        self.assertIn("not-a-date", result)

    async def test_a_link_to_the_rest_of_the_project_is_offered(self):
        result = await self._tools().my_briefing()

        self.assertIn("issues/?jql=", result)
        self.assertIn("همه تسک‌های پارس‌چت", result)

    async def test_the_project_is_named_the_way_a_person_says_it(self):
        result = await self._tools().my_briefing()

        self.assertIn("پارس‌چت", result)

    async def test_release_grouping_asks_only_for_the_callers_own_issues(self):
        await self._tools().my_briefing()

        jqls = [call.kwargs["jql"] for call in self.repo.search_issues.call_args_list]
        grouping = [jql for jql in jqls if "fixVersion" not in jql
                    and "issuetype = Bug" not in jql]
        self.assertTrue(grouping)
        self.assertIn('assignee = "z_lotfian"', grouping[0])

    async def test_only_the_callers_own_bugs_are_urgent(self):
        await self._tools().my_briefing()

        jql = self.repo.search_issues.call_args_list[0].kwargs["jql"]
        self.assertIn('assignee = "z_lotfian"', jql)

    async def test_finished_work_is_never_called_urgent(self):
        """Cancel sits in the Done category without setting a resolution."""
        await self._tools().my_briefing()

        jql = self.repo.search_issues.call_args_list[0].kwargs["jql"]
        self.assertIn("statusCategory != Done", jql)

    async def test_only_interrupting_priorities_qualify(self):
        await self._tools().my_briefing()

        jql = self.repo.search_issues.call_args_list[0].kwargs["jql"]
        self.assertIn("Highest", jql)
        self.assertNotIn("Medium", jql)

    async def test_a_screenshot_is_queued_for_sending(self):
        """A link behind Jira's login is not something anyone glances at."""
        await self._tools().my_briefing()

        self.assertEqual(len(self.sink), 1)
        self.assertEqual(self.sink[0]["filename"], "shot.png")
        self.assertEqual(self.sink[0]["issue_key"], "PARSCHAT-764")

    async def test_non_media_attachments_are_not_queued(self):
        self.bugs = [_bug("PARSCHAT-764", attachments=[
            _file("spec.pdf", "application/pdf"),
        ])]

        await self._tools().my_briefing()

        self.assertEqual(self.sink, [])

    async def test_cancelled_work_is_left_out_of_the_persons_share(self):
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", status="Cancel"),
            _task("PARSCHAT-2", status="In Progress"),
        ]

        result = await self._tools().my_briefing()

        self.assertNotIn("PARSCHAT-1", result)
        self.assertIn("PARSCHAT-2", result)

    async def test_a_person_with_nothing_open_is_told_so(self):
        self.tasks.execute.return_value = []
        self.bugs = []

        result = await self._tools().my_briefing()

        self.assertIn("تسک بازی روی شما نیست", result)

    async def test_a_jira_failure_does_not_sink_the_whole_briefing(self):
        """Losing releases costs the framing, never the list of work."""
        self.repo.search_issues.side_effect = Exception("504")
        self.repo.get_project_versions.side_effect = Exception("504")

        result = await self._tools().my_briefing()

        self.assertIn("PARSCHAT-5840", result)

    async def test_a_release_without_a_date_is_still_named(self):
        self.versions = [_version("پلن‌ها و سهمیه‌بندی", None)]

        result = await self._tools().my_briefing()

        self.assertIn("پلن‌ها و سهمیه‌بندی", result)
        self.assertIn("PARSCHAT-5840", result)

    async def test_the_title_carries_the_link_not_the_key(self):
        """A bare issue key is not what anyone recognises a task by."""
        self.tasks.execute.return_value = [_task("PARSCHAT-5840")]

        result = await self._tools().my_briefing()

        self.assertIn(
            '<a href="https://jira.example.com/browse/PARSCHAT-5840">'
            'کار PARSCHAT-5840</a>',
            result,
        )

    async def test_the_key_still_appears_beside_the_status(self):
        """Moving the link onto the title must not lose the key entirely."""
        result = await self._tools().my_briefing()

        detail = [
            line for line in result.split("\n")
            if "In Progress" in line
        ]
        self.assertTrue(detail)
        self.assertIn("PARSCHAT-5840", detail[0])

    async def test_no_markdown_emphasis_is_emitted(self):
        """The reply is sent as HTML, so an asterisk renders as an asterisk."""
        result = await self._tools().my_briefing()

        self.assertNotIn("**", result)
        self.assertIn("<b>", result)

    async def test_a_summary_with_html_characters_cannot_break_the_message(self):
        """Telegram rejects the whole message on a stray angle bracket."""
        self.tasks.execute.return_value = [
            DailyTaskCheck(
                issue_key="PARSCHAT-1", summary="A & B <script> C",
                status="Review", assignee="z_lotfian",
                check_status=TaskCheckStatus.IN_PROGRESS,
                project_key="PARSCHAT", sprint_name="S-1",
            ),
        ]

        result = await self._tools().my_briefing()

        self.assertIn("A &amp; B &lt;script&gt; C", result)
        self.assertNotIn("<script>", result)

    async def test_a_release_name_with_an_ampersand_is_escaped(self):
        self.owned = [_issue("PARSCHAT-5840", versions=["R & D"])]
        self.versions = [_version("R & D", "2026-09-15")]

        result = await self._tools().my_briefing()

        self.assertIn("R &amp; D", result)

    async def test_a_status_carries_an_icon(self):
        """The stage should read before the word does."""
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", status="Review"),
        ]

        result = await self._tools().my_briefing()

        self.assertIn("🟣 Review", result)

    async def test_a_colleague_gets_the_same_release_framing(self):
        """Asked about someone else, the old answer fell back to a bare list."""
        self.aliases.resolve = Mock(side_effect=self._resolve_lotfian)

        result = await self._tools(who="a_kazemi").my_briefing(
            person="خانوم لطفیان",
        )

        self.assertIn("پلن‌ها و سهمیه‌بندی", result)
        self.assertIn("۲۴ شهریور", result)

    async def test_a_colleagues_briefing_reads_about_them_not_you(self):
        self.aliases.resolve = Mock(side_effect=self._resolve_lotfian)

        result = await self._tools(who="a_kazemi").my_briefing(
            person="خانوم لطفیان",
        )

        self.assertIn("خانم لطفیان", result)
        self.assertNotIn("روی شما", result)

    async def test_a_colleagues_work_is_read_under_their_name(self):
        """A briefing about someone else must not query the caller."""
        self.aliases.resolve = Mock(side_effect=self._resolve_lotfian)

        await self._tools(who="a_kazemi").my_briefing(person="خانوم لطفیان")

        for call in self.repo.search_issues.call_args_list:
            self.assertIn('assignee = "z_lotfian"', call.kwargs["jql"])
        self.tasks.execute.assert_awaited_with(jira_username="z_lotfian")

    async def test_an_unreadable_person_is_refused_not_guessed(self):
        resolution = Mock()
        resolution.resolved = None
        resolution.is_ambiguous = False
        resolution.matches = []
        self.aliases.resolve = Mock(return_value=resolution)

        result = await self._tools().my_briefing(person="کسی که نیست")

        self.assertIn("پیدا نکردم", result)
        self.tasks.execute.assert_not_awaited()

    async def test_a_time_window_narrows_what_is_listed(self):
        self.tasks.execute.return_value = [
            _task("PARSCHAT-SOON", target_end=datetime.now() + timedelta(days=2)),
            _task("PARSCHAT-LATER", target_end=datetime.now() + timedelta(days=40)),
        ]

        result = await self._tools().my_briefing(within_days=7)

        self.assertIn("PARSCHAT-SOON", result)
        self.assertNotIn("PARSCHAT-LATER", result)

    async def test_a_window_says_it_is_a_window(self):
        """A filtered list headed "due soonest" reads as the whole picture."""
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", target_end=datetime.now() + timedelta(days=2)),
        ]

        result = await self._tools().my_briefing(within_days=7)

        self.assertIn("۷ روز آینده", result)

    async def test_a_window_never_shrinks_the_totals(self):
        """Four of twenty-nine tasks must not be reported as all of them."""
        self.owned = [
            _issue(f"PARSCHAT-{n}", versions=["پلن‌ها و سهمیه‌بندی"])
            for n in range(1, 6)
        ]
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", target_end=datetime.now() + timedelta(days=2)),
        ] + [
            _task(f"PARSCHAT-{n}", target_end=datetime.now() + timedelta(days=40))
            for n in range(2, 6)
        ]

        result = await self._tools().my_briefing(within_days=7)

        self.assertIn("در مجموع ۵ تسک باز", result)

    async def test_a_window_with_nothing_in_it_says_so(self):
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", target_end=datetime.now() + timedelta(days=40)),
        ]

        result = await self._tools().my_briefing(within_days=7)

        self.assertIn("مهلتی در این پروژه ندارید", result)
        self.assertNotIn("PARSCHAT-1 —", result)

    async def test_naming_a_project_narrows_the_briefing_to_it(self):
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", project="PARSCHAT"),
            _task("FOLLOWUP-1", project="FOLLOWUP"),
        ]

        result = await self._tools().my_briefing(project="پارسچت")

        self.assertIn("PARSCHAT-1", result)
        self.assertNotIn("FOLLOWUP-1", result)


if __name__ == "__main__":
    unittest.main()
