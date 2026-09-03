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
from jira_telegram_bot.entities.assistant_entities import EntityKind
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

# A similarity this high is the user having effectively named the issue.
# A project name after one of these is who the work was for, not the board
# it lives on: "به تیم پارسچت", "برای پارسچت", "with the parschat team".
_AUDIENCE_MARKERS = (
    "تیم", "بچه‌های", "بچه های",
    "to the", "for the", "with the", "to team", "for team", "with team",
)

# English names the team after the product: "parschat's team", "the parschat
# team". Looked for just after the alias rather than before it.
_TRAILING_AUDIENCE = ("'s team", "' team", " team", "s team")

_STRONG_MATCH = 0.45

# A strong score settles a split only when it also stands clear of the rest.
# Without this a 0.50 that leads a 0.49 is written straight to Jira, which is
# the one mistake in this flow that is painful to unwind.
_STRONG_LEAD = 0.08

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
        alias_repository=None,
        rank_candidates_use_case=None,
    ):
        """Initialize the use case.

        Args:
            ai_service: Service that runs the structured LLM call
            prompt_catalog: Catalog the parsing prompt is loaded from
            alias_repository: Resolves a spoken product name to a project key,
                so "برای پارسچت" narrows the candidates the user is offered
            rank_candidates_use_case: Orders issues by similarity to the
                described work, so the model chooses from a shortlist
        """
        self.ai_service = ai_service
        self.prompt_catalog = prompt_catalog
        self.alias_repository = alias_repository
        self.rank_candidates = rank_candidates_use_case

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

        shown = self._restrict_to_named_project(text, candidates)

        prompt = await self.prompt_catalog.get_prompt(_PROMPT_TASK)
        result = await self.ai_service.run(
            prompt,
            {
                "content": text,
                "candidates": self._format_candidates(shown),
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
            self._build_split(raw, shown, ordinal_key, weekday)
            for raw in self._as_list(result.get("splits"))
        ]
        # Rank inside the same set the model chose from. Ranking against the
        # full list while the model saw a narrowed one produced a single
        # report whose splits came from two different universes: one issue
        # from the narrowed 24, the next from all 30.
        await self._rerank_splits(report, shown)
        self._reindex_onto(report, shown, candidates)
        report.splits = [split for split in report.splits if split.hours > 0]
        return report

    async def _rerank_splits(
        self,
        report: ParsedWorklogReport,
        candidates: Sequence[DailyTaskCheck],
    ) -> None:
        """Settle each split against the issues, by what it actually describes.

        Ranking the whole message does not work: "دیروز ۲ ساعت ریموت روی
        تنزل خودکار کار کردم" embeds hours, a date and a way of working
        alongside the task, and the noise buries the signal — the right
        issue still led, but by 0.04 instead of 0.15. Each split carries
        only its own description, which is the text worth comparing.

        Only splits the model left unsettled are touched, so a confident
        reading is never second-guessed by similarity.

        Args:
            report: The parsed report, mutated in place
            candidates: The full candidate list indices refer to
        """
        if not self.rank_candidates or len(candidates) <= 1:
            return

        for split in report.splits:
            if split.is_ready or not split.description:
                continue

            ranked = await self.rank_candidates.execute(
                split.description, candidates,
            )
            if ranked is None:
                continue
            if not ranked:
                split.candidate_indices = []
                split.status = WorklogSplitStatus.UNMATCHED
                continue

            position = {
                task.issue_key: index
                for index, task in enumerate(candidates)
            }
            split.candidate_indices = [
                position[task.issue_key]
                for task, _ in ranked
                if task.issue_key in position
            ]
            best_task, best_score = ranked[0]
            runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
            settled = len(ranked) == 1 or (
                best_score >= _STRONG_MATCH
                and best_score - runner_up >= _STRONG_LEAD
            )
            if settled:
                split.issue_key = best_task.issue_key
                split.status = WorklogSplitStatus.RESOLVED
                LOGGER.info(
                    f"Similarity settled a split on {best_task.issue_key} "
                    f"at {best_score:.3f}",
                )
            else:
                # A high score is not on its own an answer. The ranker hands
                # back several rows precisely when they are close, and
                # writing hours to the first of them is the one mistake that
                # is painful to undo.
                split.status = WorklogSplitStatus.AMBIGUOUS
                LOGGER.info(
                    f"Split left for the user: {best_task.issue_key} at "
                    f"{best_score:.3f} leads {len(ranked) - 1} others by "
                    f"{best_score - runner_up:.3f}",
                )

    def _restrict_to_named_project(
        self,
        text: str,
        candidates: Sequence[DailyTaskCheck],
    ) -> Sequence[DailyTaskCheck]:
        """Show the model only the project the user named.

        "برای پارسچت ۴ ساعت" states a project. Filtering the model's answer
        afterwards is too late: if it shortlisted only out-of-project issues
        there is nothing left to keep, and the user is offered buttons that
        are all wrong. Narrowing the list it sees means every option it can
        return is in the right project.

        Falls back to the full list when the name does not resolve or the
        user has no open work there, since no options at all is worse.

        Args:
            text: The user's message, which may name a project
            candidates: The user's open issues

        Returns:
            The issues to show the model.
        """
        project_key = self._resolve_project_key(self._spoken_project(text))
        if not project_key:
            return candidates

        narrowed = [
            task for task in candidates if task.project_key == project_key
        ]
        if not narrowed:
            LOGGER.info(
                f"User named {project_key} but has no open issues there; "
                f"showing all {len(candidates)} candidates",
            )
            return candidates

        dropped = len(candidates) - len(narrowed)
        if dropped:
            LOGGER.info(
                f"Named project {project_key} narrowed candidates from "
                f"{len(candidates)} to {len(narrowed)}",
            )
        return narrowed

    def _spoken_project(self, text: str) -> Optional[str]:
        """Find a known project name in the user's own words.

        The model's ``project_hint`` arrives too late to choose what it is
        shown, so the message is scanned directly against the alias table.

        Args:
            text: The user's message

        Returns:
            The alias as written, or None when no known project is named.
        """
        if not self.alias_repository:
            return None
        try:
            aliases = self.alias_repository.all_of(EntityKind.PROJECT)
        except Exception as exc:
            LOGGER.error(f"Could not read project aliases: {exc}")
            return None

        haystack = text.replace("\u200c", "").casefold()
        best: Optional[str] = None
        best_position = len(haystack) + 1
        for entry in aliases:
            written = str(entry.alias)
            needle = written.replace("\u200c", "").casefold()
            position = self._alias_position(haystack, needle)
            if position < 0 or self._is_audience(haystack, position):
                continue
            # The project a report is *about* is named before the work is
            # described. "برد خودم ... توضیح وظایف به تیم پارسچت" names the
            # caller's own board first and ParsChat only as who the work was
            # for; taking the longest match read it the other way round.
            if position < best_position:
                best, best_position = written, position
        return best

    @staticmethod
    def _alias_position(haystack: str, needle: str) -> int:
        """Where a project alias occurs, if it occurs as a name at all.

        A short key like "AK" matches inside ordinary words, so it only
        counts as a whole word. Longer aliases are matched as substrings,
        because Persian attaches suffixes directly to a name.

        Args:
            haystack: The message, folded and stripped of ZWNJ
            needle: The alias, folded the same way

        Returns:
            The index where the alias occurs, or -1 when it does not.
        """
        if not needle:
            return -1
        if len(needle) > 3:
            return haystack.find(needle)

        for match in re.finditer(re.escape(needle), haystack):
            start, end = match.start(), match.end()
            before = haystack[start - 1] if start else " "
            after = haystack[end] if end < len(haystack) else " "
            if not before.isalnum() and not after.isalnum():
                return start
        return -1

    @staticmethod
    def _is_audience(haystack: str, position: int) -> bool:
        """Whether a project name here is who the work was for, not where.

        "توضیح وظایف به تیم پارسچت" is work on the caller's own board about
        ParsChat's team. Narrowing to ParsChat there hides every issue the
        report actually meant.

        Args:
            haystack: The message, folded
            position: Where the project name starts

        Returns:
            True when the name is preceded by a phrase that makes it an
            audience rather than a location.
        """
        prefix = haystack[max(0, position - 14):position]
        if any(marker in prefix for marker in _AUDIENCE_MARKERS):
            return True
        # English puts the team after the name — "parschat's team", "the
        # parschat team" — so the marker is a suffix there, not a prefix.
        suffix = haystack[position:position + 40]
        return any(marker in suffix for marker in _TRAILING_AUDIENCE)

    @staticmethod
    def _reindex_onto(
        report: ParsedWorklogReport,
        shown: Sequence[DailyTaskCheck],
        candidates: Sequence[DailyTaskCheck],
    ) -> None:
        """Translate indices into the shown list back to the full list.

        The caller confirms against the full candidate list, so an index
        that means one issue here and another there would write the hours to
        the wrong task.

        Args:
            report: The parsed report, mutated in place
            shown: The list the model pointed into
            candidates: The full list the caller will confirm against
        """
        if shown is candidates:
            return
        position = {task.issue_key: index for index, task in enumerate(candidates)}
        for split in report.splits:
            split.candidate_indices = [
                position[shown[index].issue_key]
                for index in split.candidate_indices
                if 0 <= index < len(shown) and shown[index].issue_key in position
            ]

    def _resolve_project_key(self, hint: Optional[str]) -> Optional[str]:
        """Resolve a spoken product name to a project key.

        Args:
            hint: The project the user named, if any

        Returns:
            The canonical project key, or None when it does not resolve.
        """
        if not hint or not self.alias_repository:
            return None
        try:
            resolution = self.alias_repository.resolve(hint, EntityKind.PROJECT)
        except Exception as exc:
            LOGGER.error(f"Could not resolve project hint {hint!r}: {exc}")
            return None
        match = resolution.resolved
        return match.canonical if match else None

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
