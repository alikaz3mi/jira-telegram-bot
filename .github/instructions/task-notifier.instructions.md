# Daily Task Status Implementation Instructions

## Feature Overview

Implement a daily task status tracking feature that:
1. Runs daily at a configurable time (integrated into `__main__.py`)
2. Fetches actionable tasks for each user using a specific JQL filter
3. Presents tasks one-by-one to users via Telegram with Persian text
4. Collects status updates (time spent, delay reasons, status changes)
5. Allows users to request new subtasks (sent to PO for approval)

**Important**: This feature is integrated into the existing `__main__.py` - NO new Docker service required.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        __main__.py                               │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐  │
│  │ APScheduler     │  │ Telegram Application                 │  │
│  │ (Daily trigger) │──│  ├─ DailyTaskStatusHandler           │  │
│  │                 │  │  ├─ TaskCreationHandler              │  │
│  │                 │  │  └─ ... other handlers               │  │
│  └─────────────────┘  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Use Cases Layer                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ DailyTaskStatus (ConversationHandler-based)                 ││
│  │  States: TASK_DISPLAY → TIME_SPENT → DELAY_REASON →        ││
│  │          STATUS_UPDATE → SUBTASK_REQUEST → NEXT_TASK        ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Adapters Layer                               │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │ JiraServerRepository │  │ UserConfig                       │ │
│  │ + get_user_tasks()   │  │ + get_all_users()                │ │
│  │ + log_work()         │  │ + get_po_for_project()           │ │
│  │ + set_delay_reason() │  └──────────────────────────────────┘ │
│  └──────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

### New Files to Create

```
jira_telegram_bot/
├── entities/
│   └── daily_task_status.py              # Data models
├── use_cases/
│   ├── interfaces/
│   │   └── daily_task_status_interface.py # Interface definition
│   └── telegram_commands/
│       └── daily_task_status.py          # Main use case
├── frameworks/
│   └── telegram/
│       └── daily_task_status_handler.py  # Telegram handler
└── adapters/
    └── ai_models/
        └── ai_agents/
            └── prompts/
                └── subtask_suggestion.yaml # (Optional) AI prompt for subtask suggestions
```

### Files to Modify

```
jira_telegram_bot/
├── __main__.py                           # Add handler + scheduler
├── app_container.py                      # Register dependencies
├── config_dependency_injection.py        # Add bindings
├── use_cases/
│   └── interfaces/
│       └── task_manager_repository_interface.py  # Add new methods
└── adapters/
    └── jira/
        └── jira_server_repository.py     # Implement new methods
```

---

## Implementation Details

### 1. Entities (`entities/daily_task_status.py`)

```python
"""Data models for daily task status tracking."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class DelayReason(str, Enum):
    """Enumeration of possible delay reasons."""
    
    DEPENDENCY = "dependency"
    UNCLEAR_REQUIREMENTS = "unclear_requirements"
    TECHNICAL_ISSUES = "technical_issues"
    OTHER_PRIORITIES = "other_priorities"
    PERSONAL = "personal"
    BLOCKED = "blocked"
    WAITING_REVIEW = "waiting_review"
    OTHER = "other"


class TaskStatusUpdate(BaseModel):
    """Model for a single task status update from user."""
    
    issue_key: str
    action: str  # "log_time", "mark_progress", "report_delay", "skip"
    time_spent_hours: Optional[float] = None
    delay_reason: Optional[DelayReason] = None
    delay_comment: Optional[str] = None


class SubtaskRequest(BaseModel):
    """Model for subtask creation request."""
    
    parent_issue_key: str
    summary: str
    description: Optional[str] = None
    requested_by: str  # Telegram username
    project_key: str


class DailyStatusSession(BaseModel):
    """Model for tracking a user's daily status session."""
    
    telegram_user_id: int
    telegram_username: str
    jira_username: str
    tasks: List[str]  # List of issue keys
    current_task_index: int = 0
    updates: List[TaskStatusUpdate] = []
    is_complete: bool = False
```

---

### 2. Interface (`use_cases/interfaces/daily_task_status_interface.py`)

```python
"""Interface for daily task status use case."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from telegram import Update
from telegram.ext import CallbackContext


class DailyTaskStatusInterface(ABC):
    """Interface for daily task status tracking."""

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def trigger_for_all_users(
        self,
        application,
    ) -> None:
        """Trigger daily status check for all configured users.
        
        Args:
            application: Telegram Application instance.
        """
        pass
```

---

### 3. Add Methods to Task Manager Repository Interface

**File**: `use_cases/interfaces/task_manager_repository_interface.py`

Add these abstract methods:

```python
@abstractmethod
def get_user_actionable_tasks(self, jira_username: str) -> List[Issue]:
    """Get tasks that require user attention today.
    
    Uses JQL filter:
    assignee = {username} AND resolution = Unresolved AND 
    (Sprint in openSprints() AND ("Target start" <= now() OR "Target start" is EMPTY) 
    OR Sprint is EMPTY AND ("Target start" <= now() OR "Target start" is EMPTY)) 
    ORDER BY cf[10109] ASC
    
    Args:
        jira_username: Jira username to filter tasks for.
        
    Returns:
        List of Jira issues requiring attention.
    """
    pass

@abstractmethod
def log_work(
    self,
    issue_key: str,
    time_spent_seconds: int,
    comment: Optional[str] = None,
) -> None:
    """Log work time on an issue.
    
    Args:
        issue_key: Jira issue key (e.g., "PROJ-123").
        time_spent_seconds: Time spent in seconds.
        comment: Optional work log comment.
    """
    pass

@abstractmethod
def set_delay_reason(
    self,
    issue_key: str,
    reason: str,
    comment: Optional[str] = None,
) -> None:
    """Set delay reason on an issue.
    
    Args:
        issue_key: Jira issue key.
        reason: Delay reason value.
        comment: Optional comment explaining the delay.
    """
    pass

@abstractmethod
def get_available_transitions(self, issue_key: str) -> List[dict]:
    """Get available transitions for an issue.
    
    Args:
        issue_key: Jira issue key.
        
    Returns:
        List of available transitions with id and name.
    """
    pass
```

---

### 4. Implement Methods in Jira Server Repository

**File**: `adapters/jira/jira_server_repository.py`

```python
def get_user_actionable_tasks(self, jira_username: str) -> List[Issue]:
    """Get tasks that require user attention today.
    
    Args:
        jira_username: Jira username to filter tasks for.
        
    Returns:
        List of Jira issues requiring attention.
    """
    jql = (
        f'assignee = "{jira_username}" AND resolution = Unresolved AND '
        f'(Sprint in openSprints() AND ("Target start" <= now() OR "Target start" is EMPTY) '
        f'OR Sprint is EMPTY AND ("Target start" <= now() OR "Target start" is EMPTY)) '
        f'ORDER BY cf[10109] ASC'
    )
    
    try:
        issues = self.jira.search_issues(jql, maxResults=50)
        return issues
    except Exception as e:
        LOGGER.error(f"Failed to fetch actionable tasks for {jira_username}: {e}")
        return []

def log_work(
    self,
    issue_key: str,
    time_spent_seconds: int,
    comment: Optional[str] = None,
) -> None:
    """Log work time on an issue.
    
    Args:
        issue_key: Jira issue key (e.g., "PROJ-123").
        time_spent_seconds: Time spent in seconds.
        comment: Optional work log comment.
    """
    try:
        self.jira.add_worklog(
            issue=issue_key,
            timeSpentSeconds=time_spent_seconds,
            comment=comment,
        )
        LOGGER.info(f"Logged {time_spent_seconds}s on {issue_key}")
    except Exception as e:
        LOGGER.error(f"Failed to log work on {issue_key}: {e}")
        raise

def set_delay_reason(
    self,
    issue_key: str,
    reason: str,
    comment: Optional[str] = None,
) -> None:
    """Set delay reason on an issue.
    
    Args:
        issue_key: Jira issue key.
        reason: Delay reason value.
        comment: Optional comment explaining the delay.
        
    Note:
        Update the custom field ID based on your Jira configuration.
    """
    delay_reason_field = "customfield_XXXXX"  # UPDATE THIS
    
    try:
        issue = self.jira.issue(issue_key)
        issue.update(fields={delay_reason_field: reason})
        
        if comment:
            self.jira.add_comment(issue_key, comment)
            
        LOGGER.info(f"Set delay reason '{reason}' on {issue_key}")
    except Exception as e:
        LOGGER.error(f"Failed to set delay reason on {issue_key}: {e}")
        raise

def get_available_transitions(self, issue_key: str) -> List[dict]:
    """Get available transitions for an issue.
    
    Args:
        issue_key: Jira issue key.
        
    Returns:
        List of available transitions with id and name.
    """
    try:
        transitions = self.jira.transitions(issue_key)
        return [{"id": t["id"], "name": t["name"]} for t in transitions]
    except Exception as e:
        LOGGER.error(f"Failed to get transitions for {issue_key}: {e}")
        return []
```

---

### 5. Main Use Case (`use_cases/telegram_commands/daily_task_status.py`)

```python
"""Daily task status tracking use case."""
from __future__ import annotations

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

    # Conversation states
    (
        TASK_DISPLAY,
        TIME_SPENT,
        DELAY_REASON,
        DELAY_COMMENT,
        STATUS_TRANSITION,
        SUBTASK_REQUEST,
        SUBTASK_CONFIRM,
    ) = range(7)

    # Persian text constants
    TEXTS = {
        "greeting": "سلام! 👋\nوقت بررسی وضعیت تسک‌های امروز است.",
        "no_tasks": "🎉 تبریک! هیچ تسک فعالی برای امروز ندارید.",
        "task_header": "📋 تسک {index} از {total}",
        "task_details": (
            "*کلید:* `{key}`\n"
            "*عنوان:* {summary}\n"
            "*وضعیت:* {status}\n"
            "*استوری پوینت:* {points}\n"
            "*ددلاین:* {deadline}"
        ),
        "select_action": "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        "log_time": "⏱ ثبت زمان",
        "mark_progress": "🔄 تغییر وضعیت",
        "report_delay": "⚠️ گزارش تأخیر",
        "request_subtask": "➕ درخواست ساب‌تسک",
        "skip": "⏭ بعدی",
        "hours_prompt": "چند ساعت روی این تسک کار کرده‌اید؟",
        "hours_logged": "✅ {hours} ساعت برای تسک {key} ثبت شد.",
        "select_delay_reason": "لطفاً دلیل تأخیر را انتخاب کنید:",
        "delay_reasons": {
            DelayReason.DEPENDENCY: "🔗 وابستگی به تسک دیگر",
            DelayReason.UNCLEAR_REQUIREMENTS: "❓ نامشخص بودن نیازمندی‌ها",
            DelayReason.TECHNICAL_ISSUES: "🔧 مشکلات فنی",
            DelayReason.OTHER_PRIORITIES: "📊 اولویت‌های دیگر",
            DelayReason.PERSONAL: "👤 دلایل شخصی",
            DelayReason.BLOCKED: "🚫 بلاک شده",
            DelayReason.WAITING_REVIEW: "👀 در انتظار بررسی",
            DelayReason.OTHER: "📝 سایر",
        },
        "delay_comment_prompt": "لطفاً توضیحات بیشتر را وارد کنید (یا /skip برای رد شدن):",
        "delay_recorded": "✅ دلیل تأخیر ثبت شد.",
        "select_transition": "وضعیت جدید را انتخاب کنید:",
        "transition_done": "✅ وضعیت تسک به {status} تغییر کرد.",
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
        "cancel": "❌ عملیات لغو شد.",
        "back": "🔙 بازگشت",
        "hour_suffix": "ساعت",
        "error": "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
    }

    # Hours options for keyboard (3 per row)
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

    def _build_task_action_keyboard(self) -> InlineKeyboardMarkup:
        """Build keyboard for task actions.
        
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

    def _format_task_message(
        self,
        issue: Any,
        index: int,
        total: int,
    ) -> str:
        """Format a task for display.
        
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
        
        details = self.TEXTS["task_details"].format(
            key=issue.key,
            summary=issue.fields.summary,
            status=issue.fields.status.name,
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
        
        await update.message.reply_text(self.TEXTS["greeting"])
        
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
        
        keyboard = self._build_task_action_keyboard()
        
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
            keyboard = self._build_hours_keyboard()
            await query.edit_message_text(
                self.TEXTS["hours_prompt"],
                reply_markup=keyboard,
            )
            return self.TIME_SPENT
            
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
            
        return self.TASK_DISPLAY

    async def handle_time_spent(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle time spent selection.
        
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
        session = context.user_data["daily_status_session"]
        current_key = session.tasks[session.current_task_index]
        
        try:
            time_spent_seconds = int(hours * 3600)
            self.jira_repository.log_work(current_key, time_spent_seconds)
            
            session.updates.append(TaskStatusUpdate(
                issue_key=current_key,
                action="log_time",
                time_spent_hours=hours,
            ))
            
            await query.edit_message_text(
                self.TEXTS["hours_logged"].format(hours=hours, key=current_key)
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to log work: {e}")
            await query.edit_message_text(self.TEXTS["error"])
            
        session.current_task_index += 1
        return await self._show_current_task(update, context)

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
            
            await query.edit_message_text(
                self.TEXTS["transition_done"].format(status=new_status)
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to transition issue: {e}")
            await query.edit_message_text(self.TEXTS["error"])
            
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
        
        # Get PO for the project
        po_config = self._get_project_po(project_key)
        
        if not po_config:
            await update.message.reply_text("❌ مدیر پروژه یافت نشد.")
            session.current_task_index += 1
            return await self._show_current_task(update, context)
            
        # Create subtask request
        request = SubtaskRequest(
            parent_issue_key=current_key,
            summary=subtask_summary,
            requested_by=session.telegram_username,
            project_key=project_key,
        )
        
        # Send to PO
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
        # Implementation depends on your project_info structure
        # This is a placeholder - adapt to your actual implementation
        try:
            project_info = self.user_config.get_project_info(project_key)
            if project_info and project_info.po_username:
                return self.user_config.get_user_config_by_jira_username(
                    project_info.po_username
                )
        except Exception as e:
            LOGGER.error(f"Failed to get PO for project {project_key}: {e}")
        return None

    async def _finish_session(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Finish the daily status session and show summary.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            ConversationHandler.END
        """
        session: DailyStatusSession = context.user_data["daily_status_session"]
        
        # Build summary
        summary_lines = []
        for upd in session.updates:
            if upd.action == "log_time":
                summary_lines.append(f"⏱ {upd.issue_key}: {upd.time_spent_hours} ساعت")
            elif upd.action == "report_delay":
                summary_lines.append(f"⚠️ {upd.issue_key}: تأخیر گزارش شد")
                
        summary = "\n".join(summary_lines) if summary_lines else "هیچ تغییری ثبت نشد."
        
        message = self.TEXTS["all_tasks_done"].format(summary=summary)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message)
        else:
            await update.effective_chat.send_message(message)
            
        # Cleanup
        context.user_data.pop("daily_status_session", None)
        context.user_data.pop("daily_status_issues", None)
        context.user_data.pop("selected_delay_reason", None)
        
        return ConversationHandler.END

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
        
        all_users = self.user_config.get_all_users()
        
        for user_cfg in all_users:
            try:
                if not user_cfg.telegram_user_chat_id:
                    continue
                    
                jira_username = user_cfg.jira_username
                tasks = self.jira_repository.get_user_actionable_tasks(jira_username)
                
                if not tasks:
                    continue
                    
                # Send initial message to user
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
```

---

### 6. Telegram Handler (`frameworks/telegram/daily_task_status_handler.py`)

```python
"""Telegram handler for daily task status."""
from __future__ import annotations

from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from jira_telegram_bot.use_cases.interfaces.task_handler_interface import (
    TaskHandlerInterface,
)
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import (
    DailyTaskStatus,
)


class DailyTaskStatusHandler(TaskHandlerInterface):
    """Handler for daily task status conversation."""

    def __init__(self, daily_task_status_use_case: DailyTaskStatus):
        """Initialize the handler.
        
        Args:
            daily_task_status_use_case: The daily task status use case.
        """
        self.use_case = daily_task_status_use_case

    def get_handler(self) -> ConversationHandler:
        """Get the conversation handler.
        
        Returns:
            ConversationHandler for daily task status.
        """
        return ConversationHandler(
            entry_points=[
                CommandHandler("daily_status", self.use_case.start_daily_status),
            ],
            states={
                self.use_case.TASK_DISPLAY: [
                    CallbackQueryHandler(
                        self.use_case.handle_task_action,
                        pattern=r"^action\|",
                    ),
                ],
                self.use_case.TIME_SPENT: [
                    CallbackQueryHandler(
                        self.use_case.handle_time_spent,
                        pattern=r"^(hours\||back)$",
                    ),
                ],
                self.use_case.DELAY_REASON: [
                    CallbackQueryHandler(
                        self.use_case.handle_delay_reason,
                        pattern=r"^(delay\||back)$",
                    ),
                ],
                self.use_case.DELAY_COMMENT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.use_case.handle_delay_comment,
                    ),
                    CommandHandler("skip", self.use_case.handle_delay_comment),
                ],
                self.use_case.STATUS_TRANSITION: [
                    CallbackQueryHandler(
                        self.use_case.handle_transition,
                        pattern=r"^(transition\||back)$",
                    ),
                ],
                self.use_case.SUBTASK_REQUEST: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.use_case.handle_subtask_request,
                    ),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.use_case.cancel),
            ],
            per_user=True,
            per_chat=True,
        )

    async def cancel(self, update, context):
        """Cancel handler fallback.
        
        Args:
            update: Telegram update.
            context: Callback context.
            
        Returns:
            ConversationHandler.END
        """
        return await self.use_case.cancel(update, context)
```

---

### 7. Modify `__main__.py`

Add the following to `setup_and_run()`:

```python
# Add these imports at the top
from jira_telegram_bot.frameworks.telegram.daily_task_status_handler import (
    DailyTaskStatusHandler,
)
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import DailyTaskStatus
from jira_telegram_bot.frameworks.scheduler.ap_scheduler_service import APSchedulerService

# Inside setup_and_run(), after getting container:
daily_task_status_use_case = container[DailyTaskStatus]
daily_task_status_handler = DailyTaskStatusHandler(daily_task_status_use_case)

# Add handler
application.add_handler(daily_task_status_handler.get_handler())

# Setup scheduler for daily trigger
async def schedule_daily_tasks(application):
    """Schedule daily task status checks."""
    scheduler = APSchedulerService()
    
    async def daily_trigger():
        await daily_task_status_use_case.trigger_for_all_users(application)
    
    # Schedule for 9:00 AM daily (adjust as needed)
    await scheduler.schedule_daily_job(
        job_func=daily_trigger,
        hour=9,
        minute=0,
        job_name="daily_task_status_trigger",
    )
    await scheduler.start_scheduler()
    LOGGER.info("Daily task status scheduler started")

# Add post_init to application
application.post_init = schedule_daily_tasks

# Update help_command text to include new command
help_text = (
    "Here's how to use this bot:\n\n"
    "1. **/create_task** - Start creating a new task.\n"
    # ... existing commands ...
    "10. **/daily_status** - بررسی وضعیت تسک‌های روزانه\n"
    "11. **/cancel** - Cancel the current running operation"
)
```

---

### 8. Update `config_dependency_injection.py`

```python
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import DailyTaskStatus

# Add binding
container[DailyTaskStatus] = lambda c: DailyTaskStatus(
    jira_repository=c[TaskManagerRepositoryInterface],
    user_config=c[UserConfigInterface],
)
```

---

### 9. Update `app_container.py`

```python
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import DailyTaskStatus
from jira_telegram_bot.frameworks.telegram.daily_task_status_handler import DailyTaskStatusHandler

# Ensure DailyTaskStatus is available in container
# (If using Lagom auto-registration, this may be automatic)
```

---

## Testing

### Unit Tests (`tests/use_cases/test_daily_task_status.py`)

```python
"""Tests for daily task status use case."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.entities.daily_task_status import DelayReason, DailyStatusSession
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import DailyTaskStatus


class TestDailyTaskStatus(unittest.IsolatedAsyncioTestCase):
    """Test cases for DailyTaskStatus use case."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repo = MagicMock()
        self.mock_user_config = MagicMock()
        
        self.use_case = DailyTaskStatus(
            jira_repository=self.mock_jira_repo,
            user_config=self.mock_user_config,
        )

    async def test_start_daily_status_no_tasks(self):
        """Test starting daily status when user has no tasks."""
        # Arrange
        self.mock_user_config.get_user_config.return_value = MagicMock(
            jira_username="test_user"
        )
        self.mock_jira_repo.get_user_actionable_tasks.return_value = []
        
        update = MagicMock()
        update.effective_user.username = "test_telegram_user"
        update.message.reply_text = AsyncMock()
        
        context = MagicMock()
        context.user_data = {}
        
        # Act
        result = await self.use_case.start_daily_status(update, context)
        
        # Assert
        update.message.reply_text.assert_called_once()
        self.assertIn("تبریک", update.message.reply_text.call_args[0][0])

    async def test_a_build_hours_keyboard_has_correct_layout(self):
        """Test that hours keyboard has 3 buttons per row."""
        # Act
        keyboard = self.use_case._build_hours_keyboard()
        
        # Assert
        for row in keyboard.inline_keyboard[:-1]:  # Exclude back button row
            self.assertLessEqual(len(row), 3)

    def test_format_task_message_persian(self):
        """Test that task messages are formatted in Persian."""
        # Arrange
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Test task"
        mock_issue.fields.status.name = "To Do"
        mock_issue.fields.customfield_10106 = 3
        mock_issue.fields.duedate = "2025-01-15"
        
        # Act
        message = self.use_case._format_task_message(mock_issue, 1, 5)
        
        # Assert
        self.assertIn("تسک", message)
        self.assertIn("TEST-123", message)


if __name__ == "__main__":
    unittest.main()
```

---

## Configuration Notes

### Environment Variables (Optional)

Add to your `.env` or environment:

```bash
DAILY_STATUS_HOUR=9
DAILY_STATUS_MINUTE=0
DELAY_REASON_CUSTOM_FIELD=customfield_XXXXX
```

### Jira Custom Fields

Update these field IDs in the repository implementation:
- `customfield_10106` - Story Points (verify this is correct)
- `customfield_XXXXX` - Delay Reason field
- `cf[10109]` - The field used for ordering in JQL

---

## Checklist

- [ ] Create `entities/daily_task_status.py`
- [ ] Create `use_cases/interfaces/daily_task_status_interface.py`
- [ ] Create `use_cases/telegram_commands/daily_task_status.py`
- [ ] Create `frameworks/telegram/daily_task_status_handler.py`
- [ ] Update `task_manager_repository_interface.py` with new methods
- [ ] Implement new methods in `jira_server_repository.py`
- [ ] Update `config_dependency_injection.py`
- [ ] Update `app_container.py`
- [ ] Modify `__main__.py` to add handler and scheduler
- [ ] Update help command text
- [ ] Create unit tests
- [ ] Test manually with `/daily_status` command
- [ ] Verify scheduler triggers at correct time

---

## Notes

1. **No new Docker service needed** - Everything runs in the existing `telegram-bot` service.

2. **APScheduler integration** - Uses the existing `APSchedulerService` for scheduling.

3. **Persian text** - All user-facing text is in Persian.

4. **Inline keyboards** - All selections use inline keyboards with 3 buttons per row.

5. **Sequential task processing** - Tasks are shown one-by-one, waiting for user action before proceeding.

6. **PO notifications** - Subtask requests are sent to the project's PO for approval.

7. **Custom field mapping** - Update the custom field IDs based on your Jira configuration.
