from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class TranscriptionResult(BaseModel):
    """Entity representing the result of a speech transcription."""

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
