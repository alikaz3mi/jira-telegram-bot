"""The tools the assistant may call, and the rules they enforce.

Every tool is parameterised rather than free-form: the model chooses which
tool and fills typed arguments, but never writes a query. That keeps two
things true. Authorisation is decided in Python from the bound context, so
no prompt can widen it; and a question that is really a filter — one
project, one person, one week — is answered by a filter rather than by
similarity, which cannot promise it found everything.
"""
from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import List
from typing import Optional
from typing import Sequence

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.file_storage.entity_alias_repository import (
    EntityAliasRepository,
)
from jira_telegram_bot.entities.assistant_entities import EntityKind
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext

# Said back to the model, which relays it. Phrased so the person understands
# the refusal came from a rule rather than a failure to find anything.
DENIED = (
    "شما اجازه دیدن تسک‌های افراد دیگر را ندارید. "
    "فقط می‌توانید درباره تسک‌های خودتان بپرسید."
)


class AssistantTools:
    """Data access for the assistant, scoped to one caller.

    Built per request so the caller is captured here rather than passed as a
    tool argument the model could fill with somebody else's name.
    """

    def __init__(
        self,
        context: AssistantContext,
        get_user_daily_tasks_use_case,
        alias_repository: EntityAliasRepository,
        base_url: str = "",
    ):
        """Initialize the tool set.

        Args:
            context: Who is asking and what they may see
            get_user_daily_tasks_use_case: Source of a person's open tasks
            alias_repository: Resolves names to Jira keys and usernames
            base_url: Jira base URL, used to build issue links
        """
        self.context = context
        self.get_user_daily_tasks = get_user_daily_tasks_use_case
        self.aliases = alias_repository
        self.base_url = base_url.rstrip("/")

    async def list_tasks(
        self,
        person: Optional[str] = None,
        project: Optional[str] = None,
        status: Optional[str] = None,
        due_within_days: Optional[int] = None,
    ) -> str:
        """List open tasks, filtered the way the question asked.

        Args:
            person: Whose tasks, as the user named them; None means the caller
            project: Which product or project, as the user named it
            status: A Jira status to keep, matched case-insensitively
            due_within_days: Keep only tasks due within this many days

        Returns:
            One line per task, or a message explaining why there are none.
        """
        target, error = self._resolve_person(person)
        if error:
            return error

        tasks = await self._fetch(target)
        if not tasks:
            return f"هیچ تسک بازی برای {self._label(target, person)} پیدا نشد."

        if project:
            resolution = self.aliases.resolve(project, EntityKind.PROJECT)
            match = resolution.resolved
            if not match:
                options = ", ".join(
                    f"{candidate.display_name}" for candidate in resolution.matches
                ) or "چیزی"
                return (
                    f"منظورتان از «{project}» را نفهمیدم. "
                    f"گزینه‌های نزدیک: {options}"
                )
            tasks = [task for task in tasks if task.project_key == match.canonical]
            if not tasks:
                return (
                    f"{self._label(target, person)} در "
                    f"{match.display_name} تسک بازی ندارد."
                )

        if status:
            wanted = status.strip().casefold()
            tasks = [task for task in tasks if (task.status or "").casefold() == wanted]

        if due_within_days is not None:
            horizon = datetime.now() + timedelta(days=due_within_days)
            tasks = [
                task for task in tasks
                if task.target_end and task.target_end <= horizon
            ]

        if not tasks:
            return f"با این شرط‌ها تسکی برای {self._label(target, person)} نماند."

        return self._render(tasks)

    async def count_tasks(
        self,
        person: Optional[str] = None,
        project: Optional[str] = None,
    ) -> str:
        """Count open tasks, broken down by project.

        A count has to see every row, which is why it is a filter over the
        whole list rather than a similarity search that returns a top few.

        Args:
            person: Whose tasks, as the user named them; None means the caller
            project: Restrict to one product or project

        Returns:
            The total, and the per-project breakdown when no project was named.
        """
        target, error = self._resolve_person(person)
        if error:
            return error

        tasks = await self._fetch(target)
        label = self._label(target, person)

        if project:
            resolution = self.aliases.resolve(project, EntityKind.PROJECT)
            match = resolution.resolved
            if not match:
                return f"منظورتان از «{project}» را نفهمیدم."
            tasks = [task for task in tasks if task.project_key == match.canonical]
            return f"{label} در {match.display_name} {len(tasks)} تسک باز دارد."

        if not tasks:
            return f"{label} تسک بازی ندارد."

        counts: dict[str, int] = {}
        for task in tasks:
            counts[task.project_key] = counts.get(task.project_key, 0) + 1
        breakdown = "، ".join(
            f"{key}: {count}"
            for key, count in sorted(counts.items(), key=lambda item: -item[1])
        )
        return f"{label} در مجموع {len(tasks)} تسک باز دارد ({breakdown})."

    async def logged_hours(self, person: Optional[str] = None) -> str:
        """Report hours already logged against a person's open tasks.

        Args:
            person: Whose hours, as the user named them; None means the caller

        Returns:
            The total and the tasks that carry it.
        """
        target, error = self._resolve_person(person)
        if error:
            return error

        tasks = await self._fetch(target)
        logged = [task for task in tasks if task.worklog_hours]
        total = round(sum(task.worklog_hours for task in logged), 2)
        label = self._label(target, person)

        if not logged:
            return f"روی تسک‌های باز {label} ساعتی ثبت نشده است."

        lines = [f"{label} مجموعاً {self._hours(total)} ساعت ثبت کرده است:"]
        for task in sorted(logged, key=lambda item: -item.worklog_hours):
            lines.append(
                f"{self._link(task.issue_key)} — {self._hours(task.worklog_hours)} ساعت",
            )
        return "\n".join(lines)

    def whoami(self) -> str:
        """Describe the caller, so the model stops asking who it is talking to.

        Returns:
            The caller's Jira username and what they may read.
        """
        scope = (
            "می‌تواند درباره همه اعضا بپرسد"
            if self.context.role.may_read_others
            else "فقط به تسک‌های خودش دسترسی دارد"
        )
        return f"کاربر {self.context.jira_username} ({self.context.role.value}) — {scope}"

    def _resolve_person(
        self,
        person: Optional[str],
    ) -> tuple[str, Optional[str]]:
        """Work out whose tasks are meant, and whether that is allowed.

        Args:
            person: The name the user used, or None for themselves

        Returns:
            The Jira username, and an error message when the request is
            refused or the name could not be resolved.
        """
        if not person:
            return self.context.jira_username, None

        resolution = self.aliases.resolve(person, EntityKind.PERSON)
        match = resolution.resolved
        if not match:
            if resolution.is_ambiguous:
                options = "، ".join(
                    candidate.display_name for candidate in resolution.matches
                )
                return "", f"منظورتان کدام‌یک است؟ {options}"
            return "", f"«{person}» را پیدا نکردم."

        if not self.context.may_read(match.canonical):
            LOGGER.info(
                f"{self.context.jira_username} ({self.context.role.value}) "
                f"denied access to {match.canonical}",
            )
            return "", DENIED

        return match.canonical, None

    async def _fetch(self, jira_username: str) -> Sequence[DailyTaskCheck]:
        """Fetch a person's open tasks.

        Args:
            jira_username: Whose tasks to fetch

        Returns:
            The tasks, or an empty list when the lookup fails.
        """
        try:
            return await self.get_user_daily_tasks.execute(
                jira_username=jira_username,
            )
        except Exception as exc:
            LOGGER.error(f"Could not fetch tasks for {jira_username}: {exc}")
            return []

    def _label(self, jira_username: str, spoken: Optional[str]) -> str:
        """Name the person in a reply the way the user referred to them."""
        if jira_username.lower() == self.context.jira_username.lower():
            return "شما"
        return spoken or jira_username

    def _render(self, tasks: Sequence[DailyTaskCheck]) -> str:
        """Render tasks one per line, each key linked."""
        lines = []
        for task in tasks:
            summary = (task.summary or "").strip()
            if len(summary) > 60:
                summary = f"{summary[:59]}…"
            lines.append(
                f"{self._link(task.issue_key)} — {summary} (وضعیت: {task.status})",
            )
        return "\n".join(lines)

    def _link(self, issue_key: str) -> str:
        """Render an issue key as a Telegram HTML link."""
        if not self.base_url:
            return issue_key
        return f'<a href="{self.base_url}/browse/{issue_key}">{issue_key}</a>'

    @staticmethod
    def _hours(hours: float) -> str:
        """Render hours without a trailing ``.0`` on whole numbers."""
        return str(int(hours)) if float(hours).is_integer() else str(round(hours, 2))
