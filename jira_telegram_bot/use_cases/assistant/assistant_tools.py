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

# Interrupt-worthy. Anything below this is the ordinary backlog, and
# leading with it would make the urgent section meaningless.
URGENT_PRIORITIES = ("Highest", "High")

# A briefing is read on a phone before a standup.
MAX_PURPOSE_EPICS = 5
MAX_OWN_SHARE = 8
MAX_MEDIA = 3

# Spoken discipline -> the unit string recorded in `user_components`. These
# issues carry no component or label in Jira, so a person's configured unit
# is the only record of who does design, backend, and so on.
_UNIT_ALIASES = {
    "طراحی": "UI/UX", "دیزاین": "UI/UX", "یو‌آی": "UI/UX", "یوآی": "UI/UX",
    "رابط کاربری": "UI/UX", "ui": "UI/UX", "ux": "UI/UX", "ui/ux": "UI/UX",
    "design": "UI/UX",
    "بک‌اند": "Backend", "بکند": "Backend", "بک اند": "Backend",
    "backend": "Backend", "back-end": "Backend",
    "فرانت": "Front-end", "فرانت‌اند": "Front-end", "فرانت اند": "Front-end",
    "frontend": "Front-end", "front-end": "Front-end",
    "هوش": "AI", "هوش مصنوعی": "AI", "ai": "AI",
    "دواپس": "DevOps", "devops": "DevOps", "زیرساخت": "DevOps",
}


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
        user_config_repository=None,
        media_sink=None,
        rank_candidates_use_case=None,
    ):
        """Initialize the tool set.

        Args:
            context: Who is asking and what they may see
            get_user_daily_tasks_use_case: Source of a person's open tasks
            alias_repository: Resolves names to Jira keys and usernames
            base_url: Jira base URL, used to build issue links
            task_manager_repository: Reads parent Stories and Epics, whose
                descriptions explain a Sub-task that carries none of its own
            user_config_repository: Maps people to the unit they work in on
                a project, which is the only record of who does design
            media_sink: List a tool appends attachments to, for the
                handler to send after the answer
            rank_candidates_use_case: Ranks issues against a topic by
                meaning, so «اینستاگرام» finds «ویترین» and «کامنت» too
        """
        self.context = context
        self.get_user_daily_tasks = get_user_daily_tasks_use_case
        self.aliases = alias_repository
        self.base_url = base_url.rstrip("/")
        self.task_manager_repository = task_manager_repository
        self.user_config_repository = user_config_repository
        # Attachments a tool wants sent as real files. Telegram cannot fetch
        # an authenticated Jira URL, so a link is a dead end for the reader;
        # the handler downloads what lands here and uploads the bytes.
        self.media_sink = media_sink if media_sink is not None else []
        self.rank_candidates = rank_candidates_use_case

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

    async def my_briefing(self, project: Optional[str] = None) -> str:
        """Open a check-in with what matters before what is merely assigned.

        A bare list of issue keys makes somebody reconstruct the point of
        their own sprint. This leads with anything on fire, then what the
        sprint is actually for, and only then their own share of it.

        Args:
            project: Restrict to one product, as the user named it

        Returns:
            The briefing, ready to send as Telegram HTML.
        """
        project_key = None
        if project:
            match, error = self._resolve_project(project)
            if error:
                return error
            project_key = match.canonical

        tasks = await self._fetch(self.context.jira_username)
        if project_key:
            tasks = [task for task in tasks if task.project_key == project_key]

        sections: List[str] = []
        urgent = await self._urgent_bugs(project_key)
        if urgent:
            sections.append(self._render_urgent(urgent))

        purpose = await self._sprint_purpose(project_key or self._busiest(tasks))
        if purpose:
            sections.append(purpose)

        sections.append(self._render_own_share(tasks))

        if not sections:
            return "چیزی برای گزارش پیدا نکردم."
        return "\n\n".join(section for section in sections if section)

    async def _urgent_bugs(self, project_key: Optional[str]) -> List:
        """The caller's own unresolved bugs at a priority worth interrupting for.

        Args:
            project_key: Restrict to one project, or None for all

        Returns:
            The bugs, highest priority first.
        """
        if not self.task_manager_repository:
            return []

        clauses = [
            f'assignee = "{self.context.jira_username}"',
            "issuetype = Bug",
            "resolution = Unresolved",
            # Some workflows reach Cancel or Done without ever setting a
            # resolution, so `Unresolved` alone still returns finished work.
            # Announcing a cancelled bug as urgent is worse than silence.
            "statusCategory != Done",
            f"priority in ({', '.join(URGENT_PRIORITIES)})",
        ]
        if project_key:
            clauses.append(f'project = "{project_key}"')

        try:
            return self.task_manager_repository.search_issues(
                jql=" AND ".join(clauses) + " ORDER BY priority DESC",
                max_results=10,
                fields="summary,status,priority,attachment",
            )
        except Exception as exc:
            LOGGER.error(f"Urgent bug lookup failed: {exc}")
            return []

    def _render_urgent(self, bugs: Sequence) -> str:
        """Render the urgent bugs, queueing any screenshot they carry."""
        lines = [f"🔴 {len(bugs)} باگ فوری روی شماست:"]
        for bug in bugs:
            priority = getattr(
                getattr(bug.fields, "priority", None), "name", "",
            )
            summary = str(getattr(bug.fields, "summary", "") or "").strip()
            if len(summary) > 55:
                summary = f"{summary[:54]}…"
            status = getattr(getattr(bug.fields, "status", None), "name", "?")
            lines.append(
                f"   {self._link(str(bug.key))} — {summary} "
                f"({priority}، {status})",
            )
            self._queue_media(bug)
        return "\n".join(lines)

    def _queue_media(self, issue) -> None:
        """Queue an issue's images for sending alongside the answer.

        A bug report's screenshot is usually the fastest way to understand
        it, and a link to it behind Jira's login is not something a person
        can glance at on a phone.

        Args:
            issue: The issue whose attachments to queue
        """
        for item in (getattr(issue.fields, "attachment", None) or [])[:MAX_MEDIA]:
            mime = str(getattr(item, "mimeType", "") or "")
            if not mime.startswith(("image/", "video/")):
                continue
            self.media_sink.append({
                "issue_key": str(issue.key),
                "filename": str(getattr(item, "filename", "") or "file"),
                "mime": mime,
                "attachment": item,
            })

    async def _sprint_purpose(self, project_key: Optional[str]) -> str:
        """Say what the current sprint is for, in terms of its epics.

        No sprint here carries a goal, so the epics its stories belong to
        are the only statement of intent the data holds.

        Args:
            project_key: The project whose sprint to describe

        Returns:
            The rendered section, or an empty string when unavailable.
        """
        if not project_key or not self.task_manager_repository:
            return ""

        try:
            stories = self.task_manager_repository.search_issues(
                jql=(
                    f'project = "{project_key}" '
                    f"AND sprint in openSprints() AND issuetype = Story"
                ),
                max_results=100,
                fields=f"summary,{EPIC_LINK_FIELD}",
            )
        except Exception as exc:
            LOGGER.error(f"Sprint purpose lookup failed: {exc}")
            return ""

        if not stories:
            return ""

        grouped, _ = self._group_by_epic(stories)
        if not grouped:
            return ""

        lines = [f"🎯 اسپرینت جاری {project_key} روی این‌ها متمرکز است:"]
        ordered = sorted(grouped.items(), key=lambda item: -len(item[1]))
        for epic_key, epic_stories in ordered[:MAX_PURPOSE_EPICS]:
            title = self._epic_title(epic_key) or epic_key
            lines.append(
                f"   • {title} ({len(epic_stories)} استوری) "
                f"{self._link(epic_key)}",
            )
        return "\n".join(lines)

    @staticmethod
    def _is_finished(task: DailyTaskCheck) -> bool:
        """Whether a task is over, whatever its resolution field says."""
        return (task.status or "").strip().lower() in {
            "done", "closed", "resolved", "cancel", "cancelled", "canceled",
        }

    @staticmethod
    def _busiest(tasks: Sequence[DailyTaskCheck]) -> Optional[str]:
        """The project whose current sprint the person is most committed to.

        Counting all open work picks whichever project has the largest
        backlog, which is usually not the one running a sprint. Sprint
        commitments decide it, and only when there are none does the
        overall count stand in.

        Args:
            tasks: The person's open tasks

        Returns:
            The project key, or None when they have no open work.
        """
        committed: dict = {}
        overall: dict = {}
        for task in tasks:
            overall[task.project_key] = overall.get(task.project_key, 0) + 1
            if task.sprint_name:
                committed[task.project_key] = committed.get(task.project_key, 0) + 1

        pool = committed or overall
        return max(pool, key=pool.get) if pool else None

    def _render_own_share(self, tasks: Sequence[DailyTaskCheck]) -> str:
        """Render the caller's own work, sprint commitments first."""
        tasks = [task for task in tasks if not self._is_finished(task)]
        if not tasks:
            return "📋 تسک بازی روی شما نیست."

        in_sprint = [task for task in tasks if task.sprint_name]
        shown = in_sprint or list(tasks)

        heading = (
            f"📋 سهم شما از اسپرینت ({len(in_sprint)} مورد):"
            if in_sprint
            else f"📋 کارهای باز شما ({len(tasks)} مورد):"
        )
        lines = [heading]
        for task in shown[:MAX_OWN_SHARE]:
            lines.append(f"   {self._one_line(task)}")

        hidden = len(shown) - MAX_OWN_SHARE
        if hidden > 0:
            lines.append(f"   و {hidden} مورد دیگر")
        return "\n".join(lines)

    async def sprint_board(
        self,
        project: str,
        unit: Optional[str] = None,
        person: Optional[str] = None,
        issue_type: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> str:
        """List what a project's open sprint holds, for the whole team.

        The per-person tools cannot answer this. They query
        ``assignee = <caller>``, so "what design work is in the sprint?"
        came back as the caller's own backend stories relabelled as design
        — a confident wrong answer about somebody else's work.

        Args:
            project: The product or project, as the user named it
            unit: The discipline asked about — «طراحی», «بک‌اند», «فرانت»,
                «هوش», «دواپس» — resolved through each person's recorded
                unit on this project
            person: Restrict to one person, as the user named them
            issue_type: Restrict to one issue type, e.g. "Story"
            topic: A subject to search for — «اینستاگرام», «سهمیه». Matched
                by meaning, so related wording is found too

        Returns:
            The sprint's issues grouped by assignee, or why there are none.
        """
        match, error = self._resolve_project(project)
        if error:
            return error

        if not self.task_manager_repository:
            return "دسترسی به جیرا برای این پرسش در دسترس نیست."

        allowed, denial = await self._may_read_project(match.canonical)
        if not allowed:
            return denial

        # A filter that could not be applied must never be silently
        # dropped: the answer would describe the whole sprint while the
        # question asked for one slice of it.
        owners: Optional[set] = None
        if unit:
            owners, unit_error = self._unit_members(unit, match.canonical)
            if unit_error:
                return unit_error

        target = None
        if person:
            target, person_error = self._resolve_person(person)
            if person_error:
                return person_error

        try:
            issues = self.task_manager_repository.search_issues(
                jql=(
                    f'project = "{match.canonical}" '
                    f"AND sprint in openSprints()"
                ),
                max_results=200,
                fields="summary,status,assignee,issuetype",
            )
        except Exception as exc:
            LOGGER.error(f"Sprint board lookup failed for {match.canonical}: {exc}")
            return "خواندن اسپرینت جاری از جیرا ناموفق بود."

        if not issues:
            return f"اسپرینت جاری {match.display_name} خالی است."

        total = len(issues)
        kept = [
            issue for issue in issues
            if self._matches_filters(issue, owners, target, issue_type)
        ]

        if topic:
            kept, topic_error = await self._by_topic(topic, kept)
            if topic_error:
                return topic_error

        if not kept:
            return self._nothing_matched(
                match, unit, person, issue_type, topic, total,
            )

        return self._render_board(match, kept, unit or topic, person, total)

    async def _by_topic(self, topic: str, issues: Sequence) -> tuple:
        """Keep the issues that are about a subject, by meaning not wording.

        A keyword filter answers "Instagram" with only the issues that spell
        it out, missing «ویترین» and «کامنت» that are plainly the same work.
        Ranking by embedding finds those, and — unlike the model reading a
        whole sprint — can say that nothing matched.

        Args:
            topic: The subject asked about
            issues: The issues still in play

        Returns:
            The matching issues, and an error message when the search could
            not run at all.
        """
        if not self.rank_candidates:
            return [], (
                "جست‌وجوی موضوعی در دسترس نیست، پس نمی‌توانم مطمئن باشم "
                "فهرست کامل است."
            )

        texts = [
            str(getattr(getattr(issue, "fields", None), "summary", "") or "")
            for issue in issues
        ]
        ranked = await self.rank_candidates.rank_texts(topic, texts)

        if ranked is None:
            # Returning everything here would be the original bug: a list
            # the reader takes for the answer to their question.
            return [], (
                "جست‌وجوی موضوعی الان کار نکرد. دوباره بپرسید یا بدون "
                "موضوع بپرسید تا کل اسپرینت را بدهم."
            )

        return [issues[index] for index, _ in ranked], None



    def _matches_filters(
        self,
        issue,
        owners: Optional[set],
        target: Optional[str],
        issue_type: Optional[str],
    ) -> bool:
        """Whether one sprint issue survives the filters that were asked for."""
        assignee = self._assignee_of(issue)

        if owners is not None:
            if not assignee or assignee.lower() not in owners:
                return False

        if target and (not assignee or assignee.lower() != target.lower()):
            return False

        if issue_type:
            kind = getattr(
                getattr(getattr(issue, "fields", None), "issuetype", None),
                "name", "",
            )
            if str(kind).casefold() != issue_type.strip().casefold():
                return False

        return True

    @staticmethod
    def _assignee_of(issue) -> Optional[str]:
        """The Jira username an issue is assigned to, if any."""
        assignee = getattr(getattr(issue, "fields", None), "assignee", None)
        return getattr(assignee, "name", None) if assignee else None

    def _unit_members(self, unit: str, project_key: str) -> tuple:
        """Everyone recorded as working in one discipline on a project.

        Jira here carries no component or label on these issues, so the
        only record of who does design is the unit each person is assigned
        in their configuration.

        Args:
            unit: The discipline as the user named it
            project_key: The project whose assignments to read

        Returns:
            The Jira usernames in that unit, and an error message when the
            unit is unknown or nobody is recorded in it.
        """
        canonical = self._canonical_unit(unit)
        if not canonical:
            known = "، ".join(sorted(set(_UNIT_ALIASES.values())))
            return None, (
                f"«{unit}» را به‌عنوان یک واحد نمی‌شناسم. "
                f"واحدهای شناخته‌شده: {known}"
            )

        if not self.user_config_repository:
            return None, "اطلاعات واحدهای تیم در دسترس نیست."

        try:
            configs = self.user_config_repository.get_all_user_configs()
        except Exception as exc:
            LOGGER.error(f"Could not read user configs: {exc}")
            return None, "اطلاعات واحدهای تیم خوانده نشد."

        members = {
            config.jira_username.lower()
            for config in configs.values()
            if config.jira_username
            and (config.user_components or {}).get(project_key) == canonical
        }

        if not members:
            return None, (
                f"در {project_key} کسی با واحد «{canonical}» ثبت نشده است."
            )

        LOGGER.info(
            f"Unit {canonical} on {project_key} resolves to {sorted(members)}",
        )
        return members, None

    @staticmethod
    def _canonical_unit(unit: str) -> Optional[str]:
        """Resolve a spoken discipline to the unit recorded in configuration."""
        spoken = unit.replace("\u200c", "").strip().casefold()
        for alias, canonical in _UNIT_ALIASES.items():
            if alias.replace("\u200c", "").casefold() == spoken:
                return canonical
        return None

    def _nothing_matched(
        self,
        match,
        unit: Optional[str],
        person: Optional[str],
        issue_type: Optional[str],
        topic: Optional[str],
        total: int,
    ) -> str:
        """Say that a filter matched nothing, and say which filter it was."""
        asked = "، ".join(
            part for part in (
                f"واحد {unit}" if unit else "",
                f"شخص {person}" if person else "",
                f"نوع {issue_type}" if issue_type else "",
                f"موضوع «{topic}»" if topic else "",
            ) if part
        )
        return (
            f"در اسپرینت جاری {match.display_name} ({total} آیتم) چیزی با "
            f"{asked or 'این شرط‌ها'} پیدا نشد."
        )

    def _render_board(
        self,
        match,
        issues: Sequence,
        unit: Optional[str],
        person: Optional[str],
        total: int,
    ) -> str:
        """Render the matching sprint issues, grouped by who owns them."""
        scope = f" — {unit}" if unit else (f" — {person}" if person else "")
        lines = [
            f"اسپرینت جاری {match.display_name}{scope}: "
            f"{len(issues)} از {total} آیتم.",
        ]

        grouped: dict = {}
        for issue in issues:
            grouped.setdefault(self._assignee_of(issue) or "بدون مسئول", []).append(
                issue,
            )

        for owner, owned in sorted(grouped.items(), key=lambda item: -len(item[1])):
            lines.append(f"\n{owner} ({len(owned)}):")
            for issue in owned:
                lines.append(f"   {self._story_line(issue)}")

        return "\n".join(lines)

    async def sprint_epics(self, project: str) -> str:
        """Summarise the open sprint of a project by the epics it advances.

        Epics carry no assignee, so they can never appear in an
        assignee-scoped list. This is the only tool that queries a project
        rather than a person, and it rolls the sprint's stories up to the
        epics above them.

        Args:
            project: The product or project, as the user named it

        Returns:
            One line per epic with the stories under it, or why there are none.
        """
        match, error = self._resolve_project(project)
        if error:
            return error

        if not self.task_manager_repository:
            return "دسترسی به جیرا برای این پرسش در دسترس نیست."

        allowed, denial = await self._may_read_project(match.canonical)
        if not allowed:
            return denial

        try:
            issues = self.task_manager_repository.search_issues(
                jql=(
                    f'project = "{match.canonical}" '
                    f"AND sprint in openSprints() AND issuetype = Story"
                ),
                max_results=200,
                fields=f"summary,status,{EPIC_LINK_FIELD}",
            )
        except Exception as exc:
            LOGGER.error(f"Sprint epic lookup failed for {match.canonical}: {exc}")
            return "خواندن اسپرینت جاری از جیرا ناموفق بود."

        if not issues:
            return (
                f"در اسپرینت جاری {match.display_name} استوری‌ای نیست."
            )

        grouped, orphans = self._group_by_epic(issues)
        if not grouped:
            return (
                f"{len(issues)} استوری در اسپرینت جاری {match.display_name} "
                f"هست، اما هیچ‌کدام به اپیکی وصل نیستند."
            )

        return self._render_sprint_epics(match, grouped, orphans, len(issues))

    def _group_by_epic(self, issues: Sequence) -> tuple[dict, List]:
        """Group sprint stories under their epic.

        Args:
            issues: The sprint's stories

        Returns:
            A mapping of epic key to its stories, and the stories that carry
            no epic link. Both are returned so a story without an epic is
            reported rather than dropped.
        """
        grouped: dict = {}
        orphans: List = []
        for issue in issues:
            epic_key = self._epic_key_of(issue)
            if epic_key:
                grouped.setdefault(epic_key, []).append(issue)
            else:
                orphans.append(issue)
        return grouped, orphans

    @staticmethod
    def _epic_key_of(issue) -> Optional[str]:
        """Read an issue's Epic Link, which Jira Server keeps in a custom field."""
        value = getattr(getattr(issue, "fields", None), EPIC_LINK_FIELD, None)
        if value is None:
            return None
        return str(getattr(value, "value", value)).strip() or None

    def _render_sprint_epics(
        self,
        match,
        grouped: dict,
        orphans: List,
        total: int,
    ) -> str:
        """Render the sprint's epics, largest first, with their stories.

        Args:
            match: The resolved project
            grouped: Epic key mapped to its sprint stories
            orphans: Sprint stories carrying no epic link
            total: How many stories the sprint holds in all

        Returns:
            The rendered summary.
        """
        lines = [
            f"اسپرینت جاری {match.display_name}: {total} استوری در "
            f"{len(grouped)} اپیک.",
        ]
        ordered = sorted(grouped.items(), key=lambda item: -len(item[1]))
        for epic_key, stories in ordered:
            lines.append(
                f"\n{self._link(epic_key)} — {self._epic_title(epic_key)} "
                f"({len(stories)} استوری)",
            )
            for story in stories:
                lines.append(f"   ↳ {self._story_line(story)}")

        if orphans:
            # A story with no epic is still sprint work; hiding it would make
            # the epic counts look like the whole sprint when they are not.
            lines.append(f"\n{len(orphans)} استوری بدون اپیک:")
            for story in orphans:
                lines.append(f"   ↳ {self._story_line(story)}")

        return "\n".join(lines)

    def _epic_title(self, epic_key: str) -> str:
        """Read an epic's summary, falling back to its key.

        Args:
            epic_key: The epic to name

        Returns:
            The epic's summary, or an empty string when it cannot be read.
        """
        try:
            epic = self.task_manager_repository.get_issue(epic_key)
        except Exception as exc:
            LOGGER.error(f"Could not read epic {epic_key}: {exc}")
            return ""
        summary = str(getattr(getattr(epic, "fields", None), "summary", "") or "")
        return summary.strip()

    def _story_line(self, issue) -> str:
        """Render one sprint story as a linked line with its status."""
        fields = getattr(issue, "fields", None)
        summary = str(getattr(fields, "summary", "") or "").strip()
        if len(summary) > 60:
            summary = f"{summary[:59]}…"
        status = getattr(getattr(fields, "status", None), "name", "") or "?"
        return f"{self._link(str(issue.key))} — {summary} (وضعیت: {status})"

    async def _may_read_project(self, project_key: str) -> tuple[bool, str]:
        """Whether the caller may see a whole project's sprint.

        Sprint contents are not scoped to one person, so ``may_read`` does
        not answer this. Anyone who may read others keeps that right here;
        everyone else must have work of their own in the project. The check
        is made here in Python, never left to the prompt.

        Args:
            project_key: The project being asked about

        Returns:
            Whether to proceed, and the refusal to send when not.
        """
        if self.context.role.may_read_others:
            return True, ""

        own = await self._fetch(self.context.jira_username)
        if any(task.project_key == project_key for task in own):
            return True, ""

        LOGGER.info(
            f"{self.context.jira_username} ({self.context.role.value}) denied "
            f"sprint view of {project_key}: no work of their own there",
        )
        return False, (
            "شما در این پروژه تسکی ندارید، بنابراین دسترسی به اسپرینت آن "
            "را ندارید."
        )

    def _resolve_project(self, project: str) -> tuple[Optional[object], Optional[str]]:
        """Resolve a spoken product name to a project.

        Args:
            project: The name the user used

        Returns:
            The resolved project, and an error message when it is unclear.
        """
        resolution = self.aliases.resolve(project, EntityKind.PROJECT)
        match = resolution.resolved
        if match:
            return match, None

        options = "، ".join(
            candidate.display_name for candidate in resolution.matches
        )
        if options:
            return None, f"منظورتان از «{project}» را نفهمیدم. گزینه‌های نزدیک: {options}"
        return None, f"«{project}» را پیدا نکردم."

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
        """Render tasks with sub-tasks nested under the work they belong to.

        A flat list of forty sub-tasks is unreadable: the keys are unfamiliar
        and the parent — the thing a person actually recognises — is missing.
        Stories, Tasks and Bugs lead; their sub-tasks are indented beneath.

        Args:
            tasks: The tasks to show

        Returns:
            The rendered list.
        """
        by_key = {task.issue_key: task for task in tasks}
        children: dict = {}
        top: List[DailyTaskCheck] = []

        for task in tasks:
            parent = task.parent_key
            if parent and (parent in by_key or self._is_subtask(task)):
                children.setdefault(parent, []).append(task)
            else:
                top.append(task)

        lines: List[str] = []
        for task in top:
            lines.append(self._one_line(task))
            for child in children.pop(task.issue_key, []):
                lines.append(f"   ↳ {self._one_line(child)}")

        # Sub-tasks whose parent is not in this list still have to appear, or
        # the count stops matching what the user was told.
        for parent_key, orphans in children.items():
            lines.append(f"{self._link(parent_key)}:")
            for child in orphans:
                lines.append(f"   ↳ {self._one_line(child)}")

        return "\n".join(lines)

    @staticmethod
    def _is_subtask(task: DailyTaskCheck) -> bool:
        """Whether this issue is a sub-task of something else."""
        return (task.issue_type or "").strip().lower() in {"sub-task", "subtask"}

    def _one_line(self, task: DailyTaskCheck) -> str:
        """Render a single task as one line.

        Args:
            task: The task to render

        Returns:
            The linked key, a trimmed summary, and the status.
        """
        summary = (task.summary or "").strip()
        if len(summary) > 60:
            summary = f"{summary[:59]}…"
        return f"{self._link(task.issue_key)} — {summary} (وضعیت: {task.status})"

    def _link(self, issue_key: str) -> str:
        """Render an issue key as a Telegram HTML link."""
        if not self.base_url:
            return issue_key
        return f'<a href="{self.base_url}/browse/{issue_key}">{issue_key}</a>'

    @staticmethod
    def _hours(hours: float) -> str:
        """Render hours without a trailing ``.0`` on whole numbers."""
        return str(int(hours)) if float(hours).is_integer() else str(round(hours, 2))
