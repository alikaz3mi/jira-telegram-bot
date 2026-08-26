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
from urllib.parse import quote
from typing import List
from typing import Optional
from typing import Sequence

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.file_storage.entity_alias_repository import (
    EntityAliasRepository,
)
from jira_telegram_bot.entities.assistant_entities import EntityKind
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
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


# Jira Server keeps the Epic Link in a custom field; this instance uses
# customfield_10100 (see .claude/rules/jira-conventions.md).
EPIC_LINK_FIELD = "customfield_10100"


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
        task_manager_repository=None,
    ):
        """Initialize the tool set.

        Args:
            context: Who is asking and what they may see
            get_user_daily_tasks_use_case: Source of a person's open tasks
            alias_repository: Resolves names to Jira keys and usernames
            base_url: Jira base URL, used to build issue links
            task_manager_repository: Reads parent Stories and Epics, whose
                descriptions explain a Sub-task that carries none of its own
        """
        self.context = context
        self.get_user_daily_tasks = get_user_daily_tasks_use_case
        self.aliases = alias_repository
        self.base_url = base_url.rstrip("/")
        self.task_manager_repository = task_manager_repository

    async def list_tasks(
        self,
        person: Optional[str] = None,
        project: Optional[str] = None,
        status: Optional[str] = None,
        issue_type: Optional[str] = None,
        in_active_sprint: Optional[bool] = None,
        due_within_days: Optional[int] = None,
    ) -> str:
        """List open tasks, filtered the way the question asked.

        Args:
            person: Whose tasks, as the user named them; None means the caller
            project: Which product or project, as the user named it
            status: A Jira status to keep, matched case-insensitively
            issue_type: Keep only this issue type, e.g. "Story" or "Bug"
            in_active_sprint: True keeps only work in an open sprint; False
                keeps only work that belongs to no sprint
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

        if issue_type:
            wanted_type = issue_type.strip().casefold()
            tasks = [
                task for task in tasks
                if (task.issue_type or "").casefold() == wanted_type
            ]

        if in_active_sprint is not None:
            # The daily list mixes sprint work with unscheduled work, so
            # "in the active sprint" has to be asked for explicitly.
            tasks = [
                task for task in tasks
                if bool(task.sprint_name) is in_active_sprint
            ]

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

    async def task_details(self, issue_key: str) -> str:
        """Explain what one task actually asks for.

        Args:
            issue_key: The Jira key, e.g. "FOLLOWUP-128"

        Returns:
            The task's description and status, or a refusal when the caller
            may not read it.
        """
        key = (issue_key or "").strip().upper()
        if not key:
            return "کدام تسک؟ کلید تسک را بگویید."

        for task in await self._fetch(self.context.jira_username):
            if task.issue_key.upper() == key:
                return self._describe(task)

        # The daily list deliberately omits backlog and finished work, but a
        # person can still ask about their own task by key. Fall back to a
        # direct read, with the same permission check applied in Python.
        return await self._describe_by_key(key)

    async def _describe_by_key(self, key: str) -> str:
        """Describe any single issue the caller is allowed to read.

        Args:
            key: The Jira key, already upper-cased

        Returns:
            The task's details, or a refusal when it is someone else's.
        """
        jira = self._jira()
        if not jira:
            return f"«{key}» بین تسک‌های باز شما نیست."

        try:
            issue = jira.issue(key)
        except Exception:
            return f"«{key}» را در جیرا پیدا نکردم."

        assignee = getattr(getattr(issue.fields, "assignee", None), "name", "")
        if not self.context.may_read(assignee or ""):
            LOGGER.info(
                f"{self.context.jira_username} denied task_details on {key}",
            )
            return DENIED

        return self._describe(
            DailyTaskCheck(
                issue_key=issue.key,
                summary=issue.fields.summary,
                status=issue.fields.status.name,
                assignee=assignee or "",
                check_status=TaskCheckStatus.OK,
                project_key=issue.key.split("-")[0],
                description=getattr(issue.fields, "description", None),
            ),
        )

    def _describe(self, task: DailyTaskCheck) -> str:
        """Render one task at length, description included.

        Args:
            task: The task to describe

        Returns:
            The task, its status and what it asks for.
        """
        lines = [f"{self._link(task.issue_key)} — {task.summary}"]
        lines.append(f"وضعیت: {task.status}")
        if task.target_end:
            lines.append(f"مهلت: {task.target_end:%Y-%m-%d}")
        if task.dependencies and not task.dependencies_completed:
            blockers = "، ".join(task.dependencies)
            lines.append(f"وابسته به: {blockers}")
        if task.worklog_hours:
            lines.append(f"ثبت‌شده: {self._hours(task.worklog_hours)} ساعت")

        description = (task.description or "").strip()
        if description:
            lines.append("")
            lines.append(self._trim(description))
        else:
            # A Sub-task usually carries no description of its own; the work
            # is explained on the Story it belongs to, and the reason for it
            # on the Epic above that. Saying "no description" while that text
            # sits one link away is unhelpful.
            inherited = self._inherited_context(task.issue_key)
            if inherited:
                lines.append("")
                lines.extend(inherited)
            else:
                lines.append("")
                lines.append("این تسک و والدینش توضیحی در جیرا ندارند.")

        related = self._related(task.issue_key)
        if related:
            lines.append("")
            lines.append("تسک‌های مرتبط:")
            lines.extend(related)

        attachments = self._attachments(task.issue_key)
        if attachments:
            lines.append("")
            lines.append("پیوست‌ها:")
            lines.extend(attachments)
        return "\n".join(lines)

    def _jira(self):
        """Return the Jira client, or None when the tools were built without one."""
        repository = self.task_manager_repository
        return getattr(repository, "jira", None) if repository else None

    def _inherited_context(self, issue_key: str) -> List[str]:
        """Pull the description from the task's Story, then its Epic.

        Args:
            issue_key: The task whose parents should be read

        Returns:
            Rendered lines describing the parents that carry text, nearest
            first, or an empty list when none of them do.
        """
        lines: List[str] = []
        if not self._jira():
            return lines
        try:
            for parent_key, label in self._parent_chain(issue_key):
                fields = self._jira().issue(parent_key).fields
                text = (getattr(fields, "description", "") or "").strip()
                if not text:
                    continue
                lines.append(f"{label} {self._link(parent_key)}: {fields.summary}")
                lines.append(self._trim(text))
                lines.append("")
        except Exception as exc:
            LOGGER.warning(f"Could not read parents of {issue_key}: {exc}")
        return [line for line in lines if line is not None][:-1] if lines else []

    def _parent_chain(self, issue_key: str):
        """Yield (key, label) for the task's Story and Epic, nearest first.

        Args:
            issue_key: The task to walk up from

        Yields:
            The parent Story, then the Epic above it, when each exists.
        """
        jira = self._jira()
        if not jira:
            return
        fields = jira.issue(issue_key).fields

        parent = getattr(fields, "parent", None)
        epic_key = getattr(fields, EPIC_LINK_FIELD, None)

        if parent is not None:
            yield parent.key, "از استوری"
            parent_fields = jira.issue(parent.key).fields
            epic_key = epic_key or getattr(parent_fields, EPIC_LINK_FIELD, None)

        if epic_key:
            yield epic_key, "از اپیک"

    def _related(self, issue_key: str) -> List[str]:
        """List issues linked to this one, with the relation named.

        A "blocks" / "is blocked by" edge is often the answer to "what do I
        actually do here" — it says what has to land first and what is
        waiting on this.

        Args:
            issue_key: The task to read

        Returns:
            One line per linked issue, or an empty list.
        """
        if not self._jira():
            return []
        try:
            fields = self._jira().issue(issue_key).fields
        except Exception as exc:
            LOGGER.warning(f"Could not read links of {issue_key}: {exc}")
            return []

        lines: List[str] = []
        for link in getattr(fields, "issuelinks", None) or []:
            other = getattr(link, "outwardIssue", None)
            relation = link.type.outward if other else link.type.inward
            other = other or getattr(link, "inwardIssue", None)
            if other is None:
                continue
            summary = (getattr(other.fields, "summary", "") or "").strip()
            status = getattr(getattr(other.fields, "status", None), "name", "")
            suffix = f" (وضعیت: {status})" if status else ""
            lines.append(
                f"{relation}: {self._link(other.key)} — {summary}{suffix}",
            )
        return lines

    def _attachments(self, issue_key: str) -> List[str]:
        """List the task's attachments as links.

        Args:
            issue_key: The task to read

        Returns:
            One line per attachment, or an empty list.
        """
        if not self._jira():
            return []
        try:
            fields = self._jira().issue(issue_key).fields
            return [
                f'<a href="{item.content}">{item.filename}</a>'
                for item in (getattr(fields, "attachment", None) or [])
            ]
        except Exception as exc:
            LOGGER.warning(f"Could not read attachments of {issue_key}: {exc}")
            return []

    @staticmethod
    def _trim(text: str, limit: int = 1200) -> str:
        """Shorten long description text for a phone screen."""
        text = text.strip()
        return f"{text[:limit - 1]}…" if len(text) > limit else text

    async def board_link(
        self,
        person: Optional[str] = None,
        project: Optional[str] = None,
    ) -> str:
        """Give a Jira link listing someone's open issues.

        A chat answer is capped and summarised; when the user wants to see
        everything, or scan it themselves, a link is the honest reply.

        Args:
            person: Whose issues, as the user named them; None means the caller
            project: Optional product name to narrow the list

        Returns:
            A browsable Jira URL, or a refusal when the person is not readable.
        """
        target, error = self._resolve_person(person)
        if error:
            return error

        clauses = [f'assignee = "{target}"', "resolution = Unresolved"]
        if project:
            resolution = self.aliases.resolve(project, EntityKind.PROJECT)
            if not resolution.resolved:
                return f"«{project}» را نشناختم."
            clauses.append(f"project = {resolution.resolved.canonical}")

        jql = " AND ".join(clauses) + " ORDER BY updated DESC"
        url = f"{self.base_url}/issues/?jql={quote(jql)}"
        return f'<a href="{url}">همه تسک‌های {self._label(target, person)}</a>'

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
