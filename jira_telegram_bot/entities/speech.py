"""What a voice message is, at each stage of becoming text."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class AudioClip(BaseModel):
    """One recording on disk, as it moves through the pipeline.

    Stages hand back a new clip rather than mutating this one, so a failed
    stage leaves the previous file intact and the pipeline can carry on with
    what it already had.
    """

    path: Path = Field(description="Where the audio currently is")
    mime_type: Optional[str] = Field(
        default=None,
        description="What Telegram said it was, when it said anything",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Length, when the source reported one",
    )

    @property
    def suffix(self) -> str:
        """The file extension, lowercased and without its dot."""
        return self.path.suffix.lower().lstrip(".")


class Transcript(BaseModel):
    """What a provider heard, before anything is done about it."""

    text: str = Field(description="The transcribed text")
    language: Optional[str] = Field(
        default=None,
        description="Language the provider reported, when it reports one",
    )
    provider: str = Field(
        default="",
        description="Which backend produced this, for logs and for support",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Audio length, when known — this is what a provider bills",
    )


class TranscriptionResult(BaseModel):
    """Entity representing the result of a speech transcription.

    ``translation`` and ``is_persian`` are kept for the handlers that
    already read them; new code should read ``text`` and ask the language
    detector directly rather than depending on a translation nobody asked
    for.
    """

    text: str = Field(description="The transcribed text")
    is_persian: bool = Field(description="Whether the text is primarily in Persian")
    translation: Optional[str] = Field(
        default=None,
        description="English translation if text was Persian",
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence score of the transcription",
    )
    provider: str = Field(
        default="",
        description="Which backend transcribed it",
    )
