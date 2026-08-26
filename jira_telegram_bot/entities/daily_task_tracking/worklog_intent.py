"""Entities for free-text worklog parsing.

A user reports a day's work in one Persian sentence — "امروز ۵ ساعت برای
پارس‌چت وقت گذاشتم که ۳ ساعتش برای تغییرات سمت بانک پارسیان بود و ۲ ساعتش
برای رفع مشکلات فرانت". These entities carry that sentence from the LLM's
reading of it to a set of worklogs, keeping the model's guess and the
resolved issue separate so an unresolved guess can be asked about instead
of written.
"""
from __future__ import annotations

from enum import Enum
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class WorklogSplitStatus(str, Enum):
    """How confidently a mentioned piece of work maps to one issue."""

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


class ParsedWorklogSplit(BaseModel):
    """One piece of work the user described, before it is written anywhere.

    ``candidate_indices`` refer to positions in the candidate list handed to
    the model. The model never emits issue keys: it only points at rows it
    was shown, so a hallucinated key cannot become a worklog.
    """

    hours: float = Field(description="Hours attributed to this piece of work")
    description: str = Field(
        description="What the user said they did, in their own words",
    )
    worked_on: Optional[str] = Field(
        default=None,
        description=(
            "The day the work happened as YYYY-MM-DD, or None for today. "
            "Resolved from phrases like 'دیروز' or '۲ روز پیش'."
        ),
    )
    work_type: Optional[str] = Field(
        default=None,
        description=(
            "A named way of working the team records in the worklog comment, "
            "such as 'ریموت' or 'اضافه‌کاری'. None when not stated."
        ),
    )
    candidate_indices: List[int] = Field(
        default_factory=list,
        description="Indices into the candidate list this work may belong to",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Model's confidence that the top candidate is correct",
    )
    issue_key: Optional[str] = Field(
        None,
        description="Resolved Jira issue key; None until disambiguated",
    )
    status: WorklogSplitStatus = Field(
        default=WorklogSplitStatus.UNMATCHED,
        description="Whether this split is ready to write",
    )

    @property
    def is_ready(self) -> bool:
        """True when this split can be written to Jira without asking."""
        return self.status is WorklogSplitStatus.RESOLVED and bool(self.issue_key)


class ParsedWorklogReport(BaseModel):
    """A whole free-text report, split into per-issue pieces."""

    raw_text: str = Field(description="The message exactly as the user sent it")
    total_hours: Optional[float] = Field(
        None,
        description="Total hours stated by the user, if they stated one",
    )
    splits: List[ParsedWorklogSplit] = Field(
        default_factory=list,
        description="The individual pieces of work described",
    )
    project_hint: Optional[str] = Field(
        None,
        description="Project the user named, if any, to narrow candidates",
    )

    @property
    def allocated_hours(self) -> float:
        """Sum of the hours across the splits."""
        return round(sum(split.hours for split in self.splits), 2)

    @property
    def needs_confirmation(self) -> bool:
        """True when any split cannot be written without asking the user."""
        return any(not split.is_ready for split in self.splits)
