"""Entities for resolving what a person names to what Jira calls it."""
from __future__ import annotations

from enum import Enum
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class EntityKind(str, Enum):
    """What sort of thing an alias points at."""

    PROJECT = "project"
    PERSON = "person"


class UserRole(str, Enum):
    """What a person is allowed to ask about.

    Authorisation is decided from this in Python, never by the model: a
    member may only read their own work, a lead their team's, and a CTO
    anyone's.
    """

    MEMBER = "member"
    LEAD = "lead"
    CTO = "cto"

    @property
    def may_read_others(self) -> bool:
        """True when this role may ask about someone else's tasks."""
        return self in (UserRole.LEAD, UserRole.CTO)


class EntityAlias(BaseModel):
    """One name a person might use for a project or a colleague."""

    alias: str = Field(description="The alias as written, for display")
    alias_norm: str = Field(description="Normalised form, what matching uses")
    kind: EntityKind = Field(description="Whether this names a project or a person")
    canonical: str = Field(
        description="Jira project key or jira username this resolves to",
    )
    display_name: str = Field(
        default="",
        description="Human-readable name of the target, for confirmations",
    )


class EntityMatch(BaseModel):
    """A candidate resolution of something the user named."""

    canonical: str = Field(description="Jira project key or jira username")
    display_name: str = Field(description="Human-readable name of the target")
    kind: EntityKind = Field(description="Whether this is a project or a person")
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Match confidence; 1.0 is an exact alias hit",
    )


class EntityResolution(BaseModel):
    """The outcome of resolving one name.

    Deliberately three-way. Guessing between two similar names is how a
    question about one person gets answered with another's data, so an
    uncertain match is returned as a question rather than an answer.
    """

    query: str = Field(description="What the user named")
    matches: List[EntityMatch] = Field(
        default_factory=list,
        description="Candidates, best first",
    )

    @property
    def resolved(self) -> Optional[EntityMatch]:
        """The single confident match, or None when the caller must ask."""
        if not self.matches:
            return None
        best = self.matches[0]
        if best.score < 0.85:
            return None
        runner_up = self.matches[1].score if len(self.matches) > 1 else 0.0
        # Two near-equal candidates is ambiguity, however high the scores.
        if best.score - runner_up < 0.1 and len(self.matches) > 1:
            return None
        return best

    @property
    def is_ambiguous(self) -> bool:
        """True when there are candidates but none can be chosen safely."""
        return bool(self.matches) and self.resolved is None
