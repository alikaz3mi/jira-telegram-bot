"""The tools the assistant may call, and the rules they enforce.

Every tool is parameterised rather than free-form: the model chooses which
tool and fills typed arguments, but never writes a query. That keeps two
things true. Authorisation is decided in Python from the bound context, so
no prompt can widen it; and a question that is really a filter — one
project, one person, one week — is answered by a filter rather than by
similarity, which cannot promise it found everything.
"""
from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import timedelta
from html import escape

import jdatetime
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
MAX_RELEASE_ISSUES = 8
MAX_MEDIA = 3

# A briefing names the release asking most of you, then a couple of others
# so the shape of the quarter is visible without listing every version.
MAX_BRIEFING_RELEASES = 4
MAX_BRIEFING_DUE = 3

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
    ) -> str:
        """List open tasks, filtered the way the question asked.

        Args:
            person: Whose tasks, as the user named them; None means the caller
            project: Which product or project, as the user named it
            status: A Jira status to keep, matched case-insensitively
            issue_type: Keep only this issue type, e.g. "Story" or "Bug"
            in_active_sprint: True keeps only work in an open sprint; False
                keeps only work that belongs to no sprint

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
        label = self._proper_name(target, person, display)

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
        label = self._proper_name(target, person, display)

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

        release = self._release_of(task.issue_key)
        if release:
            lines.append(release)

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

    def _release_of(self, issue_key: str) -> Optional[str]:
        """Name the release a task ships in, and when it is due.

        A task's own due date is often unset while the release it belongs to
        carries the real commitment, so the deadline is invisible from the
        task without this.

        Args:
            issue_key: The task to read

        Returns:
            The rendered line, or None when the task ships in no release.
        """
        if not self._jira():
            return None

        # The whole read is guarded, not just the fetch. A release line is a
        # nice-to-have; losing the task's description because a version
        # field was malformed is not a trade worth making.
        try:
            versions = getattr(
                self._jira().issue(issue_key).fields, "fixVersions", None,
            )
            rendered = []
            for version in versions or []:
                name = str(getattr(version, "name", "") or "").strip()
                if not name:
                    continue
                due = getattr(version, "releaseDate", None)
                rendered.append(
                    f"{name} (تا {self._spell_date(due)})" if due else name,
                )
        except Exception as exc:
            LOGGER.warning(f"Could not read fixVersions of {issue_key}: {exc}")
            return None

        return f"ریلیز: {'، '.join(rendered)}" if rendered else None

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

    async def my_briefing(
        self,
        person: Optional[str] = None,
        project: Optional[str] = None,
        within_days: Optional[int] = None,
    ) -> str:
        """Open a check-in with what matters before what is merely assigned.

        Someone with work in three products cannot read one flat list of
        issue keys and tell which product is asking something of them today.
        So the briefing leads with anything on fire, then takes each product
        in turn and frames that product's work by the releases it ships in —
        because a release carries a date, and a task usually does not.

        The same framing is what somebody wants when they ask about a
        colleague, so ``person`` answers that too rather than sending the
        question to a bare list.

        Args:
            person: Whose briefing, as the user named them; None means the
                caller
            project: Restrict to one product, as the user named it
            within_days: Restrict to work due inside this many days. The
                window narrows what is listed, never what is counted — a
                horizon that silently shrank the totals would misreport how
                much somebody is carrying.

        Returns:
            The briefing, ready to send as Telegram HTML.
        """
        target, error, display = self._resolve_person_named(person)
        if error:
            return error

        project_key = None
        if project:
            match, error = self._resolve_project(project)
            if error:
                return error
            project_key = match.canonical

        tasks = [
            task
            for task in await self._fetch(target)
            if not self._is_finished(task)
        ]
        if project_key:
            tasks = [task for task in tasks if task.project_key == project_key]

        label = self._proper_name(target, person, display)
        sections: List[str] = []
        urgent = await self._urgent_bugs(project_key, target)
        if urgent:
            sections.append(self._render_urgent(urgent, label))

        if not tasks:
            sections.append(f"📋 تسک بازی روی {label} نیست.")
            return "\n\n".join(sections)

        for key in self._projects_by_load(tasks):
            section = await self._project_section(
                key,
                [task for task in tasks if task.project_key == key],
                target,
                label,
                within_days,
            )
            if section:
                sections.append(section)

        if not sections:
            return "چیزی برای گزارش پیدا نکردم."
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _projects_by_load(tasks: Sequence[DailyTaskCheck]) -> List[str]:
        """Order the caller's projects by how much of them they carry.

        Sprint commitments decide the order, since those are what somebody
        has actually promised for this fortnight; the overall count only
        breaks ties between projects with no sprint work at all.

        Args:
            tasks: The caller's open tasks across every project

        Returns:
            The project keys, heaviest commitment first.
        """
        committed: dict = {}
        overall: dict = {}
        for task in tasks:
            overall[task.project_key] = overall.get(task.project_key, 0) + 1
            if task.sprint_name:
                committed[task.project_key] = committed.get(task.project_key, 0) + 1

        return sorted(
            overall,
            key=lambda key: (-committed.get(key, 0), -overall[key], key),
        )

    async def _project_section(
        self,
        project_key: str,
        tasks: Sequence[DailyTaskCheck],
        target: str,
        label: str,
        within_days: Optional[int] = None,
    ) -> str:
        """Frame one project's work by the releases it ships in.

        Args:
            project_key: The project to describe
            tasks: The person's open tasks in that project
            target: Whose tasks these are, as a Jira username
            label: How to name them in the reply
            within_days: Restrict the listed tasks to this horizon

        Returns:
            The rendered section for this project.
        """
        display = self._display_name(project_key)
        lines = [f"📁 <b>{escape(display)}</b>"]

        by_release = self._releases_of(project_key, tasks, target)
        dated = await self._dates_for(project_key, by_release)

        if by_release:
            lines.append(
                self._render_release_role(by_release, dated, tasks, label),
            )

        due, window = self._due_soonest(tasks, within_days)
        if due:
            lines.append("")
            lines.append(f"⏰ <b>{window}</b>")
            for task in due:
                lines.append(self._deadline_line(task))
        elif within_days is not None:
            lines.append("")
            lines.append(
                f"✅ در {self._digits(within_days)} روز آینده مهلتی در این "
                f"پروژه ندارید.",
            )

        lines.append("")
        lines.append(
            f"🔗 {self._all_tasks_link(project_key, display, target, label)}",
        )
        return "\n".join(lines)

    def _display_name(self, project_key: str) -> str:
        """Name a project the way a person says it, not the way Jira keys it."""
        try:
            resolution = self.aliases.resolve(project_key, EntityKind.PROJECT)
        except Exception as exc:
            LOGGER.warning(f"Could not resolve display name for {project_key}: {exc}")
            return project_key
        match = getattr(resolution, "resolved", None)
        return getattr(match, "display_name", None) or project_key

    def _releases_of(
        self,
        project_key: str,
        tasks: Sequence[DailyTaskCheck],
        target: str,
    ) -> dict:
        """Group the caller's tasks in one project by the release they ship in.

        The entity carries no fixVersion, so this asks Jira for the caller's
        own open issues in this project and reads the versions off them. One
        query per project, not one per task.

        Args:
            project_key: The project to read
            tasks: The person's open tasks there, used to keep the grouping
                to work the briefing already knows about
            target: Whose issues to read, as a Jira username

        Returns:
            Release name -> the issue keys of theirs riding on it. Empty when
            the lookup fails or nothing carries a version, both of which are
            reported as an absence of releases rather than as an error.
        """
        if not self.task_manager_repository:
            return {}

        known = {task.issue_key for task in tasks}
        try:
            issues = self.task_manager_repository.search_issues(
                jql=(
                    f'project = "{project_key}" '
                    f'AND assignee = "{target}" '
                    f"AND statusCategory != Done"
                ),
                max_results=100,
                fields="summary,fixVersions",
            )
        except Exception as exc:
            LOGGER.error(f"Release grouping for {project_key} failed: {exc}")
            return {}

        grouped: dict = {}
        for issue in issues or []:
            key = str(getattr(issue, "key", "") or "")
            if known and key not in known:
                continue
            for version in getattr(issue.fields, "fixVersions", None) or []:
                name = str(getattr(version, "name", "") or "").strip()
                if name:
                    grouped.setdefault(name, []).append(key)
        return grouped

    async def _dates_for(self, project_key: str, names: Sequence[str]) -> dict:
        """Read the delivery date of each named release.

        Args:
            project_key: The project the releases belong to
            names: The release names to look up

        Returns:
            Release name -> its release date as Jira stores it, for those
            that carry one.
        """
        if not names or not self.task_manager_repository:
            return {}

        wanted = set(names)
        try:
            versions = self.task_manager_repository.get_project_versions(project_key)
        except Exception as exc:
            LOGGER.error(f"Versions of {project_key} unreadable: {exc}")
            return {}

        dates = {}
        for version in versions or []:
            name = str(getattr(version, "name", "") or "").strip()
            due = getattr(version, "releaseDate", None)
            if name in wanted and due:
                dates[name] = str(due)
        return dates

    def _render_release_role(
        self,
        by_release: dict,
        dates: dict,
        tasks: Sequence[DailyTaskCheck],
        label: str,
    ) -> str:
        """Say what one person is carrying, release by release, soonest first.

        Args:
            by_release: Release name -> their issue keys on it
            dates: Release name -> delivery date, where one is set
            tasks: The person's open tasks in this project
            label: How to name them in the reply

        Returns:
            The rendered paragraph.
        """
        ordered = sorted(
            by_release,
            key=lambda name: (dates.get(name) or "9999-99-99", name),
        )
        lead = ordered[0]
        share = len(by_release[lead])

        carries = "دارید" if label == "شما" else "دارد"
        counts_on = "شما" if label == "شما" else label

        when = (
            f" — تحویل {self._spell_date(dates[lead])}" if lead in dates else ""
        )
        lines = [
            f"🚀 <b>{escape(lead)}</b>{when}",
            f"   {self._digits(share)} کار باز {label} روی این ریلیز است — "
            f"نزدیک‌ترین ریلیزی که روی {counts_on} حساب می‌کند.",
        ]

        if len(ordered) > 1:
            lines.append(
                f"   در مجموع {self._digits(len(tasks))} تسک باز در این "
                f"پروژه {carries}، پخش‌شده بین "
                f"{self._digits(len(ordered))} ریلیز:",
            )
            for name in ordered[1:MAX_BRIEFING_RELEASES]:
                due = (
                    f" — {self._jalali(date.fromisoformat(dates[name]))}"
                    if name in dates else ""
                )
                lines.append(f"   ▫️ {escape(name)}{due}")
            hidden = len(ordered) - MAX_BRIEFING_RELEASES
            if hidden > 0:
                lines.append(f"   ▫️ و {self._digits(hidden)} ریلیز دیگر")
        else:
            lines.append(
                f"   در مجموع {self._digits(len(tasks))} تسک باز در این "
                f"پروژه {carries}.",
            )

        return "\n".join(lines)

    def _due_soonest(
        self,
        tasks: Sequence[DailyTaskCheck],
        within_days: Optional[int] = None,
    ) -> tuple[List[DailyTaskCheck], str]:
        """The tasks whose own dates put them first in the queue.

        Target end decides it. A task without one is not promoted ahead of a
        task that carries a date, but it is still shown when nothing else
        does — otherwise a project where nobody sets dates renders an empty
        section.

        When a horizon is given the heading says so. A list headed "due
        soonest" that has quietly dropped everything past Friday reads as
        the whole of somebody's work, which is how a four-item answer came
        to stand in for twenty-nine.

        Args:
            tasks: The person's open tasks in one project
            within_days: Keep only work due inside this many days

        Returns:
            The tasks, soonest first, and the heading that describes them.
        """
        dated = [task for task in tasks if task.target_end or task.target_start]

        if within_days is not None:
            horizon = datetime.now() + timedelta(days=within_days)
            inside = [
                task for task in dated
                if (task.target_end or task.target_start) <= horizon
            ]
            heading = (
                f"مهلت‌های {self._digits(within_days)} روز آینده "
                f"({self._digits(len(inside))} مورد)"
            )
            return sorted(inside, key=self._due_key), heading

        pool = dated or [task for task in tasks if task.sprint_name] or list(tasks)
        pool = sorted(pool, key=self._due_key)
        return pool[:MAX_BRIEFING_DUE], "نزدیک‌ترین تسک‌ها برای تحویل"

    @staticmethod
    def _due_key(task: DailyTaskCheck) -> tuple:
        """Sort key putting the earliest committed date first."""
        when = task.target_end or task.target_start
        return (when is None, when or datetime.max, task.issue_key)

    def _deadline_line(self, task: DailyTaskCheck) -> str:
        """Render one task as a linked title above its own metadata.

        A bare issue key is not what anyone recognises a task by, so the
        summary carries the link and the key moves down to the detail line
        beside the status and the date. Two short lines also survive a phone
        screen without wrapping mid-sentence, which is what made the numbered
        one-liners hard to scan.

        Args:
            task: The task to render

        Returns:
            Two lines: the linked title, then its status, key and deadline.
        """
        when = task.target_end or task.target_start
        if when:
            deadline = f"تا {self._jalali(when.date())}"
        elif task.sprint_name:
            deadline = f"اسپرینت {task.sprint_name}"
        else:
            deadline = None

        return f"• {self._one_line(task, deadline=deadline)}"

    @staticmethod
    def _status_icon(status: Optional[str]) -> str:
        """Mark a status so its stage reads before the word does.

        Args:
            status: The Jira status name

        Returns:
            One emoji standing for the stage that status belongs to.
        """
        name = (status or "").strip().lower()
        if name in {"in progress", "in-progress", "inprogress"}:
            return "🔵"
        if name in {"review", "in review", "code review", "testing", "test"}:
            return "🟣"
        if name in {"blocked", "on hold", "paused"}:
            return "🔴"
        if name in {"done", "closed", "resolved"}:
            return "🟢"
        return "⚪️"

    def _all_tasks_link(
        self,
        project_key: str,
        display: str,
        target: str,
        label: str,
    ) -> str:
        """Link to every open task one person has in one project."""
        jql = (
            f'assignee = "{target}" '
            f'AND project = "{project_key}" AND resolution = Unresolved '
            f"ORDER BY updated DESC"
        )
        if not self.base_url:
            return display
        url = f"{self.base_url}/issues/?jql={quote(jql)}"
        return f'<a href="{url}">همه تسک‌های {display}</a>'

    async def _urgent_bugs(
        self,
        project_key: Optional[str],
        target: str,
    ) -> List:
        """One person's unresolved bugs at a priority worth interrupting for.

        Args:
            project_key: Restrict to one project, or None for all
            target: Whose bugs, as a Jira username

        Returns:
            The bugs, highest priority first.
        """
        if not self.task_manager_repository:
            return []

        clauses = [
            f'assignee = "{target}"',
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

    def _render_urgent(self, bugs: Sequence, label: str) -> str:
        """Render the urgent bugs, queueing any screenshot they carry."""
        lines = [
            f"🔴 <b>{self._digits(len(bugs))} باگ فوری روی "
            f"{escape(label)}</b>",
        ]
        for bug in bugs:
            key = str(bug.key)
            priority = getattr(
                getattr(bug.fields, "priority", None), "name", "",
            )
            summary = str(getattr(bug.fields, "summary", "") or "").strip() or key
            if len(summary) > 70:
                summary = f"{summary[:69]}…"
            summary = escape(summary)
            status = getattr(getattr(bug.fields, "status", None), "name", "?")

            title = (
                f'<a href="{self.base_url}/browse/{key}">{summary}</a>'
                if self.base_url
                else summary
            )
            detail = " · ".join(
                part for part in (priority, status, key) if part
            )
            lines.append(f"• {title}\n   {detail}")
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

    @staticmethod
    def _is_finished(task: DailyTaskCheck) -> bool:
        """Whether a task is over, whatever its resolution field says."""
        return (task.status or "").strip().lower() in {
            "done", "closed", "resolved", "cancel", "cancelled", "canceled",
        }

    async def releases(
        self,
        project: str,
        topic: Optional[str] = None,
    ) -> str:
        """Say what is due to ship, when, and what still gates it.

        A delivery date lives on a Jira version, not on a sprint or a task.
        Nothing here read versions, so "when does Instagram get verified?"
        was unanswerable — the date sat in the project the whole time while
        the assistant searched sprint contents and reported finding nothing.

        Args:
            project: The product or project, as the user named it
            topic: Narrow to releases about one subject, matched by meaning

        Returns:
            Each upcoming release with its date and the work still open
            against it.
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
            versions = self.task_manager_repository.get_project_versions(
                match.canonical,
            )
        except Exception as exc:
            LOGGER.error(f"Version lookup failed for {match.canonical}: {exc}")
            return "خواندن نسخه‌ها از جیرا ناموفق بود."

        upcoming = [
            version for version in versions
            if not getattr(version, "released", False)
            and not getattr(version, "archived", False)
        ]
        if not upcoming:
            return f"برای {match.display_name} ریلیز برنامه‌ریزی‌شده‌ای ثبت نشده."

        if topic:
            upcoming, topic_error = await self._releases_about(topic, upcoming)
            if topic_error:
                return topic_error
            if not upcoming:
                return (
                    f"ریلیزی درباره «{topic}» در {match.display_name} "
                    f"پیدا نشد."
                )

        upcoming.sort(key=lambda version: getattr(version, "releaseDate", "") or "~")
        return self._render_releases(match, upcoming)

    async def _releases_about(self, topic: str, versions: List) -> tuple:
        """Keep the releases that are about a subject, by meaning.

        Args:
            topic: The subject asked about
            versions: The unreleased versions

        Returns:
            The matching versions, and an error when the search could not run.
        """
        if not self.rank_candidates:
            return versions, None

        texts = [
            f"{getattr(version, 'name', '')} "
            f"{getattr(version, 'description', '') or ''}"
            for version in versions
        ]
        ranked = await self.rank_candidates.rank_texts(topic, texts)
        if ranked is None:
            return versions, None
        return [versions[index] for index, _ in ranked], None

    def _render_releases(self, match, versions: Sequence) -> str:
        """Render upcoming releases with the work still open against each."""
        lines = [f"ریلیزهای پیش‌روی {match.display_name}:"]

        for version in versions:
            name = str(getattr(version, "name", "") or "")
            due = getattr(version, "releaseDate", None)
            start = getattr(version, "startDate", None)

            when = f"تا {self._spell_date(due)}" if due else "بدون تاریخ"
            if getattr(version, "overdue", False):
                when += " ⚠️ عقب‌افتاده"
            window = f" (از {self._spell_date(start)})" if start else ""
            lines.append(f"\n📦 {name} — {when}{window}")

            description = str(getattr(version, "description", "") or "").strip()
            if description:
                lines.append(f"   {self._trim(description, 220)}")

            open_issues = self._open_for_version(match.canonical, name)
            if open_issues is None:
                lines.append("   (خواندن تسک‌های این ریلیز ناموفق بود)")
                continue
            if not open_issues:
                lines.append("   ✅ کار بازی روی این ریلیز نمانده.")
                continue

            lines.append(f"   {len(open_issues)} کار باز:")
            for issue in open_issues[:MAX_RELEASE_ISSUES]:
                owner = self._assignee_of(issue) or "بدون مسئول"
                lines.append(f"      {self._story_line(issue)} — {owner}")
            hidden = len(open_issues) - MAX_RELEASE_ISSUES
            if hidden > 0:
                lines.append(f"      و {hidden} مورد دیگر")

        return "\n".join(lines)

    def _open_for_version(self, project_key: str, name: str) -> Optional[List]:
        """The unfinished issues assigned to one release.

        Args:
            project_key: The project the release belongs to
            name: The version name, as Jira stores it

        Returns:
            The open issues, or None when the lookup failed — which is said
            aloud rather than shown as an empty release.
        """
        escaped = name.replace('"', '\\"')
        try:
            return self.task_manager_repository.search_issues(
                jql=(
                    f'project = "{project_key}" AND fixVersion = "{escaped}" '
                    f"AND statusCategory != Done"
                ),
                max_results=50,
                fields="summary,status,assignee",
            )
        except Exception as exc:
            LOGGER.error(f"Issues for version {name!r} failed: {exc}")
            return None

    @staticmethod
    def _spell_date(value: str) -> str:
        """Say a delivery date the way the team says dates.

        Jira stores Gregorian, but nobody here plans in it — a sprint is
        named for a Jalali half-month and a deadline is spoken as «۲۴
        شهریور». Rendering 2026-09-15 makes the reader convert, and a date
        somebody has to convert is a date they misread.

        Args:
            value: The date as Jira stores it, YYYY-MM-DD

        Returns:
            The weekday and Jalali date, or the input unchanged when it
            cannot be parsed.
        """
        try:
            day = date.fromisoformat(str(value))
        except (ValueError, TypeError):
            return str(value)
        weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه",
                    "جمعه", "شنبه", "یکشنبه"]
        return f"{weekdays[day.weekday()]} {AssistantTools._jalali(day)}"

    @staticmethod
    def _jalali(day: date) -> str:
        """Render one date as a Jalali day and month name.

        Args:
            day: The Gregorian date to convert

        Returns:
            Something like «۲۴ شهریور», or the ISO date when conversion
            fails — a wrong date would be worse than an unconverted one.
        """
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        try:
            converted = jdatetime.GregorianToJalali(day.year, day.month, day.day)
            return (
                f"{AssistantTools._digits(converted.jday)} "
                f"{months[converted.jmonth - 1]}"
            )
        except Exception as exc:
            LOGGER.warning(f"Jalali conversion of {day} failed: {exc}")
            return day.isoformat()

    @staticmethod
    def _digits(value) -> str:
        """Write a number in Persian digits, as the rest of the bot does."""
        return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

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
        username, error, _ = self._resolve_person_named(person)
        return username, error

    def _resolve_person_named(
        self,
        person: Optional[str],
    ) -> tuple[str, Optional[str], Optional[str]]:
        """Resolve a person, keeping the display name the directory holds.

        Args:
            person: The name the user used, or None for themselves

        Returns:
            The Jira username, an error when refused or unresolved, and the
            directory's spelling of their name.
        """
        if not person:
            return self.context.jira_username, None, None

        resolution = self.aliases.resolve(person, EntityKind.PERSON)
        match = resolution.resolved
        if not match:
            if resolution.is_ambiguous:
                options = "، ".join(
                    candidate.display_name for candidate in resolution.matches
                )
                return "", f"منظورتان کدام‌یک است؟ {options}", None
            return "", f"«{person}» را پیدا نکردم.", None

        if not self.context.may_read(match.canonical):
            LOGGER.info(
                f"{self.context.jira_username} ({self.context.role.value}) "
                f"denied access to {match.canonical}",
            )
            return "", DENIED, None

        return match.canonical, None, getattr(match, "display_name", None)

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

    def _proper_name(
        self,
        jira_username: str,
        spoken: Optional[str],
        display: Optional[str] = None,
    ) -> str:
        """Name the person as the directory spells them, not as they were typed.

        ``_label`` echoes the user's own wording, which is right for a short
        confirmation. A briefing is a document about somebody, and echoing
        «خانوم لطفیان» back when the directory says «خانم لطفیان» reads as
        carelessness about the person it is describing.

        The display name comes from the resolution already performed, never
        from a second lookup: resolving a Jira username through a fuzzy
        alias search could land on a different person entirely.

        Args:
            jira_username: The resolved Jira username
            spoken: What the user called them
            display: The display name from the resolution, when there was one

        Returns:
            The display name, falling back to the spoken form.
        """
        if jira_username.lower() == self.context.jira_username.lower():
            return "شما"
        return display or spoken or jira_username

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
            lines.append(f"• {self._one_line(task)}")
            for child in children.pop(task.issue_key, []):
                lines.append(f"   ↳ {self._one_line(child, indent='   ')}")

        # Sub-tasks whose parent is not in this list still have to appear, or
        # the count stops matching what the user was told.
        for parent_key, orphans in children.items():
            lines.append(f"• {self._link(parent_key)}")
            for child in orphans:
                lines.append(f"   ↳ {self._one_line(child, indent='   ')}")

        return "\n".join(lines)

    @staticmethod
    def _is_subtask(task: DailyTaskCheck) -> bool:
        """Whether this issue is a sub-task of something else."""
        return (task.issue_type or "").strip().lower() in {"sub-task", "subtask"}

    def _one_line(
        self,
        task: DailyTaskCheck,
        indent: str = "",
        deadline: Optional[str] = None,
    ) -> str:
        """Render a single task as a linked title above its own detail.

        The title carries the link, not the key: nobody recognises their own
        work by ``PARSCHAT-5807``. The key stays on the detail line, since
        it is still what somebody quotes when they talk about the task.

        Args:
            task: The task to render
            indent: Leading whitespace, so a sub-task's detail line lines up
                under its own title rather than under its parent's
            deadline: A commitment to show between the status and the key

        Returns:
            Two lines: the linked title, then its status, deadline and key.
        """
        summary = (task.summary or "").strip() or task.issue_key
        if len(summary) > 70:
            summary = f"{summary[:69]}…"
        summary = escape(summary)

        title = (
            f'<a href="{self.base_url}/browse/{task.issue_key}">{summary}</a>'
            if self.base_url
            else summary
        )
        detail = [f"{self._status_icon(task.status)} {task.status}"]
        if deadline:
            detail.append(deadline)
        detail.append(task.issue_key)

        return f"{title}\n{indent}   {' · '.join(detail)}"

    def _link(self, issue_key: str) -> str:
        """Render an issue key as a Telegram HTML link."""
        if not self.base_url:
            return issue_key
        return f'<a href="{self.base_url}/browse/{issue_key}">{issue_key}</a>'

    @staticmethod
    def _hours(hours: float) -> str:
        """Render hours without a trailing ``.0`` on whole numbers."""
        return str(int(hours)) if float(hours).is_integer() else str(round(hours, 2))
