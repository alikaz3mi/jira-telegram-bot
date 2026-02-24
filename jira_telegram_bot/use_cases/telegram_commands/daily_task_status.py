"""Daily task status tracking use case."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_status import (
    DelayReason,
    DailyStatusSession,
    SubtaskRequest,
    TaskStatusUpdate,
)
from jira_telegram_bot.use_cases.interfaces.daily_task_status_interface import (
    DailyTaskStatusInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class DailyTaskStatus(DailyTaskStatusInterface):
    """Use case for daily task status tracking."""

    (
        TASK_DISPLAY,
        TIME_SPENT_DATE,
        TIME_SPENT,
        DELAY_REASON,
        DELAY_COMMENT,
        STATUS_TRANSITION,
        POST_TRANSITION_ACTION,
        SUBTASK_REQUEST,
        SUBTASK_CONFIRM,
        WORK_DESCRIPTION,
    ) = range(10)

    ISSUE_TYPE_ICONS = {
        "bug": "🐛",
        "sub-task": "🔹",
        "story": "📖",
        "task": "📋",
        "epic": "🏔",
        "improvement": "💡",
        "new feature": "✨",
    }

    TEXTS = {
        "greeting": "سلام! 👋\nوقت بررسی وضعیت تسک‌های امروز است.",
        "no_tasks": "🎉 تبریک! هیچ تسک فعالی برای امروز ندارید.",
        "task_header": "📋 تسک {index} از {total}",
        "task_details": (
            "{type_icon} *نوع:* {issue_type}\n"
            "🎫 *تیکت:* [{key}]({jira_url})\n"
            "📝 *عنوان:* {summary}\n"
            "{epic_line}"
            "{parent_line}"
            "📊 *وضعیت:* {status}\n"
            "⭐ *استوری پوینت:* {points}\n"
            "🗓 *ددلاین:* {deadline}"
        ),
        "select_action": "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        "log_time": "⏱ ثبت زمان",
        "mark_progress": "🔄 تغییر وضعیت",
        "report_delay": "⚠️ گزارش تأخیر",
        "request_subtask": "➕ درخواست ساب‌تسک",
        "skip": "⏭ بعدی",
        "previous": "⏮ قبلی",
        "select_date": "لطفاً روزی که روی تسک کار کرده‌اید را انتخاب کنید:",
        "today": "امروز",
        "yesterday": "دیروز",
        "days_ago": "{days} روز پیش",
        "hours_prompt": "چند ساعت روی این تسک کار کرده‌اید؟",
        "work_description_prompt": (
            "چه کاری روی این تسک انجام داده‌اید؟\n"
            "توضیح مختصر بنویسید یا /skip بزنید:"
        ),
        "hours_logged": "✅ {hours} ساعت برای تسک {key} ثبت شد.",
        "select_delay_reason": "لطفاً دلیل تأخیر را انتخاب کنید:",
        "delay_reasons": {
            DelayReason.UNCLEAR_EXPLANATION: "❓ توضیح نامشخص",
            DelayReason.INCOMPLETE_DESIGN: "🎨 طراحی ناقص",
            DelayReason.BLOCKING_ISSUE: "🚫 مسئله بلاک کننده",
            DelayReason.TECHNICAL_ISSUE: "🔧 مسئله فنی",
            DelayReason.LACK_OF_KNOWLEDGE: "📚 کمبود دانش",
        },
        "delay_comment_prompt": "لطفاً توضیحات بیشتر را وارد کنید (یا /skip برای رد شدن):",
        "delay_recorded": "✅ دلیل تأخیر ثبت شد.",
        "select_transition": "وضعیت جدید را انتخاب کنید:",
        "transition_done": "✅ وضعیت تسک به {status} تغییر کرد.",
        "want_to_log_time": "آیا می‌خواهید زمان صرف شده را ثبت کنید؟",
        "yes": "✅ بله",
        "no": "❌ خیر",
        "subtask_prompt": "لطفاً عنوان ساب‌تسک مورد نظر را وارد کنید:",
        "subtask_sent_to_po": "✅ درخواست ساب‌تسک به مدیر پروژه ({po}) ارسال شد.",
        "subtask_request_for_po": (
            "📬 *درخواست ساب‌تسک جدید*\n\n"
            "*از طرف:* {requester}\n"
            "*تسک والد:* `{parent_key}`\n"
            "*عنوان پیشنهادی:* {summary}\n\n"
            "آیا این ساب‌تسک ایجاد شود؟"
        ),
        "all_tasks_done": "🎉 همه تسک‌ها بررسی شدند!\n\nخلاصه:\n{summary}",
        "upcoming_header": "\n\n📅 *تسک‌های پیش رو (تا {days} روز آینده):*\n",
        "upcoming_empty": "هیچ تسک جدیدی در روزهای آینده ندارید. ✨",
        "cancel": "❌ عملیات لغو شد.",
        "back": "🔙 بازگشت",
        "hour_suffix": "ساعت",
        "error": "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
    }

    HOURS_OPTIONS = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7, 8, 10, 12]

    def __init__(
        self,
        jira_repository: TaskManagerRepositoryInterface,
        user_config: UserConfigInterface,
    ):
        """Initialize the daily task status use case.
        
        Args:
            jira_repository: Repository for Jira operations.
            user_config: User configuration interface.
        """
        self.jira_repository = jira_repository
        self.user_config = user_config

    def _build_keyboard(
        self,
        options: List[str],
        data: Optional[List[str]] = None,
        row_width: int = 3,
        include_back: bool = False,
    ) -> InlineKeyboardMarkup:
        """Build an inline keyboard with specified options.
        
        Args:
            options: Button text options.
            data: Callback data (defaults to options if not provided).
            row_width: Number of buttons per row.
            include_back: Whether to include a back button.
            
        Returns:
            InlineKeyboardMarkup with the keyboard layout.
        """
        if not data:
            data = options
            
        keyboard = []
        for i in range(0, len(options), row_width):
            row = [
                InlineKeyboardButton(text=opt, callback_data=dat)
                for opt, dat in zip(options[i:i + row_width], data[i:i + row_width])
            ]
            keyboard.append(row)
            
        if include_back:
            keyboard.append([
                InlineKeyboardButton(self.TEXTS["back"], callback_data="back")
            ])
            
        return InlineKeyboardMarkup(keyboard)

    def _build_hours_keyboard(self) -> InlineKeyboardMarkup:
        """Build keyboard for hours selection.
        
        Returns:
            InlineKeyboardMarkup with hours options (3 per row).
        """
        options = [f"{h} {self.TEXTS['hour_suffix']}" for h in self.HOURS_OPTIONS]
        data = [f"hours|{h}" for h in self.HOURS_OPTIONS]
        return self._build_keyboard(options, data, row_width=3, include_back=True)

    def _build_date_keyboard(self) -> InlineKeyboardMarkup:
        """Build keyboard for date selection (last 7 days).
        
        Returns:
            InlineKeyboardMarkup with date options.
        """
        from datetime import datetime, timedelta
        
        options = []
        data = []
        
        for days_back in range(7):
            if days_back == 0:
                label = self.TEXTS["today"]
            elif days_back == 1:
                label = self.TEXTS["yesterday"]
            else:
                label = self.TEXTS["days_ago"].format(days=days_back)
            
            date = datetime.now() - timedelta(days=days_back)
            date_str = date.strftime("%Y-%m-%d")
            
            options.append(label)
            data.append(f"date|{date_str}")
        
        return self._build_keyboard(options, data, row_width=2, include_back=True)

    def _build_task_action_keyboard(self, show_previous: bool = False) -> InlineKeyboardMarkup:
        """Build keyboard for task actions.
        
        Args:
            show_previous: Whether to show the previous button.
        
        Returns:
            InlineKeyboardMarkup with action options.
        """
        keyboard = [
            [
                InlineKeyboardButton(self.TEXTS["log_time"], callback_data="action|log_time"),
                InlineKeyboardButton(self.TEXTS["mark_progress"], callback_data="action|transition"),
                InlineKeyboardButton(self.TEXTS["report_delay"], callback_data="action|delay"),
            ],
            [
                InlineKeyboardButton(self.TEXTS["request_subtask"], callback_data="action|subtask"),
                InlineKeyboardButton(self.TEXTS["skip"], callback_data="action|skip"),
            ],
        ]
        if show_previous:
            keyboard[1].insert(
                0,
                InlineKeyboardButton(self.TEXTS["previous"], callback_data="action|prev"),
            )
        return InlineKeyboardMarkup(keyboard)

    def _build_delay_reason_keyboard(self) -> InlineKeyboardMarkup:
        """Build keyboard for delay reasons.
        
        Returns:
            InlineKeyboardMarkup with delay reason options.
        """
        options = list(self.TEXTS["delay_reasons"].values())
        data = [f"delay|{reason.value}" for reason in DelayReason]
        return self._build_keyboard(options, data, row_width=2, include_back=True)

    def _build_transition_keyboard(self, transitions: List[dict]) -> InlineKeyboardMarkup:
        """Build keyboard for status transitions.
        
        Args:
            transitions: List of available transitions.
            
        Returns:
            InlineKeyboardMarkup with transition options.
        """
        options = [t["name"] for t in transitions]
        data = [f"transition|{t['id']}" for t in transitions]
        return self._build_keyboard(options, data, row_width=2, include_back=True)

    def _get_persian_date(self) -> str:
        """Get current date in Persian format with day of week.
        
        Returns:
            Formatted date string like 'شنبه 2026/01/10'.
        """
        now = datetime.now()
        
        # Persian weekday names
        persian_weekdays = [
            "دوشنبه",  # Monday
            "سه‌شنبه",  # Tuesday
            "چهارشنبه",  # Wednesday
            "پنج‌شنبه",  # Thursday
            "جمعه",  # Friday
            "شنبه",  # Saturday
            "یکشنبه",  # Sunday
        ]
        
        weekday_name = persian_weekdays[now.weekday()]
        date_str = now.strftime("%Y/%m/%d")
        
        return f"{weekday_name} {date_str}"

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape special characters for Telegram Markdown v1.

        Args:
            text: Raw text to escape.

        Returns:
            Escaped text safe for Markdown v1.
        """
        special_chars = r"_*[]()~`>"
        escaped = text
        for ch in special_chars:
            escaped = escaped.replace(ch, f"\\{ch}")
        return escaped

    def _get_epic_name_for_issue(self, issue: Any) -> Optional[str]:
        """Get the epic name for an issue via its epic link field.

        Args:
            issue: Jira issue object.

        Returns:
            Epic summary string, or None if no epic is linked.
        """
        epic_key = getattr(issue.fields, "customfield_10100", None)
        if not epic_key:
            return None
        try:
            epic_issue = self.jira_repository.get_issue(epic_key)
            if epic_issue:
                return epic_issue.fields.summary
        except Exception as exc:
            LOGGER.warning(f"Could not fetch epic {epic_key} for {issue.key}: {exc}")
        return None

    def _get_parent_summary(self, issue: Any) -> Optional[str]:
        """Get the parent issue summary for a subtask.

        Args:
            issue: Jira issue object.

        Returns:
            Parent summary string, or None if not a subtask or parent unavailable.
        """
        if not hasattr(issue.fields, "parent"):
            return None
        try:
            parent_issue = self.jira_repository.get_issue(issue.fields.parent.key)
            if parent_issue:
                return parent_issue.fields.summary
        except Exception as exc:
            LOGGER.warning(f"Could not fetch parent for {issue.key}: {exc}")
        return None

    def _format_task_message(
        self,
        issue: Any,
        index: int,
        total: int,
    ) -> str:
        """Format a task for display with type, epic and parent info.

        Args:
            issue: Jira issue object.
            index: Current task index (1-based).
            total: Total number of tasks.

        Returns:
            Formatted task message in Persian.
        """
        header = self.TEXTS["task_header"].format(index=index, total=total)

        points = getattr(issue.fields, "customfield_10106", None) or "-"
        deadline = getattr(issue.fields, "duedate", None) or "-"

        jira_base_url = self.jira_repository.settings.domain
        jira_url = f"{jira_base_url.scheme}://{jira_base_url.host}/browse/{issue.key}"

        issue_type_name = issue.fields.issuetype.name
        type_icon = self.ISSUE_TYPE_ICONS.get(issue_type_name.lower(), "📋")

        epic_name = self._get_epic_name_for_issue(issue)
        epic_line = f"🏔 *اپیک:* {self._escape_markdown(epic_name)}\n" if epic_name else ""

        parent_summary = self._get_parent_summary(issue)
        parent_line = f"📖 *استوری والد:* {self._escape_markdown(parent_summary)}\n" if parent_summary else ""

        details = self.TEXTS["task_details"].format(
            type_icon=type_icon,
            issue_type=self._escape_markdown(issue_type_name),
            key=issue.key,
            jira_url=jira_url,
            summary=self._escape_markdown(issue.fields.summary),
            epic_line=epic_line,
            parent_line=parent_line,
            status=self._escape_markdown(issue.fields.status.name),
            points=points,
            deadline=deadline,
        )

        return f"{header}\n\n{details}\n\n{self.TEXTS['select_action']}"

    async def start_daily_status(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Start the daily status check for a user.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        user = update.effective_user
        user_cfg = self.user_config.get_user_config(user.username)
        
        if not user_cfg:
            await update.message.reply_text("❌ کاربر یافت نشد.")
            return ConversationHandler.END
            
        jira_username = user_cfg.jira_username
        tasks = self.jira_repository.get_user_actionable_tasks(jira_username)
        
        if not tasks:
            await update.message.reply_text(self.TEXTS["no_tasks"])
            return ConversationHandler.END
            
        session = DailyStatusSession(
            telegram_user_id=user.id,
            telegram_username=user.username,
            jira_username=jira_username,
            tasks=[task.key for task in tasks],
        )
        
        context.user_data["daily_status_session"] = session
        context.user_data["daily_status_issues"] = {task.key: task for task in tasks}
        
        # Add today's date to greeting
        persian_date = self._get_persian_date()
        greeting_with_date = f"{self.TEXTS['greeting']}\n\n📅 {persian_date}"
        await update.message.reply_text(greeting_with_date)
        
        return await self._show_current_task(update, context)

    async def _show_current_task(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Show the current task to the user.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        session: DailyStatusSession = context.user_data["daily_status_session"]
        issues = context.user_data["daily_status_issues"]
        
        if session.current_task_index >= len(session.tasks):
            return await self._finish_session(update, context)
            
        current_key = session.tasks[session.current_task_index]
        current_issue = issues[current_key]
        
        message = self._format_task_message(
            current_issue,
            session.current_task_index + 1,
            len(session.tasks),
        )
        
        keyboard = self._build_task_action_keyboard(
            show_previous=session.current_task_index > 0,
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
        else:
            await update.effective_chat.send_message(
                message,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            
        return self.TASK_DISPLAY

    async def handle_task_action(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle user's action selection for a task.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()
        
        action = query.data.split("|")[1]
        
        if action == "log_time":
            keyboard = self._build_date_keyboard()
            await query.edit_message_text(
                self.TEXTS["select_date"],
                reply_markup=keyboard,
            )
            return self.TIME_SPENT_DATE
            
        elif action == "transition":
            session = context.user_data["daily_status_session"]
            current_key = session.tasks[session.current_task_index]
            transitions = self.jira_repository.get_available_transitions(current_key)
            
            if not transitions:
                await query.edit_message_text("❌ هیچ انتقال وضعیتی موجود نیست.")
                return await self._show_current_task(update, context)
                
            keyboard = self._build_transition_keyboard(transitions)
            await query.edit_message_text(
                self.TEXTS["select_transition"],
                reply_markup=keyboard,
            )
            return self.STATUS_TRANSITION
            
        elif action == "delay":
            keyboard = self._build_delay_reason_keyboard()
            await query.edit_message_text(
                self.TEXTS["select_delay_reason"],
                reply_markup=keyboard,
            )
            return self.DELAY_REASON
            
        elif action == "subtask":
            await query.edit_message_text(self.TEXTS["subtask_prompt"])
            return self.SUBTASK_REQUEST
            
        elif action == "skip":
            session = context.user_data["daily_status_session"]
            session.current_task_index += 1
            return await self._show_current_task(update, context)

        elif action == "prev":
            session = context.user_data["daily_status_session"]
            if session.current_task_index > 0:
                session.current_task_index -= 1
            return await self._show_current_task(update, context)
            
        return self.TASK_DISPLAY

    async def handle_time_spent(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle time spent selection and ask for work description.

        Args:
            update: Telegram update object.
            context: Telegram callback context.

        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()

        if query.data == "back":
            return await self._show_current_task(update, context)

        hours = float(query.data.split("|")[1])
        context.user_data["pending_hours"] = hours

        await query.edit_message_text(self.TEXTS["work_description_prompt"])
        return self.WORK_DESCRIPTION

    async def handle_work_description(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle work description input and log the work.

        Args:
            update: Telegram update object.
            context: Telegram callback context.

        Returns:
            Next conversation state.
        """
        session: DailyStatusSession = context.user_data["daily_status_session"]
        current_key = session.tasks[session.current_task_index]
        hours = context.user_data.pop("pending_hours", 0)
        selected_date = context.user_data.pop("selected_work_date", None)

        description = None
        if update.message and update.message.text != "/skip":
            description = update.message.text.strip()

        try:
            time_spent_seconds = int(hours * 3600)
            self.jira_repository.log_work(
                current_key,
                time_spent_seconds,
                started_date=selected_date,
                comment=description,
            )

            session.updates.append(TaskStatusUpdate(
                issue_key=current_key,
                action="log_time",
                time_spent_hours=hours,
                work_description=description,
            ))

            await update.effective_chat.send_message(
                self.TEXTS["hours_logged"].format(hours=hours, key=current_key)
            )

        except Exception as exc:
            LOGGER.error(f"Failed to log work: {exc}")
            await update.effective_chat.send_message(self.TEXTS["error"])

        session.current_task_index += 1
        return await self._show_current_task(update, context)

    async def handle_date_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle date selection for time logging.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            return await self._show_current_task(update, context)
        
        selected_date = query.data.split("|")[1]
        context.user_data["selected_work_date"] = selected_date
        
        keyboard = self._build_hours_keyboard()
        await query.edit_message_text(
            self.TEXTS["hours_prompt"],
            reply_markup=keyboard,
        )
        return self.TIME_SPENT

    async def handle_delay_reason(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle delay reason selection.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            return await self._show_current_task(update, context)
            
        reason = query.data.split("|")[1]
        context.user_data["selected_delay_reason"] = reason
        
        await query.edit_message_text(self.TEXTS["delay_comment_prompt"])
        return self.DELAY_COMMENT

    async def handle_delay_comment(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle delay comment input.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        session = context.user_data["daily_status_session"]
        current_key = session.tasks[session.current_task_index]
        reason = context.user_data.get("selected_delay_reason")
        
        comment = None
        if update.message and update.message.text != "/skip":
            comment = update.message.text
            
        try:
            self.jira_repository.set_delay_reason(current_key, reason, comment)
            
            session.updates.append(TaskStatusUpdate(
                issue_key=current_key,
                action="report_delay",
                delay_reason=DelayReason(reason),
                delay_comment=comment,
            ))
            
            await update.effective_chat.send_message(self.TEXTS["delay_recorded"])
            
        except Exception as e:
            LOGGER.error(f"Failed to set delay reason: {e}")
            await update.effective_chat.send_message(self.TEXTS["error"])
            
        session.current_task_index += 1
        return await self._show_current_task(update, context)

    async def handle_transition(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle status transition selection.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            return await self._show_current_task(update, context)
            
        transition_id = query.data.split("|")[1]
        session = context.user_data["daily_status_session"]
        current_key = session.tasks[session.current_task_index]
        
        try:
            self.jira_repository.transition_issue(current_key, transition_id)
            
            new_status = self.jira_repository.get_issue(current_key).fields.status.name
            
            message = self.TEXTS["transition_done"].format(status=new_status)
            message += f"\n\n{self.TEXTS['want_to_log_time']}"
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(self.TEXTS["yes"], callback_data="post_trans|log_time"),
                    InlineKeyboardButton(self.TEXTS["no"], callback_data="post_trans|skip"),
                ]
            ])
            
            await query.edit_message_text(
                message,
                reply_markup=keyboard,
            )
            return self.POST_TRANSITION_ACTION
            
        except Exception as e:
            LOGGER.error(f"Failed to transition issue: {e}")
            await query.edit_message_text(self.TEXTS["error"])
            
            session.current_task_index += 1
            return await self._show_current_task(update, context)

    async def handle_post_transition_action(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle action after transition (log time or skip).
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()
        
        action = query.data.split("|")[1]
        
        if action == "log_time":
            keyboard = self._build_date_keyboard()
            await query.edit_message_text(
                self.TEXTS["select_date"],
                reply_markup=keyboard,
            )
            return self.TIME_SPENT_DATE
        else:
            session = context.user_data["daily_status_session"]
            session.current_task_index += 1
            return await self._show_current_task(update, context)

    async def handle_subtask_request(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle subtask request input.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        session = context.user_data["daily_status_session"]
        issues = context.user_data["daily_status_issues"]
        current_key = session.tasks[session.current_task_index]
        current_issue = issues[current_key]
        
        subtask_summary = update.message.text.strip()
        project_key = current_issue.fields.project.key
        
        po_config = self._get_project_po(project_key)
        
        if not po_config:
            await update.message.reply_text("❌ مدیر پروژه یافت نشد.")
            session.current_task_index += 1
            return await self._show_current_task(update, context)
            
        request = SubtaskRequest(
            parent_issue_key=current_key,
            summary=subtask_summary,
            requested_by=session.telegram_username,
            project_key=project_key,
        )
        
        try:
            po_message = self.TEXTS["subtask_request_for_po"].format(
                requester=session.telegram_username,
                parent_key=current_key,
                summary=subtask_summary,
            )
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ تأیید", callback_data=f"approve_subtask|{current_key}|{subtask_summary}"),
                    InlineKeyboardButton("❌ رد", callback_data=f"reject_subtask|{current_key}"),
                ]
            ])
            
            await context.bot.send_message(
                chat_id=po_config.telegram_user_chat_id,
                text=po_message,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            
            await update.message.reply_text(
                self.TEXTS["subtask_sent_to_po"].format(po=po_config.jira_username)
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to send subtask request to PO: {e}")
            await update.message.reply_text(self.TEXTS["error"])
            
        session.current_task_index += 1
        return await self._show_current_task(update, context)

    def _get_project_po(self, project_key: str) -> Optional[Any]:
        """Get the Product Owner config for a project.
        
        Args:
            project_key: Jira project key.
            
        Returns:
            User config for the PO, or None if not found.
        """
        try:
            all_users = self.user_config.get_all_user_configs()
            for user in all_users:
                if hasattr(user, "projects") and user.projects:
                    for project in user.projects:
                        if project.get("key") == project_key and project.get("role") == "PO":
                            return user
        except Exception as e:
            LOGGER.error(f"Failed to get PO for project {project_key}: {e}")
        return None

    async def _finish_session(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Finish the daily status session and show summary with upcoming tasks.

        Args:
            update: Telegram update object.
            context: Telegram callback context.

        Returns:
            ConversationHandler.END
        """
        session: DailyStatusSession = context.user_data["daily_status_session"]

        summary_lines = self._build_summary_lines(session)
        summary = "\n".join(summary_lines) if summary_lines else "هیچ تغییری ثبت نشد."

        message = self.TEXTS["all_tasks_done"].format(summary=summary)
        message += self._build_upcoming_section(session.jira_username)

        if update.callback_query:
            await update.callback_query.edit_message_text(message, parse_mode="Markdown")
        else:
            await update.effective_chat.send_message(message, parse_mode="Markdown")

        context.user_data.pop("daily_status_session", None)
        context.user_data.pop("daily_status_issues", None)
        context.user_data.pop("selected_delay_reason", None)
        context.user_data.pop("pending_hours", None)
        context.user_data.pop("selected_work_date", None)

        return ConversationHandler.END

    def _build_summary_lines(self, session: DailyStatusSession) -> List[str]:
        """Build summary lines from session updates.

        Args:
            session: The daily status session.

        Returns:
            List of formatted summary lines.
        """
        lines: List[str] = []
        for upd in session.updates:
            if upd.action == "log_time":
                line = f"⏱ {upd.issue_key}: {upd.time_spent_hours} ساعت"
                if upd.work_description:
                    line += f" — {self._escape_markdown(upd.work_description)}"
                lines.append(line)
            elif upd.action == "report_delay":
                lines.append(f"⚠️ {upd.issue_key}: تأخیر گزارش شد")
        return lines

    def _build_upcoming_section(self, jira_username: str) -> str:
        """Build the upcoming tasks section for the final summary.

        Args:
            jira_username: The Jira username to look up upcoming tasks for.

        Returns:
            Formatted upcoming tasks string, or empty-notice.
        """
        lookahead_days = 4
        try:
            upcoming = self.jira_repository.get_user_upcoming_tasks(
                jira_username, lookahead_days
            )
        except Exception as exc:
            LOGGER.warning(f"Could not fetch upcoming tasks: {exc}")
            upcoming = []

        if not upcoming:
            return self.TEXTS["upcoming_header"].format(days=lookahead_days) + self.TEXTS["upcoming_empty"]

        grouped: Dict[str, List[Any]] = {}
        for issue in upcoming:
            epic_name = self._get_epic_name_for_issue(issue) or "بدون اپیک"
            grouped.setdefault(epic_name, []).append(issue)

        section = self.TEXTS["upcoming_header"].format(days=lookahead_days)
        for epic, issues in grouped.items():
            section += f"\n🏔 *{self._escape_markdown(epic)}*\n"
            for iss in issues:
                type_icon = self.ISSUE_TYPE_ICONS.get(
                    iss.fields.issuetype.name.lower(), "📋"
                )
                target_start = getattr(iss.fields, "customfield_10109", None) or "-"
                section += (
                    f"  {type_icon} [{iss.key}] "
                    f"{self._escape_markdown(iss.fields.summary)} "
                    f"(شروع: {target_start})\n"
                )
        return section

    async def cancel(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Cancel the current session.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            ConversationHandler.END
        """
        await update.message.reply_text(self.TEXTS["cancel"])
        
        context.user_data.pop("daily_status_session", None)
        context.user_data.pop("daily_status_issues", None)
        
        return ConversationHandler.END

    async def trigger_for_all_users(self, application) -> None:
        """Trigger daily status check for all configured users.
        
        Args:
            application: Telegram Application instance.
        """
        LOGGER.info("Triggering daily task status for all users")
        
        all_users_dict = self.user_config.get_all_user_configs()
        all_users = list(all_users_dict.values())
        
        for user_cfg in all_users:
            try:
                if not user_cfg.telegram_user_chat_id:
                    continue
                
                    
                jira_username = user_cfg.jira_username
                if jira_username != 'a_kazemi':
                    continue
                tasks = self.jira_repository.get_user_actionable_tasks(jira_username)
                
                if not tasks:
                    continue
                    
                await application.bot.send_message(
                    chat_id=user_cfg.telegram_user_chat_id,
                    text=(
                        f"{self.TEXTS['greeting']}\n\n"
                        f"شما {len(tasks)} تسک فعال دارید.\n"
                        f"برای شروع بررسی، دستور /daily_status را وارد کنید."
                    ),
                )
                
                LOGGER.info(f"Sent daily status reminder to {user_cfg.telegram_username}")
                
            except Exception as e:
                LOGGER.error(f"Failed to trigger daily status for {user_cfg.telegram_username}: {e}")
