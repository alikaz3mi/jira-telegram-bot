"""Build the morning digest that opens the daily check-in.

The reminder used to open by asking about one task, then the next, up to
twelve times. That inverts the conversation: the person already knows what
they did, and the bot spends the morning extracting it one tap at a time.

A digest leads with what the person could not know on their own — a blocker
that cleared overnight, a task that moved backwards — and then asks the one
open question a person can answer in a sentence. What they report is
matched against their issues; only what is left unaccounted for is asked
about individually.
"""
from __future__ import annotations

from typing import List
from typing import Optional
from typing import Sequence

from pydantic import BaseModel
from pydantic import Field

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.constants import persian_messages
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)


class DailyDigest(BaseModel):
    """What one person is told before they are asked anything."""

    unblocked: List[DailyTaskCheck] = Field(
        default_factory=list,
        description="Tasks whose blockers finished recently",
    )
    regressed: List[DailyTaskCheck] = Field(
        default_factory=list,
        description="Tasks that moved backwards",
    )
    in_flight: List[DailyTaskCheck] = Field(
        default_factory=list,
        description="Tasks already in progress",
    )
    waiting: List[DailyTaskCheck] = Field(
        default_factory=list,
        description="Tasks that should have started but have not",
    )
    backlog_count: int = Field(
        default=0,
        description="Loose backlog items, counted but not listed",
    )

    @property
    def has_news(self) -> bool:
        """Whether anything here is worth leading with."""
        return bool(self.unblocked or self.regressed)

    @property
    def is_empty(self) -> bool:
        """Whether there is nothing at all to say."""
        return not (
            self.unblocked or self.regressed or self.in_flight or self.waiting
        )


class BuildDailyDigestUseCase:
    """Sort a person's tasks into the story their morning message tells."""

    def execute(
        self,
        tasks: Sequence[DailyTaskCheck],
        backlog_count: int = 0,
    ) -> DailyDigest:
        """Group tasks by what the person needs to know about them.

        A task appears in exactly one group, most actionable first, so the
        counts in the rendered message add up to what was actually fetched.

        Args:
            tasks: The person's live tasks, backlog already separated out
            backlog_count: How many loose backlog items were set aside

        Returns:
            The digest.
        """
        digest = DailyDigest(backlog_count=backlog_count)

        for task in tasks:
            if task.blockers_cleared_recently:
                digest.unblocked.append(task)
            elif task.check_status is TaskCheckStatus.STATUS_REGRESSED:
                digest.regressed.append(task)
            elif task.check_status is TaskCheckStatus.IN_PROGRESS:
                digest.in_flight.append(task)
            elif task.check_status in (
                TaskCheckStatus.SHOULD_BE_STARTED,
                TaskCheckStatus.NEEDS_WORKLOG,
            ):
                digest.waiting.append(task)

        return digest

    @staticmethod
    def unaccounted_for(
        tasks: Sequence[DailyTaskCheck],
        reported_keys: Sequence[str],
        limit: int,
    ) -> List[DailyTaskCheck]:
        """The tasks still worth asking about after a person has reported.

        Someone who wrote a full report should not then be asked about the
        work they just described. Only what their message did not cover is
        put to them one at a time.

        Args:
            tasks: The tasks that were candidates for questioning
            reported_keys: Issues the person's own report accounted for
            limit: Most questions to ask

        Returns:
            The remaining tasks, capped.
        """
        covered = {key.upper() for key in reported_keys}
        return [
            task for task in tasks if task.issue_key.upper() not in covered
        ][:limit]


class RenderDailyDigestUseCase:
    """Turn a digest into the message a person actually reads."""

    # Enough to recognise the work without the list becoming the message.
    MAX_LISTED = 5

    def __init__(self, base_url: str = ""):
        """Initialize the renderer.

        Args:
            base_url: Jira base URL, used to link issue keys
        """
        self.base_url = (base_url or "").rstrip("/")

    def execute(self, digest: DailyDigest) -> str:
        """Render the digest as Telegram HTML.

        Args:
            digest: The grouped tasks

        Returns:
            The message, ready to send.
        """
        if digest.is_empty:
            return persian_messages.DIGEST_NOTHING.strip()

        lines = [persian_messages.DIGEST_GREETING, ""]

        # Led with, because it is the only part a person could not have
        # worked out for themselves.
        self._section(
            lines, persian_messages.DIGEST_UNBLOCKED_HEADER, digest.unblocked,
            with_blockers=True,
        )
        self._section(
            lines, persian_messages.DIGEST_REGRESSED_HEADER, digest.regressed,
        )
        self._section(
            lines, persian_messages.DIGEST_IN_FLIGHT_HEADER, digest.in_flight,
        )
        self._section(
            lines, persian_messages.DIGEST_WAITING_HEADER, digest.waiting,
        )

        if digest.backlog_count:
            lines.append(
                persian_messages.DIGEST_BACKLOG_NOTE.format(
                    count=digest.backlog_count,
                ),
            )
            lines.append("")

        lines.append(persian_messages.DIGEST_ASK.strip())
        return "\n".join(lines).strip()

    def _section(
        self,
        lines: List[str],
        header: str,
        tasks: Sequence[DailyTaskCheck],
        with_blockers: bool = False,
    ) -> None:
        """Append one titled group, saying how many were not listed.

        Args:
            lines: The message being built, appended to in place
            header: The group's heading
            tasks: The group's tasks
            with_blockers: Whether to name the blockers that cleared
        """
        if not tasks:
            return

        lines.append(header)
        for task in tasks[: self.MAX_LISTED]:
            lines.append(self._one_line(task, with_blockers))

        hidden = len(tasks) - self.MAX_LISTED
        if hidden > 0:
            lines.append(f"   و {hidden} مورد دیگر")
        lines.append("")

    def _one_line(self, task: DailyTaskCheck, with_blockers: bool) -> str:
        """Render one task as a linked line."""
        summary = (task.summary or "").strip()
        if len(summary) > 55:
            summary = f"{summary[:54]}…"

        line = f"   {self._link(task.issue_key)} — {summary}"
        if with_blockers and task.blockers_cleared_recently:
            cleared = "، ".join(
                self._link(key) for key in task.blockers_cleared_recently
            )
            line += f" (بلاکر: {cleared} تمام شد)"
        return line

    def _link(self, issue_key: str) -> str:
        """Render an issue key as a Telegram HTML link."""
        if not self.base_url:
            return issue_key
        return f'<a href="{self.base_url}/browse/{issue_key}">{issue_key}</a>'
