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
