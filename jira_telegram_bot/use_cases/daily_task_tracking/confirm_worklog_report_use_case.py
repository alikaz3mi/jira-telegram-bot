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

# Words that say how or when the work happened, never what it was. A split
# carrying only these names no subject to match against.
_NON_SUBJECTS = frozenset({
    "ریموت", "اضافه‌کاری", "اضافه", "کاری", "امروز", "دیروز", "پریروز",
    "صبح", "بعدازظهر", "عصر", "شب", "remote", "overtime", "today",
    "yesterday", "ساعت", "کار", "کردم", "روی",
})

# Shorter than this and there is nothing for somebody to recognise.
_MIN_SUBJECT_LENGTH = 4


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
            # Nothing matched what they described. Naming the closest few is
            # not a guess dressed as a choice — the buttons are their own
            # open issues, and picking one is the only way to record work on
            # a task the description did not name. Asking for a typed key
            # while showing nothing leaves somebody who cannot recall their
            # own issue keys with nowhere to go.
            # A description that names no work at all — "ریموت", "امروز" —
            # gives nothing to choose against, so buttons there would be a
            # guess dressed as a choice. A description that names work the
            # ranker simply could not place is different: the person knows
            # which task they meant, and only needs to see the list.
            nearest = (
                [
                    WorklogQuestionOption(
                        label=self._option_label(task),
                        issue_key=task.issue_key,
                    )
                    for task in candidates[:MAX_OPTIONS]
                ]
                if self._describes_work(split)
                else []
            )
            if not nearest:
                return WorklogQuestion(
                    split_index=index,
                    text=(
                        f"برای «{self._subject(split)}» ({hours} ساعت) تسکی "
                        f"پیدا نکردم.\nکلید تسک را بنویسید (مثل "
                        f"PARSCHAT-123)، یا اگر تسکی برایش ثبت نشده این مورد "
                        f"را رد کنید."
                    ),
                    options=[],
                )
            return WorklogQuestion(
                split_index=index,
                text=(
                    f"«{self._subject(split)}» ({hours} ساعت)\n"
                    f"تسکی که دقیقاً به این بخورد پیدا نکردم. "
                    f"{self._digits(len(candidates))} تسک باز دارید — "
                    f"اگر یکی از این‌هاست انتخاب کنید، یا کلید تسک را "
                    f"بنویسید (مثل PARSCHAT-123)، یا این مورد را رد کنید."
                ),
                options=nearest,
            )

        # Say why the question is being asked. "Which task?" with four
        # buttons reads as the bot not having looked; naming what was found
        # and where shows the work and makes the choice quicker.
        chosen = [
            candidates[position] for position in shortlist
            if 0 <= position < len(candidates)
        ]
        projects = sorted({task.project_key for task in chosen})
        where = (
            f" در {projects[0]}" if len(projects) == 1
            else f" در {'، '.join(projects)}"
        )
        reason = (
            f"{self._digits(len(options))} تسک{where} به این توضیح می‌خورند "
            f"و نتوانستم بین‌شان تصمیم بگیرم."
            if len(options) > 1
            else f"نزدیک‌ترین تسک{where} این است:"
        )

        return WorklogQuestion(
            split_index=index,
            text=(
                f"«{self._subject(split)}» ({hours} ساعت)\n"
                f"{reason}\nکدام‌یک درست است؟"
            ),
            options=options,
        )

    @staticmethod
    def _digits(value) -> str:
        """Write a number in Persian digits, as the rest of the bot does."""
        return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

    @staticmethod
    def _describes_work(split: ParsedWorklogSplit) -> bool:
        """Whether the split says what was worked on, not just how or when.

        "ریموت" is a way of working and "دیروز" is a day; neither narrows
        anything, so a list of tasks beside one is noise. Anything longer
        names a subject the person can match against their own board.

        Args:
            split: The unresolved piece of work

        Returns:
            Whether it is worth showing candidates for.
        """
        description = (split.description or "").strip()
        if not description:
            return False
        words = [word for word in description.split() if word not in _NON_SUBJECTS]
        return len(" ".join(words)) >= _MIN_SUBJECT_LENGTH

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
        """Label a button with enough of the issue to recognise it.

        The summary leads, because that is what somebody recognises their
        own work by; the key follows for the cases where two summaries read
        alike.
        """
        summary = (task.summary or "").strip()
        if not summary:
            return task.issue_key
        if len(summary) > 40:
            summary = f"{summary[:39]}…"
        return f"{summary} ({task.issue_key})"

    @staticmethod
    def _format_hours(hours: float) -> str:
        """Render hours without a trailing ``.0`` on whole numbers."""
        return str(int(hours)) if float(hours).is_integer() else str(round(hours, 2))
