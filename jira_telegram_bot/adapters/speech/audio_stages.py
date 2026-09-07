"""Steps applied to a recording before it reaches a transcription backend."""
from __future__ import annotations

import asyncio
import shutil

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.speech import AudioClip
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    AudioStageInterface,
)

# 16 kHz mono is what speech models are trained on, and what every backend
# accepts. Sending more than that costs bandwidth and buys nothing.
_SAMPLE_RATE = "16000"
_CHANNELS = "1"


class NormaliseAudioStage(AudioStageInterface):
    """Re-encode a recording to 16 kHz mono WAV.

    Telegram sends voice notes as Opus in an ``.oga`` container. Some
    backends accept that and some do not, and a local model generally will
    not — so normalising here means a new backend needs no conversion code
    of its own.
    """

    def __init__(self, target_suffix: str = "wav"):
        """Initialize the stage.

        Args:
            target_suffix: Container to write, without its dot
        """
        self._target_suffix = target_suffix.lstrip(".")

    @property
    def name(self) -> str:
        """The name this stage is selected by in settings."""
        return "normalise"

    async def apply(self, clip: AudioClip) -> AudioClip:
        """Convert the clip, or return it unchanged when that is not possible.

        Args:
            clip: The audio as recorded

        Returns:
            The converted audio, or the original when ffmpeg is unavailable
            or the conversion fails. A recording a backend might still
            accept is worth more than a clean failure.
        """
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            LOGGER.warning(
                "ffmpeg is not installed; sending audio to the backend as "
                "recorded. Install it to support every provider.",
            )
            return clip

        target = clip.path.with_name(
            f"{clip.path.stem}.normalised.{self._target_suffix}",
        )
        command = [
            ffmpeg, "-nostdin", "-y",
            "-i", str(clip.path),
            "-ac", _CHANNELS,
            "-ar", _SAMPLE_RATE,
            "-vn",
            str(target),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
        except Exception as exc:
            LOGGER.warning(f"Could not run ffmpeg: {exc}")
            return clip

        if process.returncode != 0 or not target.exists():
            LOGGER.warning(
                f"ffmpeg could not normalise {clip.path.name}: "
                f"{stderr.decode(errors='replace')[:200]}",
            )
            return clip

        return AudioClip(
            path=target,
            mime_type=f"audio/{self._target_suffix}",
            duration_seconds=clip.duration_seconds,
        )
