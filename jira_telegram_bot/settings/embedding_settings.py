from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot.utils.pydantic_advanced_settings import CustomizedSettings


class EmbeddingSettings(CustomizedSettings):
    """How issues are embedded for similarity ranking.

    The defaults are measured rather than assumed: on this team's own
    issues, 512 dimensions matched full-size retrieval exactly at a third
    of the storage.
    """

    model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model",
    )
    dimensions: int = Field(
        default=512,
        description="Vector size; the model is trained to be truncated",
    )
    min_similarity: float = Field(
        default=0.25,
        description=(
            "Below this the best match is not worth showing. A shortlist of "
            "unrelated issues reads as an answer; nothing is honest."
        ),
    )
    min_margin: float = Field(
        default=0.08,
        description=(
            "How far the best match must lead the runner-up. Absolute "
            "similarity cannot separate a real match from noise here: "
            "nonsense scored 0.386 while a genuine near-miss scored 0.375. "
            "What does separate them is the gap — real matches led by "
            "0.15-0.27, non-matches by 0.02-0.04."
        ),
    )
    ambiguous_similarity: float = Field(
        default=0.42,
        description=(
            "When the best match clears this but does not clear the margin, "
            "the tie is worth asking about rather than refusing. Several "
            "issues that all plausibly match is a different situation from "
            "nothing matching, and only the person who did the work can "
            "settle it. Below this the tie is between rows that are all "
            "unrelated, and a question about them wastes their time."
        ),
    )
    ambiguous_spread: float = Field(
        default=0.06,
        description=(
            "How close a runner-up must be to the leader to join the "
            "question. Anything further behind is not really in contention, "
            "and padding the options makes the choice harder, not easier."
        ),
    )
    max_ambiguous_options: int = Field(
        default=4,
        description=(
            "A question with more options than this is not a question, it "
            "is the list the user was trying to avoid reading."
        ),
    )
    min_topic_similarity: float = Field(
        default=0.38,
        description=(
            "Floor for topic search, higher than the worklog floor. A "
            "worklog names one issue; a topic spans a whole epic, and a "
            "subject the project has never heard of still scores ~0.35 "
            "against dozens of summaries. Measured on this sprint: every "
            "true Instagram match scored >= 0.400, while an absent topic "
            "peaked at 0.349."
        ),
    )
    topic_matches: int = Field(
        default=25,
        description=(
            "How many issues a topic search may return. A topic spans a "
            "whole epic, so this is larger than the worklog shortlist."
        ),
    )
    shortlist_size: int = Field(
        default=5,
        description="How many issues to hand the model after ranking",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="embedding_",
        extra="ignore",
        protected_namespaces=(),
    )
