from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Optional

from jira_telegram_bot.entities.speech import TranscriptionResult


class SpeechProcessorInterface(ABC):
    """Interface for speech processing capabilities."""

    @abstractmethod
    async def convert_audio_format(
        self,
        input_path: str,
        target_format: str = "mp3",
    ) -> str:
        """Convert audio to a specified format."""
        pass

    @abstractmethod
    async def transcribe_audio(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> str:
        """Transcribe audio file to text."""
        pass

    @abstractmethod
    async def process_voice_message(self, voice_file_path: str) -> TranscriptionResult:
        """Process a voice message and return a TranscriptionResult entity."""
        pass

    @abstractmethod
    async def translate_to_english(self, text: str) -> str:
        """Translate text to English if needed."""
        pass

    @abstractmethod
    def is_persian(self, text: str) -> bool:
        """Check if text contains Persian characters."""
        pass
