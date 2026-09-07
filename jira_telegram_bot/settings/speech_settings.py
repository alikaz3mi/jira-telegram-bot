"""Which speech backend runs, and what is done to the audio around it."""
from __future__ import annotations

from typing import List
from typing import Optional

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot.utils.pydantic_advanced_settings import CustomizedSettings


class SpeechSettings(CustomizedSettings):
    """How a voice message becomes text.

    The backend is chosen by name here rather than constructed in code, so
    swapping providers is a configuration change. The pipeline around it is
    also named here: stages run in the order listed, and a stage nobody
    lists never runs.
    """

    provider: str = Field(
        default="openai_whisper",
        description=(
            "Which transcription backend to use, by its registered name. "
            "Unknown names fail at startup rather than at the first voice "
            "message."
        ),
    )
    model: str = Field(
        default="whisper-1",
        description=(
            "The model within that backend. For OpenAI: whisper-1, or "
            "gpt-4o-transcribe for better Persian at a higher price."
        ),
    )
    language: Optional[str] = Field(
        default="fa",
        description=(
            "ISO code the recording is expected to be in. Persian here, "
            "because that is what this team speaks; None lets the model "
            "detect, which it does less reliably on short clips."
        ),
    )
    max_seconds: int = Field(
        default=600,
        description=(
            "Refuse anything longer. A ten-minute cap is generous for a "
            "status report and stops an accidental hour-long recording "
            "becoming a surprise bill."
        ),
    )
    max_bytes: int = Field(
        default=25 * 1024 * 1024,
        description="OpenAI's own upload limit; larger files are refused early",
    )
    audio_stages: List[str] = Field(
        default_factory=lambda: ["normalise"],
        description=(
            "Pre-processing stages, in order. `normalise` re-encodes to "
            "16 kHz mono WAV, which every backend accepts. Add `trim` or "
            "`denoise` here once they exist and are measured."
        ),
    )
    text_stages: List[str] = Field(
        default_factory=lambda: ["persian_digits", "vocabulary"],
        description=(
            "Post-processing stages, in order. `persian_digits` turns "
            "spoken numerals into digits the worklog parser can read; "
            "`vocabulary` repairs the team's own terms."
        ),
    )
    vocabulary: List[str] = Field(
        default_factory=lambda: [
            "پارس‌چت", "آواخرد", "خردیار", "جیرا", "اسپرینت", "استوری",
            "اپیک", "ریلیز", "بک‌اند", "فرانت‌اند", "دواپس", "ای‌پی‌آی",
            "APISIX", "Jira", "Plan DB", "webhook", "endpoint",
        ],
        description=(
            "Terms the recordings are likely to contain. Passed to the "
            "backend as a prompt, which is the only lever a hosted model "
            "gives you over its vocabulary."
        ),
    )
    timeout_seconds: float = Field(
        default=120.0,
        description="Give up on a backend rather than leave the user waiting",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="speech_",
        extra="ignore",
        protected_namespaces=(),
    )
