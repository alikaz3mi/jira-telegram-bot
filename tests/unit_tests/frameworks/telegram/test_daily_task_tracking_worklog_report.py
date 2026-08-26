"""Unit tests for free-text worklog reporting in DailyTaskTrackingHandler."""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_intent import (
    ParsedWorklogReport,
    ParsedWorklogSplit,
    WorklogSplitStatus,
)
from jira_telegram_bot.frameworks.telegram.daily_task_tracking_handler import (
    DailyTaskTrackingHandler,
)
from jira_telegram_bot.use_cases.daily_task_tracking.classify_message_intent_use_case import (
    MessageIntent,
)
from jira_telegram_bot.use_cases.daily_task_tracking.confirm_worklog_report_use_case import (
    ConfirmWorklogReportUseCase,
)


def _task(key: str, summary: str) -> DailyTaskCheck:
    return DailyTaskCheck(
        issue_key=key,
        summary=summary,
        status="In Progress",
        assignee="ali",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key="PARSCHAT",
    )


def _split(hours, key=None, indices=(), status=WorklogSplitStatus.RESOLVED):
    return ParsedWorklogSplit(
        hours=hours,
        description="کار",
        candidate_indices=list(indices),
        confidence=0.95,
        issue_key=key,
        status=status,
    )


class _Message:
    """Minimal stand-in for a Telegram message."""

    def __init__(self, text=""):
        self.text = text
        self.chat_id = 42
        self.sent = []
        self.reply_markup = None

    async def reply_text(self, text, reply_markup=None):
        notice = _Message()
        notice.sent.append(text)
        return notice

    async def edit_text(self, text, reply_markup=None):
        self.sent.append(text)
        self.reply_markup = reply_markup
        return self


class TestWorklogReportFlow(unittest.IsolatedAsyncioTestCase):
    """Tests for the free-text report path through the handler."""

    def setUp(self):
        self.candidates = [
            _task("PARSCHAT-1", "درگاه بانک پارسیان"),
            _task("PARSCHAT-2", "رفع باگ فرانت"),
        ]
        self.parse = AsyncMock()
        self.tasks = AsyncMock()
        self.tasks.execute.return_value = self.candidates
        self.record_worklog = AsyncMock()
        self.classify = AsyncMock()
        self.classify.execute.return_value = MessageIntent.WORKLOG
        self.answer = AsyncMock()

        self.user_config = Mock()
        self.user_config.get_user_config.return_value = Mock(jira_username="ali")

        self.handler = DailyTaskTrackingHandler(
            record_delay_reason_use_case=AsyncMock(),
            record_time_spent_use_case=AsyncMock(),
            record_worklog_use_case=self.record_worklog,
            request_subtask_creation_use_case=AsyncMock(),
            user_config_repository=self.user_config,
            queue_manager=Mock(),
            parse_worklog_report_use_case=self.parse,
            confirm_worklog_report_use_case=ConfirmWorklogReportUseCase(),
            get_user_daily_tasks_use_case=self.tasks,
            classify_message_intent_use_case=self.classify,
            answer_task_question_use_case=self.answer,
        )
        self.context = Mock()
        self.context.user_data = {}

    def _update(self, text):
        update = Mock()
        update.message = _Message(text)
        update.effective_user.username = "ali_tg"
        return update

    def _query(self, data=""):
        query = Mock()
        query.data = data
        query.message = _Message()
        query.from_user.username = "ali_tg"
        query.edit_message_text = AsyncMock(side_effect=query.message.edit_text)
        return query

    async def test_clear_report_offers_confirmation(self):
        """A fully resolved report goes straight to one confirm step."""
        self.parse.execute.return_value = ParsedWorklogReport(
            raw_text="...", total_hours=5,
            splits=[_split(3, "PARSCHAT-1"), _split(2, "PARSCHAT-2")],
        )

        update = self._update("امروز ۵ ساعت کار کردم")
        await self.handler._handle_worklog_report(update, self.context)

        pending = self.context.user_data[self.handler.PENDING_REPORT]
        self.assertEqual(len(pending["report"].splits), 2)
        self.assertEqual(len(pending["candidate_objects"]), 2)

    async def test_confirm_writes_one_worklog_per_split(self):
        """Confirming logs each split separately against its own issue."""
        self.context.user_data[self.handler.PENDING_REPORT] = {
            "report": ParsedWorklogReport(
                raw_text="...",
                splits=[_split(3, "PARSCHAT-1"), _split(2, "PARSCHAT-2")],
            ),
            "candidates": {"PARSCHAT-1": "a", "PARSCHAT-2": "b"},
            "candidate_objects": self.candidates,
        }

        await self.handler._handle_worklog_confirm(self._query(), self.context)

        self.assertEqual(self.record_worklog.execute.await_count, 2)
        logged = {
            call.kwargs["issue_key"]: call.kwargs["hours"]
            for call in self.record_worklog.execute.await_args_list
        }
        self.assertEqual(logged, {"PARSCHAT-1": 3, "PARSCHAT-2": 2})

    async def test_cancel_writes_nothing(self):
        """Cancelling clears the pending report without touching Jira."""
        self.context.user_data[self.handler.PENDING_REPORT] = {"report": None}
        query = self._query("wlcancel")
        query.answer = AsyncMock()

        update = Mock()
        update.callback_query = query
        await self.handler.handle_callback(update, self.context)

        self.assertNotIn(self.handler.PENDING_REPORT, self.context.user_data)
        self.record_worklog.execute.assert_not_awaited()

    async def test_pick_resolves_split_then_confirms(self):
        """Answering the question resolves that split and moves on."""
        report = ParsedWorklogReport(
            raw_text="...",
            splits=[_split(2, None, (0, 1), WorklogSplitStatus.AMBIGUOUS)],
        )
        self.context.user_data[self.handler.PENDING_REPORT] = {
            "report": report,
            "candidates": {t.issue_key: t.summary for t in self.candidates},
            "candidate_objects": self.candidates,
        }

        await self.handler._handle_worklog_pick(
            self._query(), self.context, "wlpick_0_PARSCHAT-2",
        )

        self.assertEqual(report.splits[0].issue_key, "PARSCHAT-2")
        self.assertIs(report.splits[0].status, WorklogSplitStatus.RESOLVED)

    async def test_skip_drops_the_split(self):
        """Skipping removes that piece of work rather than logging it."""
        report = ParsedWorklogReport(
            raw_text="...",
            splits=[_split(2, None, (0,), WorklogSplitStatus.AMBIGUOUS)],
        )
        self.context.user_data[self.handler.PENDING_REPORT] = {
            "report": report,
            "candidates": {},
            "candidate_objects": self.candidates,
        }

        await self.handler._handle_worklog_pick(
            self._query(), self.context, "wlpick_0_skip",
        )

        self.assertEqual(report.splits, [])
        self.assertNotIn(self.handler.PENDING_REPORT, self.context.user_data)

    async def test_no_open_tasks_is_reported(self):
        """A user with no open issues is told, not left waiting."""
        self.tasks.execute.return_value = []

        await self.handler._handle_worklog_report(
            self._update("۳ ساعت کار کردم"), self.context,
        )

        self.parse.execute.assert_not_called()
        self.assertNotIn(self.handler.PENDING_REPORT, self.context.user_data)

    async def test_unparseable_text_does_not_create_pending(self):
        """Chatter that yields no splits is not turned into a worklog."""
        self.parse.execute.return_value = ParsedWorklogReport(
            raw_text="سلام", splits=[],
        )

        await self.handler._handle_worklog_report(
            self._update("سلام"), self.context,
        )

        self.assertNotIn(self.handler.PENDING_REPORT, self.context.user_data)

    async def test_custom_hours_state_is_not_hijacked(self):
        """Text answering an existing prompt still goes to that prompt."""
        self.context.user_data["state"] = self.handler.WAITING_CUSTOM_HOURS
        self.handler._handle_custom_hours = AsyncMock()

        await self.handler.handle_text_message(self._update("3"), self.context)

        self.handler._handle_custom_hours.assert_awaited_once()
        self.parse.execute.assert_not_called()

    async def test_failed_worklog_does_not_abort_the_rest(self):
        """One Jira failure is reported without losing the other entries."""
        self.record_worklog.execute.side_effect = [
            Exception("jira down"), Mock(),
        ]
        self.context.user_data[self.handler.PENDING_REPORT] = {
            "report": ParsedWorklogReport(
                raw_text="...",
                splits=[_split(3, "PARSCHAT-1"), _split(2, "PARSCHAT-2")],
            ),
            "candidates": {},
            "candidate_objects": self.candidates,
        }
        query = self._query()

        await self.handler._handle_worklog_confirm(query, self.context)

        self.assertEqual(self.record_worklog.execute.await_count, 2)
        self.assertIn("PARSCHAT-1", query.message.sent[-1])


    async def test_agent_is_preferred_over_the_single_shot_answerer(self):
        """When the tool-using agent is available it handles the question."""
        self.handler.task_assistant_agent = AsyncMock()
        self.handler.task_assistant_agent.answer.return_value = "دو تا داری"
        self.classify.execute.return_value = MessageIntent.QUESTION

        await self.handler._handle_free_text(
            self._update("تسکام چیه؟"), self.context,
        )

        self.handler.task_assistant_agent.answer.assert_awaited_once()
        self.answer.execute.assert_not_called()

    async def test_caller_identity_is_bound_outside_the_model(self):
        """The agent is told who is asking; it cannot choose for itself."""
        self.handler.task_assistant_agent = AsyncMock()
        self.handler.task_assistant_agent.answer.return_value = "..."
        self.classify.execute.return_value = MessageIntent.QUESTION

        await self.handler._handle_free_text(
            self._update("تسک زهرا چیه؟"), self.context,
        )

        ctx = self.handler.task_assistant_agent.answer.call_args.kwargs["context"]
        self.assertEqual(ctx.jira_username, "ali")

    def test_unknown_role_falls_back_to_member(self):
        """A bad role must not widen access or break the assistant."""
        from jira_telegram_bot.entities.assistant_entities import UserRole

        for raw in ["typo", None, "", 42]:
            self.assertIs(
                self.handler._role_of(Mock(assistant_role=raw)),
                UserRole.MEMBER,
            )

    def test_configured_role_is_honoured(self):
        """A valid role is read as written, case and spacing aside."""
        from jira_telegram_bot.entities.assistant_entities import UserRole

        self.assertIs(
            self.handler._role_of(Mock(assistant_role=" CTO ")), UserRole.CTO,
        )

    async def test_question_is_answered_not_logged(self):
        """A question about tasks is answered instead of parsed for hours."""
        self.classify.execute.return_value = MessageIntent.QUESTION
        self.answer.execute.return_value = "این هفته PARSCHAT-1 را داری."

        await self.handler._handle_free_text(
            self._update("این هفته چه تسکی دارم؟"), self.context,
        )

        self.answer.execute.assert_awaited_once()
        self.parse.execute.assert_not_called()
        self.assertNotIn(self.handler.PENDING_REPORT, self.context.user_data)

    async def test_greeting_gets_help_not_a_worklog_error(self):
        """A greeting is answered with help, not "I didn't understand hours"."""
        self.classify.execute.return_value = MessageIntent.CHITCHAT

        await self.handler._handle_free_text(self._update("hello"), self.context)

        self.parse.execute.assert_not_called()
        self.answer.execute.assert_not_called()

    async def test_worklog_intent_still_reaches_the_parser(self):
        """Reporting time keeps going to the worklog flow."""
        self.classify.execute.return_value = MessageIntent.WORKLOG
        self.parse.execute.return_value = ParsedWorklogReport(
            raw_text="...", total_hours=3, splits=[_split(3, "PARSCHAT-1")],
        )

        await self.handler._handle_free_text(
            self._update("۳ ساعت کار کردم"), self.context,
        )

        self.parse.execute.assert_awaited_once()
        self.assertIn(self.handler.PENDING_REPORT, self.context.user_data)


    async def test_intent_without_detail_asks_instead_of_erroring(self):
        """"I want to log my time" gets a prompt for the missing detail."""
        self.classify.execute.return_value = MessageIntent.WORKLOG
        self.parse.execute.return_value = ParsedWorklogReport(
            raw_text="...", splits=[],
        )
        update = self._update("میخوام تایمی که کار کردم رو ثبت کنم")

        await self.handler._handle_free_text(update, self.context)

        self.assertNotIn(self.handler.PENDING_REPORT, self.context.user_data)
        self.assertTrue(self.handler._memory(self.context).turns)

    async def test_history_is_passed_to_the_parser(self):
        """A continuation is parsed together with what came before."""
        self.classify.execute.return_value = MessageIntent.WORKLOG
        self.parse.execute.return_value = ParsedWorklogReport(
            raw_text="...", splits=[],
        )
        self.handler._memory(self.context).remember("قبلی", "پاسخ قبلی")

        await self.handler._handle_free_text(
            self._update("۳ ساعت"), self.context,
        )

        self.assertIn(
            "پاسخ قبلی", self.parse.execute.call_args.kwargs["history"],
        )

    async def test_history_is_passed_to_the_answerer(self):
        """A follow-up question can see the previous answer."""
        self.classify.execute.return_value = MessageIntent.QUESTION
        self.answer.execute.return_value = "بله، همین دوتا."
        self.handler._memory(self.context).remember("تسکام؟", "دو تا داری")

        await self.handler._handle_free_text(
            self._update("فقط همین دوتاست؟"), self.context,
        )

        self.assertIn(
            "دو تا داری", self.answer.execute.call_args.kwargs["history"],
        )

    async def test_answers_are_remembered_for_the_next_turn(self):
        """Each exchange is recorded so the next message has context."""
        self.classify.execute.return_value = MessageIntent.QUESTION
        self.answer.execute.return_value = "دو تا تسک داری"

        await self.handler._handle_free_text(
            self._update("تسکام چیه؟"), self.context,
        )

        turns = self.handler._memory(self.context).turns
        self.assertEqual(turns[-1].user, "تسکام چیه؟")
        self.assertEqual(turns[-1].assistant, "دو تا تسک داری")


if __name__ == "__main__":
    unittest.main()
