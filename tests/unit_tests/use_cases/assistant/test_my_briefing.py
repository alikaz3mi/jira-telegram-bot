"""A briefing leads with what is on fire, then why the sprint exists.

A bare list of issue keys makes somebody reconstruct the point of their own
sprint, and buries an urgent bug among routine backlog. Order is the
feature: urgent bugs, then the sprint's purpose, then their own share.
"""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.assistant_entities import UserRole
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext
from jira_telegram_bot.use_cases.assistant.assistant_tools import (
    AssistantTools,
    EPIC_LINK_FIELD,
)


def _task(key, project="PARSCHAT", sprint="S-1", status="In Progress"):
    return DailyTaskCheck(
        issue_key=key, summary=f"کار {key}", status=status,
        assignee="z_lotfian", check_status=TaskCheckStatus.IN_PROGRESS,
        project_key=project, sprint_name=sprint,
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


def _story(key, epic):
    issue = Mock()
    issue.key = key
    issue.fields.summary = f"استوری {key}"
    issue.fields.status.name = "Backlog"
    setattr(issue.fields, EPIC_LINK_FIELD, Mock(value=epic))
    return issue


class TestMyBriefing(unittest.IsolatedAsyncioTestCase):
    """The shape of the answer when somebody asks what they should do."""

    def setUp(self):
        self.bugs = [_bug("PARSCHAT-764", attachments=[_file("shot.png")])]
        self.stories = [_story("PARSCHAT-11", "PARSCHAT-5691")]

        self.repo = Mock()
        self.repo.search_issues = Mock(side_effect=self._search)
        epic = Mock()
        epic.fields.summary = "سهمیه‌بندی چندگانه"
        self.repo.get_issue = Mock(return_value=epic)

        self.tasks = AsyncMock()
        self.tasks.execute.return_value = [_task("PARSCHAT-5840")]
        self.aliases = Mock()
        self.sink = []

    def _search(self, jql, **kwargs):
        return self.bugs if "issuetype = Bug" in jql else self.stories

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

        self.assertLess(result.index("PARSCHAT-764"), result.index("سهمیه"))

    async def test_the_sprint_purpose_is_stated_before_the_task_list(self):
        result = await self._tools().my_briefing()

        self.assertLess(result.index("سهمیه"), result.index("PARSCHAT-5840"))

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

    async def test_the_sprint_shown_is_where_their_commitments_are(self):
        """Counting all open work picks the biggest backlog, not the sprint."""
        self.tasks.execute.return_value = [
            _task("A-1", project="BACKLOGGY", sprint=None),
            _task("A-2", project="BACKLOGGY", sprint=None),
            _task("A-3", project="BACKLOGGY", sprint=None),
            _task("B-1", project="PARSCHAT", sprint="S-1"),
        ]

        await self._tools().my_briefing()

        story_jql = self.repo.search_issues.call_args_list[-1].kwargs["jql"]
        self.assertIn("PARSCHAT", story_jql)

    async def test_a_person_with_nothing_open_is_told_so(self):
        self.tasks.execute.return_value = []
        self.bugs = []

        result = await self._tools().my_briefing()

        self.assertIn("تسک بازی روی شما نیست", result)

    async def test_a_jira_failure_does_not_sink_the_whole_briefing(self):
        self.repo.search_issues.side_effect = Exception("504")

        result = await self._tools().my_briefing()

        self.assertIn("PARSCHAT-5840", result)

    async def test_issue_keys_are_linked(self):
        result = await self._tools().my_briefing()

        self.assertIn(
            '<a href="https://jira.example.com/browse/PARSCHAT-764"', result,
        )


if __name__ == "__main__":
    unittest.main()
