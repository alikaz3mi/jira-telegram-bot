"""Ports for turning a recording into text.

Three small interfaces rather than one large one, because the three things
change for different reasons: a provider changes when the vendor does, an
audio stage when a recording gives trouble, a text stage when the team's
vocabulary does. The old ``SpeechProcessorInterface`` bundled transcription,
format conversion, language detection and translation into one class, so a
second backend could not be added without reimplementing all four.
"""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Optional

from jira_telegram_bot.entities.speech import AudioClip
from jira_telegram_bot.entities.speech import Transcript


class TranscriberInterface(ABC):
    """One speech-to-text backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name this backend is selected by in settings."""

    @property
    @abstractmethod
    def accepts(self) -> frozenset[str]:
        """Extensions this backend takes directly, without conversion."""

    @abstractmethod
    async def transcribe(
        self,
        clip: AudioClip,
        language: Optional[str] = None,
        vocabulary: str = "",
    ) -> Transcript:
        """Turn one recording into text.

        Args:
            clip: The audio to transcribe
            language: ISO code to bias the model, or None to let it detect
            vocabulary: Terms the recording is likely to contain, which the
                backend may use as a prompt

        Returns:
            What the backend heard.

        Raises:
            TranscriptionError: When the backend could not produce text.
        """


class AudioStageInterface(ABC):
    """One step applied to a recording before it is transcribed."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name this stage is selected by in settings."""

    @abstractmethod
    async def apply(self, clip: AudioClip) -> AudioClip:
        """Transform a recording, returning where it now lives.

        A stage that cannot help must return the clip it was given rather
        than raise: losing a usable recording to an optional improvement is
        never the right trade.

        Args:
            clip: The audio as it currently stands

        Returns:
            The audio to hand to the next stage.
        """


class TextStageInterface(ABC):
    """One step applied to a transcript after it is produced."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name this stage is selected by in settings."""

    @abstractmethod
    async def apply(self, transcript: Transcript) -> Transcript:
        """Clean up or enrich a transcript.

        Like an audio stage, a text stage that fails returns what it was
        given.

        Args:
            transcript: The text as it currently stands

        Returns:
            The text to hand to the next stage.
        """


class TranscriptionError(RuntimeError):
    """A recording could not be turned into text."""
