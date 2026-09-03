"""Telegram handler for daily task tracking with Persian interface."""
from __future__ import annotations

import re
from datetime import date

from typing import TYPE_CHECKING
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, filters

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.constants import persian_messages
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    DelayReason,
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.record_delay_reason_use_case import (
    RecordDelayReasonUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.record_time_spent_use_case import (
    RecordTimeSpentUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.record_worklog_use_case import (
    RecordWorklogUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.request_subtask_creation_use_case import (
    RequestSubtaskCreationUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.parse_worklog_report_use_case import (
    ParseWorklogReportUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.confirm_worklog_report_use_case import (
    ConfirmWorklogReportUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.get_user_daily_tasks_use_case import (
    GetUserDailyTasksUseCase,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_intent import (
    WorklogSplitStatus,
)
from jira_telegram_bot.entities.daily_task_tracking.conversation_turn import (
    ConversationMemory,
)
from jira_telegram_bot.entities.assistant_entities import UserRole
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext
from jira_telegram_bot.use_cases.assistant.task_assistant_agent import (
    TaskAssistantAgent,
)
from jira_telegram_bot.use_cases.daily_task_tracking.classify_message_intent_use_case import (
    ClassifyMessageIntentUseCase,
    MessageIntent,
)
from jira_telegram_bot.use_cases.daily_task_tracking.answer_task_question_use_case import (
    AnswerTaskQuestionUseCase,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.use_cases.daily_task_tracking.build_daily_digest_use_case import (
    BuildDailyDigestUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.send_daily_task_reminders_use_case import (
    MAX_TASKS_PER_REMINDER,
)
from jira_telegram_bot.frameworks.telegram.daily_task_queue_manager import (
    DailyTaskQueueManager,
)

if TYPE_CHECKING:
    from jira_telegram_bot.use_cases.daily_task_tracking.send_daily_task_reminders_use_case import (
        SendDailyTaskRemindersUseCase,
    )


# A briefing with a dozen screenshots is a wall, not an answer.
MAX_MEDIA_PER_ANSWER = 4


class DailyTaskTrackingHandler:
    """Handler for daily task tracking conversations."""

    WAITING_CUSTOM_HOURS = "waiting_custom_hours"
    WAITING_CUSTOM_DELAY = "waiting_custom_delay"
    PENDING_REPORT = "pending_worklog_report"
    WAITING_ISSUE_KEY = "waiting_issue_key"
    MEMORY = "conversation_memory"

    def __init__(
        self,
        record_delay_reason_use_case: RecordDelayReasonUseCase,
        record_time_spent_use_case: RecordTimeSpentUseCase,
        record_worklog_use_case: RecordWorklogUseCase,
        request_subtask_creation_use_case: RequestSubtaskCreationUseCase,
        user_config_repository: UserConfigInterface,
        queue_manager: DailyTaskQueueManager,
        parse_worklog_report_use_case: ParseWorklogReportUseCase = None,
        confirm_worklog_report_use_case: ConfirmWorklogReportUseCase = None,
        get_user_daily_tasks_use_case: GetUserDailyTasksUseCase = None,
        classify_message_intent_use_case: ClassifyMessageIntentUseCase = None,
        answer_task_question_use_case: AnswerTaskQuestionUseCase = None,
        task_assistant_agent: TaskAssistantAgent = None,
        base_url: str = "",
    ):
        """Initialize the handler.

        Args:
            record_delay_reason_use_case: Use case for recording delay
            record_time_spent_use_case: Use case for recording time
            record_worklog_use_case: Use case for recording worklog
            request_subtask_creation_use_case: Use case for subtask requests
            user_config_repository: Repository for user config
            queue_manager: Task queue manager
            parse_worklog_report_use_case: Parses a free-text work report
            confirm_worklog_report_use_case: Decides what must be confirmed
            get_user_daily_tasks_use_case: Supplies the issues to match against
            classify_message_intent_use_case: Routes a message to the right flow
            answer_task_question_use_case: Answers questions about own tasks
            task_assistant_agent: Tool-using agent; preferred when available,
                since it can look up other people and count as well as list
            base_url: Jira base URL, used to hyperlink issue keys
        """
        self.record_delay = record_delay_reason_use_case
        self.record_time = record_time_spent_use_case
        self.record_worklog = record_worklog_use_case
        self.request_subtask = request_subtask_creation_use_case
        self.user_config_repository = user_config_repository
        self.queue_manager = queue_manager
        self.parse_worklog_report = parse_worklog_report_use_case
        self.confirm_worklog_report = confirm_worklog_report_use_case
        self.get_user_daily_tasks = get_user_daily_tasks_use_case
        self.classify_message_intent = classify_message_intent_use_case
        self.answer_task_question = answer_task_question_use_case
        self.task_assistant_agent = task_assistant_agent
        self.base_url = (base_url or "").rstrip("/")
        self.task_sender = None  # Will be set by SendDailyTaskRemindersUseCase
        # Also set by SendDailyTaskRemindersUseCase, which owns the bot the
        # reminder sends through.
        self.message_sender = None
        # Chat id -> the tasks a digest offered and how many may be asked
        # about, so a reply can be matched against what was actually shown.
        self.digest_sessions: dict = {}

    def create_delay_reason_keyboard(self) -> InlineKeyboardMarkup:
        """Create inline keyboard for delay reasons.

        Returns:
            Inline keyboard markup
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_WAITING_APPROVAL,
                    callback_data="delay_waiting_approval",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_TECHNICAL_BLOCKER,
                    callback_data="delay_technical_blocker",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_OTHER_PRIORITIES,
                    callback_data="delay_other_priorities",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_MISSING_REQUIREMENTS,
                    callback_data="delay_missing_requirements",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_DEPENDENCY_NOT_READY,
                    callback_data="delay_dependency_not_ready",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.DELAY_OTHER,
                    callback_data="delay_other",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.REQUEST_SUBTASKS,
                    callback_data="request_subtasks",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.SKIP_TASK,
                    callback_data="skip_task",
                ),
                InlineKeyboardButton(
                    persian_messages.FINISH_LATER,
                    callback_data="finish_later",
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_hours_keyboard(self, prefix: str = "hours") -> InlineKeyboardMarkup:
        """Create inline keyboard for hours selection.

        Args:
            prefix: Callback data prefix (hours or worklog)

        Returns:
            Inline keyboard markup
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    persian_messages.HOURS_1,
                    callback_data=f"{prefix}_1",
                ),
                InlineKeyboardButton(
                    persian_messages.HOURS_2,
                    callback_data=f"{prefix}_2",
                ),
            ],
            [
                InlineKeyboardButton(
                    persian_messages.HOURS_3,
                    callback_data=f"{prefix}_3",
                ),
                InlineKeyboardButton(
                    persian_messages.HOURS_4,
                    callback_data=f"{prefix}_4",
                ),
            ],
            [
                InlineKeyboardButton(
                    persian_messages.HOURS_6,
                    callback_data=f"{prefix}_6",
                ),
                InlineKeyboardButton(
                    persian_messages.HOURS_8,
                    callback_data=f"{prefix}_8",
                ),
            ],
            [
                InlineKeyboardButton(
                    persian_messages.HOURS_CUSTOM,
                    callback_data=f"{prefix}_custom",
                )
            ],
            [
                InlineKeyboardButton(
                    persian_messages.SKIP_TASK,
                    callback_data="skip_task",
                ),
                InlineKeyboardButton(
                    persian_messages.FINISH_LATER,
                    callback_data="finish_later",
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def handle_callback(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Handle callback query from inline keyboard.

        Args:
            update: Telegram update
            context: Callback context
        """
        query = update.callback_query
        await query.answer()
        
        data = query.data
        chat_id = query.message.chat_id
        
        LOGGER.info(f"Callback received: data='{data}', chat_id={chat_id}")
        
        try:
            if data.startswith("delay_"):
                LOGGER.info("Processing delay callback")
                await self._handle_delay_callback(query, context, data)
            elif data.startswith("hours_"):
                LOGGER.info("Processing hours callback")
                await self._handle_hours_callback(query, context, data)
            elif data.startswith("worklog_"):
                LOGGER.info("Processing worklog callback")
                await self._handle_worklog_callback(query, context, data)
            elif data == "request_subtasks":
                LOGGER.info("Processing subtask request")
                await self._handle_subtask_request(query, context)
            elif data.startswith("wlpick_"):
                LOGGER.info("Processing worklog disambiguation")
                await self._handle_worklog_pick(query, context, data)
            elif data == "wlconfirm":
                LOGGER.info("Processing worklog confirmation")
                await self._handle_worklog_confirm(query, context)
            elif data == "wlcancel":
                LOGGER.info("Processing worklog cancellation")
                context.user_data.pop(self.PENDING_REPORT, None)
                await query.edit_message_text(persian_messages.WORKLOG_CANCELLED)
            elif data == "skip_task":
                LOGGER.info("Processing skip task")
                await query.edit_message_text(persian_messages.TASK_SKIPPED)
                # Send next task
                await self._send_next_task_for_user(chat_id)
            elif data == "finish_later":
                LOGGER.info("Processing finish later")
                await query.edit_message_text(persian_messages.CHECK_PAUSED)
                self.queue_manager.clear_queue(chat_id)
            
        except Exception as e:
            LOGGER.error(f"Error handling callback: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ خطا در پردازش: {str(e)}"
            )

    async def _handle_delay_callback(
        self,
        query,
        context: CallbackContext,
        data: str,
    ) -> None:
        """Handle delay reason callback.

        Args:
            query: Callback query
            context: Callback context
            data: Callback data
        """
        if data == "delay_other":
            context.user_data["state"] = self.WAITING_CUSTOM_DELAY
            await query.edit_message_text(
                persian_messages.ENTER_CUSTOM_DELAY_REASON
            )
            return
        
        delay_mapping = {
            "delay_waiting_approval": DelayReason.WAITING_APPROVAL,
            "delay_technical_blocker": DelayReason.TECHNICAL_BLOCKER,
            "delay_other_priorities": DelayReason.OTHER_PRIORITIES,
            "delay_missing_requirements": DelayReason.MISSING_REQUIREMENTS,
            "delay_dependency_not_ready": DelayReason.DEPENDENCY_NOT_READY,
        }
        
        delay_reason = delay_mapping.get(data)
        
        if delay_reason:
            chat_id = query.message.chat_id
            queue = self.queue_manager.get_queue(chat_id)
            if not queue:
                await query.edit_message_text("❌ خطا: تسک یافت نشد")
                return
                
            task = queue.get_current()
            if not task:
                await query.edit_message_text("❌ خطا: تسک یافت نشد")
                return
            
            user_config = self.user_config_repository.get_user_config(
                query.from_user.username
            )
            
            if user_config:
                await self.record_delay.execute(
                    issue_key=task.issue_key,
                    jira_username=user_config.jira_username,
                    telegram_username=query.from_user.username,
                    delay_reason=delay_reason,
                )
                
                await query.edit_message_text(
                    persian_messages.DELAY_RECORDED
                )
                
                # Send next task
                await self._send_next_task_for_user(chat_id)

    async def _handle_hours_callback(
        self,
        query,
        context: CallbackContext,
        data: str,
    ) -> None:
        """Handle hours spent callback.

        Args:
            query: Callback query
            context: Callback context
            data: Callback data
        """
        if data == "hours_custom":
            context.user_data["state"] = self.WAITING_CUSTOM_HOURS
            context.user_data["hours_type"] = "progress"
            await query.edit_message_text(
                persian_messages.ENTER_CUSTOM_HOURS
            )
            return
        
        hours_str = data.split("_")[1]
        try:
            hours = float(hours_str)
        except ValueError:
            return
        
        chat_id = query.message.chat_id
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
            
        task = queue.get_current()
        if not task:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
        
        user_config = self.user_config_repository.get_user_config(
            query.from_user.username
        )
        
        if user_config:
            await self.record_time.execute(
                issue_key=task.issue_key,
                jira_username=user_config.jira_username,
                telegram_username=query.from_user.username,
                hours_spent=hours,
            )
            
            await query.edit_message_text(
                persian_messages.HOURS_RECORDED.format(hours)
            )
            
            # Send next task
            await self._send_next_task_for_user(chat_id)

    async def _handle_worklog_callback(
        self,
        query,
        context: CallbackContext,
        data: str,
    ) -> None:
        """Handle worklog callback.

        Args:
            query: Callback query
            context: Callback context
            data: Callback data
        """
        if data == "worklog_custom":
            context.user_data["state"] = self.WAITING_CUSTOM_HOURS
            context.user_data["hours_type"] = "worklog"
            await query.edit_message_text(
                persian_messages.ENTER_CUSTOM_HOURS
            )
            return
        
        hours_str = data.split("_")[1]
        try:
            hours = float(hours_str)
        except ValueError:
            return
        
        chat_id = query.message.chat_id
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
            
        task = queue.get_current()
        if not task:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
        
        user_config = self.user_config_repository.get_user_config(
            query.from_user.username
        )
        
        if user_config:
            await self.record_worklog.execute(
                issue_key=task.issue_key,
                jira_username=user_config.jira_username,
                telegram_username=query.from_user.username,
                hours=hours,
            )
            
            await query.edit_message_text(
                persian_messages.WORKLOG_RECORDED.format(hours)
            )
            
            # Send next task
            await self._send_next_task_for_user(chat_id)

    async def _handle_subtask_request(
        self,
        query,
        context: CallbackContext,
    ) -> None:
        """Handle subtask creation request.

        Args:
            query: Callback query
            context: Callback context
        """
        chat_id = query.message.chat_id
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
            
        task = queue.get_current()
        if not task:
            await query.edit_message_text("❌ خطا: تسک یافت نشد")
            return
        
        user_config = self.user_config_repository.get_user_config(
            query.from_user.username
        )
        
        if user_config:
            await self.request_subtask.execute(
                issue_key=task.issue_key,
                issue_summary=task.summary,
                project_key=task.project_key,
                jira_username=user_config.jira_username,
                telegram_username=query.from_user.username,
            )
            
            await query.edit_message_text(
                persian_messages.SUBTASK_REQUEST_SENT
            )

    async def handle_text_message(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Handle text message (for custom input).

        Args:
            update: Telegram update
            context: Callback context
        """
        state = context.user_data.get("state")
        
        if state == self.WAITING_CUSTOM_HOURS:
            await self._handle_custom_hours(update, context)
        elif state == self.WAITING_CUSTOM_DELAY:
            await self._handle_custom_delay(update, context)
        elif state == self.WAITING_ISSUE_KEY:
            await self._handle_typed_issue_key(update, context)
        else:
            await self._handle_free_text(update, context)

    async def _handle_custom_hours(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Handle custom hours input.

        Args:
            update: Telegram update
            context: Callback context
        """
        try:
            hours = float(update.message.text)
            
            if hours <= 0 or hours > 24:
                await update.message.reply_text(
                    persian_messages.ERROR_INVALID_HOURS
                )
                return
            
            chat_id = update.effective_chat.id
            queue = self.queue_manager.get_queue(chat_id)
            if not queue:
                await update.message.reply_text("❌ خطا: تسک یافت نشد")
                return
                
            task = queue.get_current()
            if not task:
                await update.message.reply_text("❌ خطا: تسک یافت نشد")
                return
            
            hours_type = context.user_data.get("hours_type", "progress")
            
            user_config = self.user_config_repository.get_user_config(
                update.effective_user.username
            )
            
            if user_config:
                if hours_type == "worklog":
                    await self.record_worklog.execute(
                        issue_key=task.issue_key,
                        jira_username=user_config.jira_username,
                        telegram_username=update.effective_user.username,
                        hours=hours,
                    )
                    await update.message.reply_text(
                        persian_messages.WORKLOG_RECORDED.format(hours)
                    )
                else:
                    await self.record_time.execute(
                        issue_key=task.issue_key,
                        jira_username=user_config.jira_username,
                        telegram_username=update.effective_user.username,
                        hours_spent=hours,
                    )
                    await update.message.reply_text(
                        persian_messages.HOURS_RECORDED.format(hours)
                    )
                
                context.user_data.pop("state", None)
                context.user_data.pop("hours_type", None)
                
                # Send next task
                await self._send_next_task_for_user(chat_id)
                    
        except ValueError:
            await update.message.reply_text(
                persian_messages.ERROR_INVALID_HOURS
            )

    async def _handle_custom_delay(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Handle custom delay reason input.

        Args:
            update: Telegram update
            context: Callback context
        """
        delay_text = update.message.text
        
        chat_id = update.effective_chat.id
        queue = self.queue_manager.get_queue(chat_id)
        if not queue:
            await update.message.reply_text("❌ خطا: تسک یافت نشد")
            return
            
        task = queue.get_current()
        if not task:
            await update.message.reply_text("❌ خطا: تسک یافت نشد")
            return
        
        user_config = self.user_config_repository.get_user_config(
            update.effective_user.username
        )
        
        if user_config:
            await self.record_delay.execute(
                issue_key=task.issue_key,
                jira_username=user_config.jira_username,
                telegram_username=update.effective_user.username,
                delay_reason=DelayReason.OTHER,
                delay_reason_text=delay_text,
            )
            
            await update.message.reply_text(
                persian_messages.DELAY_RECORDED
            )
            
            context.user_data.pop("state", None)
            
            # Send next task
            await self._send_next_task_for_user(chat_id)

    def _memory(self, context: CallbackContext) -> ConversationMemory:
        """Return this chat's short-term memory, creating it on first use.

        Args:
            context: Callback context

        Returns:
            The conversation memory for this chat.
        """
        memory = context.user_data.get(self.MEMORY)
        if not isinstance(memory, ConversationMemory):
            memory = ConversationMemory()
            context.user_data[self.MEMORY] = memory
        return memory

    async def _reply_and_remember(
        self,
        context: CallbackContext,
        send,
        user_text: str,
        answer: str,
        parse_mode: str = None,
    ) -> None:
        """Send a reply and record the exchange for the next message.

        Args:
            context: Callback context
            send: Coroutine function that renders the reply
            user_text: What the user wrote
            answer: What we are replying
            parse_mode: Telegram parse mode, if the reply carries markup
        """
        try:
            if parse_mode:
                await send(answer, parse_mode=parse_mode)
            else:
                await send(answer)
        except Exception as exc:
            LOGGER.warning(f"Formatted reply rejected, sending plain: {exc}")
            await send(answer)
        self._memory(context).remember(user_text, answer)

    async def _handle_free_text(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Route a free-text message to the flow that can serve it.

        Args:
            update: Telegram update
            context: Callback context
        """
        text = (update.message.text or "").strip()
        if not text:
            return

        intent = MessageIntent.WORKLOG
        if self.classify_message_intent:
            intent = await self.classify_message_intent.execute(
                text, history=self._memory(context).render(),
            )
        LOGGER.info(
            f"Free-text intent for {text[:40]!r}: {intent.value} "
            f"({len(self._memory(context).turns)} turns of history)"
        )

        if intent is MessageIntent.WORKLOG:
            await self._handle_worklog_report(update, context)
        elif intent is MessageIntent.QUESTION:
            await self._handle_task_question(update, context, text)
        else:
            await self._reply_and_remember(
                context,
                update.message.reply_text,
                text,
                persian_messages.FREE_TEXT_HELP,
            )

    @staticmethod
    def _role_of(user_config) -> UserRole:
        """Read a caller's role, defaulting to the least privileged one.

        A misspelt role in the config must not break the assistant, and it
        must never widen access, so anything unrecognised reads as MEMBER.

        Args:
            user_config: The caller's configuration

        Returns:
            The configured role, or ``UserRole.MEMBER``.
        """
        raw = getattr(user_config, "assistant_role", None)
        try:
            return UserRole(str(raw).strip().lower())
        except ValueError:
            LOGGER.warning(f"Unknown assistant_role {raw!r}; treating as member")
            return UserRole.MEMBER

    async def _handle_task_question(
        self,
        update: Update,
        context: CallbackContext,
        question: str,
    ) -> None:
        """Answer a question about the user's own tasks.

        Args:
            update: Telegram update
            context: Callback context
            question: The question as the user asked it
        """
        if not (self.task_assistant_agent or self.answer_task_question):
            await update.message.reply_text(persian_messages.FREE_TEXT_HELP)
            return

        user_config = self.user_config_repository.get_user_config(
            update.effective_user.username,
        )
        if not user_config:
            return

        notice = await update.message.reply_text(persian_messages.QUESTION_THINKING)
        media: list = []
        try:
            if self.task_assistant_agent:
                # The agent can look people up and count, not just list, and
                # binds identity outside the model.
                answer = await self.task_assistant_agent.answer(
                    question,
                    context=AssistantContext(
                        jira_username=user_config.jira_username,
                        telegram_username=update.effective_user.username or "",
                        role=self._role_of(user_config),
                    ),
                    memory=self._memory(context),
                    media_sink=media,
                )
            else:
                tasks = await self.get_user_daily_tasks.execute(
                    jira_username=user_config.jira_username,
                )
                answer = await self.answer_task_question.execute(
                    question, tasks, history=self._memory(context).render(),
                )
        except Exception as exc:
            LOGGER.error(f"Failed to answer question: {exc}", exc_info=True)
            await notice.edit_text(persian_messages.ERROR_MESSAGE)
            return

        if not answer:
            await notice.edit_text(persian_messages.QUESTION_NO_ANSWER)
            return
        # The answer carries <a href> links, so it must render as HTML.
        await self._reply_and_remember(
            context, notice.edit_text, question, answer, parse_mode="HTML",
        )
        await self._send_media(context.bot, update.effective_chat.id, media)

    async def _send_media(self, bot, chat_id: int, media: list) -> None:
        """Send the screenshots a tool queued alongside its answer.

        Telegram cannot fetch an authenticated Jira URL, so the bytes are
        downloaded here and uploaded. A screenshot is usually the fastest
        way to understand a bug, and a link behind a login is not something
        anyone glances at on a phone.

        Args:
            bot: The Telegram bot to upload through
            chat_id: Where to send them
            media: Attachment records queued by the tools
        """
        for item in media[:MAX_MEDIA_PER_ANSWER]:
            try:
                payload = item["attachment"].get()
            except Exception as exc:
                LOGGER.warning(
                    f"Could not download {item['filename']} from "
                    f"{item['issue_key']}: {exc}",
                )
                continue

            caption = f"{item['issue_key']} — {item['filename']}"
            try:
                if item["mime"].startswith("video/"):
                    await bot.send_video(
                        chat_id=chat_id, video=payload, caption=caption,
                    )
                else:
                    await bot.send_photo(
                        chat_id=chat_id, photo=payload, caption=caption,
                    )
            except Exception as exc:
                LOGGER.warning(
                    f"Could not send {item['filename']} to {chat_id}: {exc}",
                )

    async def _handle_worklog_report(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Read a free-text report of the day's work and offer to log it.

        Args:
            update: Telegram update
            context: Callback context
        """
        if not (self.parse_worklog_report and self.confirm_worklog_report
                and self.get_user_daily_tasks):
            return

        text = (update.message.text or "").strip()
        if not text:
            return

        user_config = self.user_config_repository.get_user_config(
            update.effective_user.username,
        )
        if not user_config:
            return

        notice = await update.message.reply_text(persian_messages.WORKLOG_PARSING)

        try:
            candidates = await self.get_user_daily_tasks.execute(
                jira_username=user_config.jira_username,
            )
            if not candidates:
                await notice.edit_text(persian_messages.WORKLOG_NO_TASKS)
                return

            report = await self.parse_worklog_report.execute(
                text, candidates, history=self._memory(context).render(),
            )
            if not report.splits:
                # They mean to log time but have not said how much or on what.
                await self._reply_and_remember(
                    context,
                    notice.edit_text,
                    text,
                    persian_messages.WORKLOG_NEEDS_DETAIL,
                )
                return

            confirmation = self.confirm_worklog_report.execute(report, candidates)
        except Exception as exc:
            LOGGER.error(f"Failed to parse worklog report: {exc}", exc_info=True)
            await notice.edit_text(persian_messages.ERROR_MESSAGE)
            return

        context.user_data[self.PENDING_REPORT] = {
            "report": report,
            "candidates": {task.issue_key: task.summary for task in candidates},
            "candidate_objects": list(candidates),
        }
        await self._prompt_next_worklog_step(notice.edit_text, context, confirmation)

    async def _prompt_next_worklog_step(
        self,
        send,
        context: CallbackContext,
        confirmation,
    ) -> None:
        """Ask the next outstanding question, or offer the final confirmation.

        Args:
            send: Coroutine function that renders text plus a keyboard
            context: Callback context
            confirmation: Result of the confirmation use case
        """
        if confirmation.questions:
            question = confirmation.questions[0]
            if not question.options:
                # Nothing matched: the user types the key or skips. Remember
                # which split is waiting so the typed answer lands on it.
                context.user_data["state"] = self.WAITING_ISSUE_KEY
                context.user_data["awaiting_split"] = question.split_index
                await send(
                    question.text,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            persian_messages.WORKLOG_SKIP_SPLIT_BUTTON,
                            callback_data=f"wlpick_{question.split_index}_skip",
                        ),
                    ]]),
                )
                return
            buttons = [
                [InlineKeyboardButton(
                    option.label,
                    callback_data=f"wlpick_{question.split_index}_{option.issue_key}",
                )]
                for option in question.options
            ]
            buttons.append([InlineKeyboardButton(
                persian_messages.WORKLOG_SKIP_SPLIT_BUTTON,
                callback_data=f"wlpick_{question.split_index}_skip",
            )])
            await send(question.text, reply_markup=InlineKeyboardMarkup(buttons))
            return

        report = confirmation.report
        summaries = context.user_data[self.PENDING_REPORT]["candidates"]
        lines = [persian_messages.WORKLOG_CONFIRM_HEADER]
        for split in report.splits:
            if not split.is_ready:
                continue
            line = persian_messages.WORKLOG_CONFIRM_LINE.format(
                hours=self._format_hours(split.hours),
                issue_key=self._issue_link(split.issue_key),
                summary=summaries.get(split.issue_key, ""),
            )
            # Show a backdate and the work type, so what gets written to Jira
            # is visible before it is confirmed.
            extras = [
                part for part in (
                    self._spell_date(split.worked_on), split.work_type,
                ) if part
            ]
            if extras:
                line += f"  ({'، '.join(extras)})"
            lines.append(line)
        if confirmation.arithmetic_warning:
            lines.append(f"\n⚠️ {confirmation.arithmetic_warning}")

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                persian_messages.WORKLOG_CONFIRM_BUTTON,
                callback_data="wlconfirm",
            ),
            InlineKeyboardButton(
                persian_messages.WORKLOG_CANCEL_BUTTON,
                callback_data="wlcancel",
            ),
        ]])
        await send(
            "\n".join(lines), reply_markup=keyboard, parse_mode="HTML",
        )

    async def _handle_typed_issue_key(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Accept an issue key typed in answer to "I could not find a task".

        Args:
            update: Telegram update
            context: Callback context
        """
        pending = context.user_data.get(self.PENDING_REPORT)
        split_index = context.user_data.get("awaiting_split")
        if not pending or split_index is None:
            context.user_data.pop("state", None)
            return

        key = (update.message.text or "").strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9]+-\d+", key):
            await update.message.reply_text(persian_messages.WORKLOG_KEY_INVALID)
            return

        # Only the person's own issues are accepted, so a typed key cannot be
        # used to log time against somebody else's work.
        candidates = pending["candidate_objects"]
        if not any(task.issue_key.upper() == key for task in candidates):
            await update.message.reply_text(
                persian_messages.WORKLOG_KEY_NOT_YOURS.format(issue_key=key),
            )
            return

        context.user_data.pop("state", None)
        context.user_data.pop("awaiting_split", None)

        report = pending["report"]
        split = report.splits[split_index]
        split.issue_key = key
        split.status = WorklogSplitStatus.RESOLVED

        confirmation = self.confirm_worklog_report.execute(report, candidates)
        await self._prompt_next_worklog_step(
            update.message.reply_text, context, confirmation,
        )

    async def _handle_worklog_pick(
        self,
        query,
        context: CallbackContext,
        data: str,
    ) -> None:
        """Apply the user's answer to one disambiguation question.

        Args:
            query: Callback query
            context: Callback context
            data: Callback data, ``wlpick_<split index>_<issue key or skip>``
        """
        pending = context.user_data.get(self.PENDING_REPORT)
        if not pending:
            # The report was already written or cancelled. Answering a stale
            # keyboard is not a failure, and calling it one makes the user
            # think their hours were lost.
            LOGGER.info("Worklog choice arrived after the report was gone")
            await query.answer(
                persian_messages.WORKLOG_ALREADY_SAVED, show_alert=True,
            )
            return

        _, raw_index, choice = data.split("_", 2)
        report = pending["report"]
        try:
            split = report.splits[int(raw_index)]
        except (ValueError, IndexError):
            await query.edit_message_text(persian_messages.ERROR_MESSAGE)
            return

        if choice == "skip":
            report.splits.remove(split)
        else:
            split.issue_key = choice
            split.status = WorklogSplitStatus.RESOLVED

        if not report.splits:
            context.user_data.pop(self.PENDING_REPORT, None)
            await query.edit_message_text(persian_messages.WORKLOG_SPLIT_SKIPPED)
            return

        # Re-run confirmation so the next unresolved split is asked about.
        confirmation = self.confirm_worklog_report.execute(
            report, pending["candidate_objects"],
        )
        await self._prompt_next_worklog_step(
            query.edit_message_text, context, confirmation,
        )

    async def _handle_worklog_confirm(
        self,
        query,
        context: CallbackContext,
    ) -> None:
        """Write the confirmed report to Jira as one worklog per split.

        Args:
            query: Callback query
            context: Callback context
        """
        pending = context.user_data.pop(self.PENDING_REPORT, None)
        if not pending:
            # Writing several worklogs takes seconds, during which the
            # buttons are still on screen and look unresponsive. A second
            # tap arriving after the first has consumed the report is not
            # an error: the work is already in Jira, and saying "خطا رخ داد"
            # invites the user to report it again by hand.
            LOGGER.info("Duplicate worklog confirmation ignored")
            await query.answer(
                persian_messages.WORKLOG_ALREADY_SAVED, show_alert=True,
            )
            return

        user_config = self.user_config_repository.get_user_config(
            query.from_user.username,
        )
        if not user_config:
            context.user_data[self.PENDING_REPORT] = pending
            await query.edit_message_text(persian_messages.ERROR_MESSAGE)
            return

        # Take the buttons away before the first write, so the only tap that
        # can reach here is the one already being served.
        await self._disarm(query)

        lines = [persian_messages.WORKLOG_SAVED_HEADER]
        for split in pending["report"].splits:
            if not split.is_ready:
                continue
            try:
                await self.record_worklog.execute(
                    issue_key=split.issue_key,
                    jira_username=user_config.jira_username,
                    telegram_username=query.from_user.username,
                    hours=split.hours,
                    comment=self._worklog_comment(split),
                    started_date=split.worked_on,
                )
                lines.append(persian_messages.WORKLOG_SAVED_LINE.format(
                    hours=self._format_hours(split.hours),
                    issue_key=self._issue_link(split.issue_key),
                ))
            except Exception as exc:
                LOGGER.error(
                    f"Failed to log {split.hours}h on {split.issue_key}: {exc}",
                )
                lines.append(persian_messages.WORKLOG_SAVE_FAILED_LINE.format(
                    issue_key=self._issue_link(split.issue_key),
                ))

        # Worklog hours changed, so the cached list is now behind Jira.
        invalidate = getattr(self.get_user_daily_tasks, "invalidate", None)
        if invalidate:
            invalidate(user_config.jira_username)

        await query.edit_message_text("\n".join(lines), parse_mode="HTML")
        await self._follow_up_after_digest(query.message.chat_id, pending)

    @staticmethod
    async def _disarm(query) -> None:
        """Remove a message's buttons so it cannot be tapped twice.

        Args:
            query: The callback query whose message is being served
        """
        try:
            await query.edit_message_text(
                persian_messages.WORKLOG_SAVING, reply_markup=None,
            )
        except Exception as exc:
            LOGGER.warning(f"Could not clear the worklog keyboard: {exc}")

    async def _follow_up_after_digest(self, chat_id: int, pending: dict) -> None:
        """Ask about the work a digest reply did not account for.

        Someone who has just written a report should not then be asked
        about the tasks they described. Only the remainder is queued, and
        when a report covers everything nothing further is asked at all.

        Args:
            chat_id: Whose check-in this is
            pending: The confirmed report, holding the tasks it was parsed
                against
        """
        session = self.digest_sessions.pop(chat_id, None)
        if not session:
            return

        reported = {
            split.issue_key
            for split in pending["report"].splits
            if split.issue_key
        }
        remaining = BuildDailyDigestUseCase.unaccounted_for(
            session["tasks"], reported, session["limit"],
        )

        if not self.message_sender:
            LOGGER.error("message_sender is not set; cannot follow up")
            return

        if not remaining:
            await self.message_sender(
                chat_id, persian_messages.DIGEST_ALL_COVERED.strip(),
            )
            return

        await self.message_sender(
            chat_id,
            persian_messages.DIGEST_REMAINING.format(
                count=len(remaining),
            ).strip(),
        )
        self.queue_manager.create_queue(chat_id, remaining)
        if self.task_sender:
            await self.task_sender(chat_id)

    @staticmethod
    def _spell_date(worked_on: Optional[str]) -> Optional[str]:
        """Name the weekday alongside a backdated worklog.

        A bare "2026-08-24" reads as correct even when it is three days out.
        The weekday is what a person actually checks.

        Args:
            worked_on: ISO date the work happened, or None for today

        Returns:
            The date with its Persian weekday, or None when it is today.
        """
        if not worked_on:
            return None
        try:
            day = date.fromisoformat(worked_on)
        except ValueError:
            return worked_on
        names = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه",
                 "جمعه", "شنبه", "یکشنبه"]
        return f"{names[day.weekday()]} {worked_on}"

    def _issue_link(self, issue_key: str) -> str:
        """Render an issue key as a tappable Jira link.

        Args:
            issue_key: The key to link

        Returns:
            An anchor, or the bare key when no base URL is configured.
        """
        if not self.base_url:
            return issue_key
        return f'<a href="{self.base_url}/browse/{issue_key}">{issue_key}</a>'

    @staticmethod
    def _worklog_comment(split) -> Optional[str]:
        """Build the worklog comment, keeping how the time was worked.

        "ریموت" and "اضافه‌کاری" carry meaning for payroll here, so they are
        recorded in the comment rather than dropped with the rest of the
        phrasing.

        Args:
            split: The parsed piece of work

        Returns:
            The comment to store, or None when there is nothing to say.
        """
        parts = [part for part in (split.work_type, split.description) if part]
        return " — ".join(parts) or None

    @staticmethod
    def _format_hours(hours: float) -> str:
        """Render hours without a trailing ``.0`` on whole numbers."""
        return str(int(hours)) if float(hours).is_integer() else str(round(hours, 2))

    async def tasks_command(self, update: Update, context: CallbackContext) -> None:
        """Ask about today's tasks one at a time, on request.

        The digest offers this for people who would rather be walked
        through their tasks than write a report. It also works outside the
        morning check-in, when someone wants to go through them again.

        Args:
            update: The incoming command
            context: Telegram callback context
        """
        chat_id = update.effective_chat.id
        user_config = self.user_config_repository.get_user_config(
            update.effective_user.username,
        )
        if not user_config or not user_config.jira_username:
            await update.message.reply_text(persian_messages.ERROR_MESSAGE)
            return

        session = self.digest_sessions.pop(chat_id, None)
        if session:
            tasks = session["tasks"]
        else:
            tasks = await self.get_user_daily_tasks.execute(
                user_config.jira_username,
            )
            tasks = tasks[:MAX_TASKS_PER_REMINDER]

        if not tasks:
            await update.message.reply_text(
                persian_messages.DIGEST_NOTHING.strip(),
            )
            return

        self.queue_manager.create_queue(chat_id, tasks)
        if self.task_sender:
            await self.task_sender(chat_id)

    async def _send_next_task_for_user(self, chat_id: int) -> None:
        """Send next task for user.

        Args:
            chat_id: User's chat ID
        """
        LOGGER.info(f"_send_next_task_for_user called for chat_id {chat_id}")
        
        if self.task_sender:
            LOGGER.info(f"Calling task_sender for chat_id {chat_id}")
            await self.task_sender(chat_id)
        else:
            LOGGER.error("task_sender is not set!")
