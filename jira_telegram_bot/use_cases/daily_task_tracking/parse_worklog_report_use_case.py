"""Use case for turning a free-text work report into per-issue worklogs."""
from __future__ import annotations

import re
from datetime import date
from datetime import timedelta

from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_intent import (
    ParsedWorklogReport,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_intent import (
    ParsedWorklogSplit,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_intent import (
    WorklogSplitStatus,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AIServiceProtocol,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    PromptCatalogProtocol,
)

_PROMPT_TASK = "parse_worklog_report"

# Below this, the top candidate is not trusted on its own and the user is asked.
CONFIDENCE_THRESHOLD = 0.75

# Persian and Arabic-Indic digits, so "۲.۵" survives float().
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class ParseWorklogReportUseCase:
    """Split a free-text report into worklog entries against the user's issues.

    The model is never asked for a Jira key. It sees a numbered list of the
    user's own open issues and answers with positions in that list, so the
    worst it can do is point at the wrong row — which the confidence check
    turns into a question rather than a wrong worklog.
    """

    def __init__(
        self,
        ai_service: AIServiceProtocol,
        prompt_catalog: PromptCatalogProtocol,
    ):
        """Initialize the use case.

        Args:
            ai_service: Service that runs the structured LLM call
            prompt_catalog: Catalog the parsing prompt is loaded from
        """
        self.ai_service = ai_service
        self.prompt_catalog = prompt_catalog

    async def execute(
        self,
        text: str,
        candidates: Sequence[DailyTaskCheck],
        history: str = "",
    ) -> ParsedWorklogReport:
        """Parse a work report against the issues the user could have worked on.

        Args:
            text: The user's message, as they wrote it
            candidates: The user's open issues, in the order shown to the model
            history: Recent turns, so a message continuing an earlier one is
                read together with it

        Returns:
            The parsed report; splits that could not be resolved confidently
            are marked so the caller asks about them.
        """
        report = ParsedWorklogReport(raw_text=text)
        if not candidates:
            LOGGER.info("No candidate issues to match a worklog report against")
            return report

        prompt = await self.prompt_catalog.get_prompt(_PROMPT_TASK)
        result = await self.ai_service.run(
            prompt,
            {
                "content": text,
                "candidates": self._format_candidates(candidates),
                "history": history,
                "today": date.today().isoformat(),
            },
            cleanse_llm_text=True,
        )

        report.total_hours = self._to_float(result.get("total_hours")) or None
        report.project_hint = (result.get("project_hint") or "").strip() or None
        ordinal_key = self._ordinal_issue_key(text, history)
        weekday = self._weekday_date(text, date.today())
        report.splits = [
            self._build_split(raw, candidates, ordinal_key, weekday)
            for raw in self._as_list(result.get("splits"))
        ]
        report.splits = [split for split in report.splits if split.hours > 0]
        return report

    @staticmethod
    def _format_candidates(candidates: Sequence[DailyTaskCheck]) -> str:
        """Render the issues as a numbered list for the model to point into."""
        lines: List[str] = []
        for index, task in enumerate(candidates):
            parts = [f"[{index}] {task.issue_key}: {task.summary}"]
            parts.append(f"project={task.project_key}")
            if task.issue_type:
                parts.append(f"type={task.issue_type}")
            parts.append(f"status={task.status}")
            if task.description:
                snippet = " ".join(task.description.split())[:160]
                parts.append(f"detail={snippet}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    def _build_split(
        self,
        raw: Any,
        candidates: Sequence[DailyTaskCheck],
        ordinal_key: Optional[str] = None,
        weekday: Optional[date] = None,
    ) -> ParsedWorklogSplit:
        """Turn one raw model entry into a split with a resolved status.

        Args:
            raw: One entry from the model's ``splits``
            candidates: The issues the report was parsed against
            ordinal_key: Issue key an ordinal in the message points at, which
                settles the match the model could not make on its own
            weekday: Date resolved in Python from a named weekday, which
                overrides the model's arithmetic
        """
        if not isinstance(raw, dict):
            raw = {}

        indices = [
            index
            for index in self._as_int_list(raw.get("candidate_indices"))
            if 0 <= index < len(candidates)
        ]
        confidence = self._to_float(raw.get("confidence"))
        confidence = min(max(confidence, 0.0), 1.0)

        split = ParsedWorklogSplit(
            hours=self._to_float(raw.get("hours")),
            description=str(raw.get("description") or "").strip(),
            worked_on=(
                weekday.isoformat() if weekday
                else self._to_past_date(raw.get("worked_on"))
            ),
            work_type=self._clean(raw.get("work_type")),
            candidate_indices=indices,
            confidence=confidence,
        )

        if ordinal_key and len(indices) != 1:
            # "دومی" names one task exactly; trust it over the model's guess.
            for position, candidate in enumerate(candidates):
                if candidate.issue_key == ordinal_key:
                    split.candidate_indices = [position]
                    split.issue_key = ordinal_key
                    split.status = WorklogSplitStatus.RESOLVED
                    return split

        if not indices:
            split.status = WorklogSplitStatus.UNMATCHED
        elif len(indices) == 1 and confidence >= CONFIDENCE_THRESHOLD:
            split.status = WorklogSplitStatus.RESOLVED
            split.issue_key = candidates[indices[0]].issue_key
        else:
            split.status = WorklogSplitStatus.AMBIGUOUS
        return split

    # Ordinals the team uses to point back at a list the bot just printed.
    # Resolving these in Python rather than in the prompt keeps "دومی" as
    # reliable as "تسک دوم" — the model was resolving one and not the other.
    _ORDINALS = {
        "اول": 0, "اولی": 0, "اولین": 0, "یکم": 0, "یکمی": 0,
        "دوم": 1, "دومی": 1, "دومین": 1,
        "سوم": 2, "سومی": 2, "سومین": 2,
        "چهارم": 3, "چهارمی": 3, "چهارمین": 3,
        "پنجم": 4, "پنجمی": 4, "پنجمین": 4,
    }
    _LAST = ("آخری", "آخرین", "اخری", "اخرین")

    @classmethod
    def _ordinal_issue_key(cls, text: str, history: str) -> Optional[str]:
        """Resolve "the second one" against the list the bot last printed.

        Args:
            text: The user's message
            history: The rendered conversation so far

        Returns:
            The issue key that ordinal points at, or None when the message
            names no ordinal or the history holds no list to count.
        """
        if not history:
            return None

        keys: List[str] = []
        for match in re.finditer(r"\b([A-Z][A-Z0-9]+-\d+)\b", history):
            if match.group(1) not in keys:
                keys.append(match.group(1))
        if not keys:
            return None

        words = set(re.findall(r"[\u0600-\u06FF]+", text))
        if words & set(cls._LAST):
            return keys[-1]
        for word in words:
            index = cls._ORDINALS.get(word)
            if index is not None and index < len(keys):
                return keys[index]
        return None

    # Persian weekday names to Python's Monday=0 numbering. Weekday
    # arithmetic is not something a language model does reliably: asked for
    # "last Thursday" it returned a Tuesday, three days out, and a worklog
    # filed against the wrong day is not visibly wrong to anyone reading it.
    _WEEKDAYS = {
        "دوشنبه": 0,
        "سه‌شنبه": 1, "سه شنبه": 1, "سشنبه": 1,
        "چهارشنبه": 2, "چارشنبه": 2,
        "پنج‌شنبه": 3, "پنجشنبه": 3, "پنج شنبه": 3, "۵شنبه": 3, "5شنبه": 3,
        "جمعه": 4,
        "شنبه": 5,
        "یکشنبه": 6, "یک‌شنبه": 6, "یکشنبه‌": 6,
    }
    # "last week" / "this week" qualifiers.
    _LAST_WEEK = ("هفته پیش", "هفته‌ی پیش", "هفته گذشته", "هفته‌ی گذشته", "هفته قبل")

    @classmethod
    def _weekday_date(cls, text: str, today: date) -> Optional[date]:
        """Resolve a Persian weekday phrase to an actual past date.

        Args:
            text: The user's message
            today: The day the message was sent

        Returns:
            The date meant, or None when no weekday is named.
        """
        normalised = text.replace("\u200c", " ")
        # Longest first, so "پنجشنبه" is not matched by "شنبه".
        for name in sorted(cls._WEEKDAYS, key=len, reverse=True):
            if name.replace("\u200c", " ") not in normalised:
                continue
            delta = (today.weekday() - cls._WEEKDAYS[name]) % 7
            if delta == 0:
                delta = 7

            # The Persian week begins on Saturday, so the most recent Thursday
            # can already belong to the previous week. Adding another seven
            # days then skips a week the user did not mean. Only go back
            # further when the day named is still inside the current week.
            if any(q in normalised for q in cls._LAST_WEEK):
                days_since_saturday = (today.weekday() - 5) % 7
                if delta <= days_since_saturday:
                    delta += 7
            return today - timedelta(days=delta)
        return None

    @staticmethod
    def _clean(value: Any) -> Optional[str]:
        """Return a trimmed string, or None for anything empty or null-ish."""
        text = str(value or "").strip()
        return text or None

    @classmethod
    def _to_past_date(cls, value: Any) -> Optional[str]:
        """Validate a parsed work date, rejecting anything in the future.

        A worklog dated ahead of today is always wrong and Jira accepts it
        silently, so bad arithmetic from the model is dropped here.

        Args:
            value: The model's ``worked_on`` value

        Returns:
            An ISO date string of today or earlier, or None meaning today.
        """
        text = cls._clean(value)
        if not text:
            return None
        try:
            parsed = date.fromisoformat(cls._normalise_digits(text))
        except (TypeError, ValueError):
            LOGGER.warning(f"Ignoring unparseable work date {text!r}")
            return None
        if parsed > date.today():
            LOGGER.warning(f"Ignoring future work date {text!r}")
            return None
        return parsed.isoformat()

    @staticmethod
    def _as_list(value: Any) -> List[Any]:
        """Coerce the model's ``splits`` field to a list."""
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
        return []

    @classmethod
    def _as_int_list(cls, value: Any) -> List[int]:
        """Coerce the model's index field to a list of ints, dropping junk."""
        if not isinstance(value, list):
            value = [value]
        indices: List[int] = []
        for item in value:
            try:
                indices.append(int(cls._normalise_digits(item)))
            except (TypeError, ValueError):
                continue
        return indices

    @classmethod
    def _to_float(cls, value: Any) -> float:
        """Read a number that may arrive as a string with Persian digits."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(cls._normalise_digits(value))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _normalise_digits(value: Any) -> str:
        """Convert Persian/Arabic digits so ``float`` and ``int`` accept them."""
        return str(value).translate(_DIGIT_MAP).strip()
