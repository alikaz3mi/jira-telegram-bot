"""Transcription through OpenAI's hosted speech models."""
from __future__ import annotations

import asyncio
from typing import Optional

from openai import AsyncOpenAI

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.speech import AudioClip
from jira_telegram_bot.entities.speech import Transcript
from jira_telegram_bot.settings.openai_settings import OpenAISettings
from jira_telegram_bot.settings.speech_settings import SpeechSettings
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    TranscriberInterface,
)
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    TranscriptionError,
)

# What the API accepts without a re-encode. Anything else goes through the
# normalisation stage first — Telegram sends .oga, which is not on this list.
_ACCEPTED = frozenset(
    {"flac", "m4a", "mp3", "mp4", "mpeg", "mpga", "oga", "ogg", "wav", "webm"},
)


class OpenAITranscriber(TranscriberInterface):
    """Speech to text via OpenAI's audio API."""

    def __init__(self, openai_settings: OpenAISettings, settings: SpeechSettings):
        """Initialize the transcriber.

        Args:
            openai_settings: Supplies the API token
            settings: Model, timeout and language
        """
        self._client = AsyncOpenAI(api_key=openai_settings.token)
        self._settings = settings

    @property
    def name(self) -> str:
        """The name this backend is selected by in settings."""
        return "openai_whisper"

    @property
    def accepts(self) -> frozenset[str]:
        """Extensions the API takes without a re-encode."""
        return _ACCEPTED

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
            vocabulary: Terms the recording is likely to contain

        Returns:
            What the model heard.

        Raises:
            TranscriptionError: When the API fails or times out.
        """
        request = {
            "model": self._settings.model,
            "response_format": "verbose_json",
        }
        if language:
            request["language"] = language
        if vocabulary:
            request["prompt"] = vocabulary

        try:
            with clip.path.open("rb") as handle:
                response = await asyncio.wait_for(
                    self._client.audio.transcriptions.create(
                        file=handle, **request,
                    ),
                    timeout=self._settings.timeout_seconds,
                )
        except asyncio.TimeoutError as exc:
            raise TranscriptionError(
                f"{self.name} timed out after "
                f"{self._settings.timeout_seconds}s",
            ) from exc
        except Exception as exc:
            # verbose_json is unavailable on the gpt-4o transcribe models,
            # which reject the whole request rather than downgrade it.
            if "response_format" in str(exc):
                return await self._plain_transcribe(clip, request)
            raise TranscriptionError(f"{self.name} failed: {exc}") from exc

        return Transcript(
            text=str(getattr(response, "text", "") or "").strip(),
            language=getattr(response, "language", None) or language,
            provider=self.name,
            duration_seconds=getattr(response, "duration", None),
        )

    async def _plain_transcribe(self, clip: AudioClip, request: dict) -> Transcript:
        """Retry without the rich response format, for models that refuse it.

        Args:
            clip: The audio to transcribe
            request: The request that was rejected

        Returns:
            What the model heard, without duration or detected language.

        Raises:
            TranscriptionError: When the retry also fails.
        """
        request = dict(request, response_format="text")
        LOGGER.info(f"{self._settings.model} refused verbose_json; retrying plain")
        try:
            with clip.path.open("rb") as handle:
                response = await asyncio.wait_for(
                    self._client.audio.transcriptions.create(
                        file=handle, **request,
                    ),
                    timeout=self._settings.timeout_seconds,
                )
        except Exception as exc:
            raise TranscriptionError(f"{self.name} failed: {exc}") from exc

        text = response if isinstance(response, str) else getattr(response, "text", "")
        return Transcript(
            text=str(text or "").strip(),
            language=request.get("language"),
            provider=self.name,
        )
