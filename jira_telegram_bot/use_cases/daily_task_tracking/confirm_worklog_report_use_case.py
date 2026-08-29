"""Use case for deciding what to ask before a parsed report is written."""
from __future__ import annotations

from typing import List
from typing import Optional
from typing import Sequence

from pydantic import BaseModel
from pydantic import Field

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_intent import (
    ParsedWorklogReport,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_intent import (
    ParsedWorklogSplit,
)

# Rounding in "نصف روز" style reports should not trigger a question.
HOURS_TOLERANCE = 0.05

# Telegram inline keyboards get unreadable past a handful of buttons.
MAX_OPTIONS = 4


class WorklogQuestionOption(BaseModel):
    """One tappable answer to a disambiguation question."""

    label: str = Field(description="Button text shown in Telegram")
    issue_key: Optional[str] = Field(
        None,
        description="Issue this option selects; None for a non-issue answer",
    )


class WorklogQuestion(BaseModel):
    """A single question to put to the user, answerable by tapping."""

    split_index: int = Field(description="Which split of the report this is about")
    text: str = Field(description="The question, in Persian")
    options: List[WorklogQuestionOption] = Field(
        default_factory=list,
        description="Tappable answers; a free-text reply is always allowed too",
    )


class WorklogConfirmation(BaseModel):
    """What still has to be settled before a report can be written."""

    report: ParsedWorklogReport
    questions: List[WorklogQuestion] = Field(default_factory=list)
    arithmetic_warning: Optional[str] = Field(
        None,
        description="Set when the parts do not add up to the stated total",
    )

    @property
    def is_ready(self) -> bool:
        """True when nothing needs asking and the report can be written."""
        return not self.questions and self.arithmetic_warning is None


class ConfirmWorklogReportUseCase:
    """Work out which parts of a parsed report the user must confirm.

    Two things get checked in code rather than trusted from the model: that
    an issue was actually resolved, and that the pieces add up to the total
    the user stated. A mismatch there is the user's own arithmetic or a
    misread sentence, and either way it is worth one tap to settle.
    """

    def execute(
        self,
        report: ParsedWorklogReport,
        candidates: Sequence[DailyTaskCheck],
    ) -> WorklogConfirmation:
        """Build the confirmation for a parsed report.

        Args:
            report: The parsed report
            candidates: The same issue list the report was parsed against

        Returns:
            The questions to ask, if any.
        """
        confirmation = WorklogConfirmation(report=report)

        for index, split in enumerate(report.splits):
            if split.is_ready:
                continue
            question = self._build_question(index, split, candidates)
            if question:
                confirmation.questions.append(question)

        confirmation.arithmetic_warning = self._check_arithmetic(report)
        return confirmation

    def _build_question(
        self,
        index: int,
        split: ParsedWorklogSplit,
        candidates: Sequence[DailyTaskCheck],
    ) -> Optional[WorklogQuestion]:
        """Ask which issue a split belongs to, offering the model's shortlist."""
        shortlist = split.candidate_indices[:MAX_OPTIONS]
        options = [
            WorklogQuestionOption(
                label=self._option_label(candidates[position]),
                issue_key=candidates[position].issue_key,
            )
            for position in shortlist
            if 0 <= position < len(candidates)
        ]

        hours = self._format_hours(split.hours)

        if not options:
            # Nothing matched. Offering the first few of the user's issues
            # looks like a choice but is a guess wearing a keyboard: the user
            # may have just said the task does not exist. Say so and let them
            # name it or drop the entry.
            return WorklogQuestion(
                split_index=index,
                text=(
                    f"برای «{self._subject(split)}» ({hours} ساعت) تسکی پیدا "
                    f"نکردم.\nکلید تسک را بنویسید (مثل PARSCHAT-123)، یا اگر "
                    f"تسکی برایش ثبت نشده این مورد را رد کنید."
                ),
                options=[],
            )

        return WorklogQuestion(
            split_index=index,
            text=f"«{self._subject(split)}» ({hours} ساعت) روی کدام تسک ثبت شود؟",
            options=options,
        )

    @staticmethod
    def _subject(split: ParsedWorklogSplit) -> str:
        """The user's own words for one piece of work, for quoting back."""
        return (split.description or "").strip() or "این بخش از کار"

    def _check_arithmetic(self, report: ParsedWorklogReport) -> Optional[str]:
        """Flag a stated total that the pieces do not add up to."""
        if report.total_hours is None or not report.splits:
            return None
        difference = round(report.allocated_hours - report.total_hours, 2)
        if abs(difference) <= HOURS_TOLERANCE:
            return None

        stated = self._format_hours(report.total_hours)
        allocated = self._format_hours(report.allocated_hours)
        return (
            f"مجموع اعلام‌شده {stated} ساعت است، اما جمع بخش‌ها "
            f"{allocated} ساعت شد."
        )

    @staticmethod
    def _option_label(task: DailyTaskCheck) -> str:
        """Label a button with enough of the issue to recognise it."""
        summary = task.summary or ""
        if len(summary) > 40:
            summary = f"{summary[:39]}…"
        return f"{task.issue_key} — {summary}" if summary else task.issue_key

    @staticmethod
    def _format_hours(hours: float) -> str:
        """Render hours without a trailing ``.0`` on whole numbers."""
        return str(int(hours)) if float(hours).is_integer() else str(round(hours, 2))
