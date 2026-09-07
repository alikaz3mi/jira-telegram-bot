"""Run a recording through pre-processing, a backend, and post-processing."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from typing import Sequence

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.speech import AudioClip
from jira_telegram_bot.entities.speech import Transcript
from jira_telegram_bot.settings.speech_settings import SpeechSettings
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    AudioStageInterface,
)
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    TextStageInterface,
)
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    TranscriberInterface,
)
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    TranscriptionError,
)


class TranscribeVoiceUseCase:
    """Turn a voice message into text, through a configured pipeline.

    The backend is one collaborator among several rather than the whole of
    this class, which is what makes it swappable: the stages, the limits and
    the error handling do not know which provider is behind the interface.
    """

    def __init__(
        self,
        transcriber: TranscriberInterface,
        settings: SpeechSettings,
        audio_stages: Sequence[AudioStageInterface] = (),
        text_stages: Sequence[TextStageInterface] = (),
    ):
        """Initialize the use case.

        Args:
            transcriber: The backend that produces text
            settings: Limits and the vocabulary to prompt with
            audio_stages: Steps applied before transcription, in order
            text_stages: Steps applied after transcription, in order
        """
        self.transcriber = transcriber
        self.settings = settings
        self.audio_stages = list(audio_stages)
        self.text_stages = list(text_stages)

    async def execute(
        self,
        path: Path,
        mime_type: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> Transcript:
        """Transcribe one recording.

        Args:
            path: Where the downloaded audio is
            mime_type: What the sender said it was, when it said anything
            duration_seconds: Length, when the sender reported one

        Returns:
            The transcript, after every configured stage has run.

        Raises:
            TranscriptionError: When the recording is refused or no backend
                could produce text.
        """
        clip = AudioClip(
            path=path, mime_type=mime_type, duration_seconds=duration_seconds,
        )
        self._refuse_if_oversized(clip)

        clip = await self._run_audio_stages(clip)
        transcript = await self.transcriber.transcribe(
            clip,
            language=self.settings.language,
            vocabulary=", ".join(self.settings.vocabulary),
        )
        if not transcript.text.strip():
            raise TranscriptionError("The recording produced no text")

        return await self._run_text_stages(transcript)

    def _refuse_if_oversized(self, clip: AudioClip) -> None:
        """Reject a recording too long or too large to transcribe.

        Checked before any work is done, because both limits exist to avoid
        spending money on a recording that was never going to succeed.

        Args:
            clip: The audio as received

        Raises:
            TranscriptionError: When the recording exceeds a limit.
        """
        duration = clip.duration_seconds
        if duration and duration > self.settings.max_seconds:
            raise TranscriptionError(
                f"Recording is {int(duration)}s, over the "
                f"{self.settings.max_seconds}s limit",
            )

        try:
            size = clip.path.stat().st_size
        except OSError as exc:
            raise TranscriptionError(f"Could not read {clip.path}: {exc}") from exc

        if size > self.settings.max_bytes:
            raise TranscriptionError(
                f"Recording is {size} bytes, over the "
                f"{self.settings.max_bytes} limit",
            )

    async def _run_audio_stages(self, clip: AudioClip) -> AudioClip:
        """Apply each pre-processing stage in order.

        A stage that raises is logged and skipped: an optional improvement
        must never cost a usable recording.

        Args:
            clip: The audio as received

        Returns:
            The audio to transcribe.
        """
        for stage in self.audio_stages:
            try:
                clip = await stage.apply(clip)
            except Exception as exc:
                LOGGER.warning(f"Audio stage {stage.name} failed: {exc}")
        return clip

    async def _run_text_stages(self, transcript: Transcript) -> Transcript:
        """Apply each post-processing stage in order.

        Args:
            transcript: The text the backend produced

        Returns:
            The text to hand back to the caller.
        """
        for stage in self.text_stages:
            try:
                transcript = await stage.apply(transcript)
            except Exception as exc:
                LOGGER.warning(f"Text stage {stage.name} failed: {exc}")
        return transcript
