"""Build the speech pipeline named in settings.

A registry rather than a chain of ``if`` statements: adding a backend means
adding a factory here, and nothing else in the codebase learns its name.
"""
from __future__ import annotations

from typing import Callable
from typing import Dict
from typing import List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.speech.audio_stages import NormaliseAudioStage
from jira_telegram_bot.adapters.speech.openai_transcriber import OpenAITranscriber
from jira_telegram_bot.adapters.speech.text_stages import PersianDigitsStage
from jira_telegram_bot.adapters.speech.text_stages import VocabularyStage
from jira_telegram_bot.settings.openai_settings import OpenAISettings
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

# name -> how to build it. A local backend (faster-whisper, vosk) is added
# here as one more entry; nothing outside this module changes.
TRANSCRIBERS: Dict[str, Callable[[OpenAISettings, SpeechSettings], TranscriberInterface]] = {
    "openai_whisper": lambda openai, speech: OpenAITranscriber(openai, speech),
}

AUDIO_STAGES: Dict[str, Callable[[SpeechSettings], AudioStageInterface]] = {
    "normalise": lambda settings: NormaliseAudioStage(),
}

TEXT_STAGES: Dict[str, Callable[[SpeechSettings], TextStageInterface]] = {
    "persian_digits": lambda settings: PersianDigitsStage(),
    "vocabulary": lambda settings: VocabularyStage(settings.vocabulary),
}


def build_transcriber(
    openai_settings: OpenAISettings,
    settings: SpeechSettings,
) -> TranscriberInterface:
    """Construct the backend named in settings.

    Args:
        openai_settings: Supplies the API token
        settings: Names the provider

    Returns:
        The backend.

    Raises:
        ValueError: When the name is not registered. Failing at startup is
            the point — a typo must not surface as a broken voice message
            hours later.
    """
    factory = TRANSCRIBERS.get(settings.provider)
    if not factory:
        raise ValueError(
            f"Unknown speech provider {settings.provider!r}. "
            f"Available: {', '.join(sorted(TRANSCRIBERS))}",
        )
    return factory(openai_settings, settings)


def build_audio_stages(settings: SpeechSettings) -> List[AudioStageInterface]:
    """Construct the pre-processing stages named in settings, in order.

    Args:
        settings: Names the stages

    Returns:
        The stages. An unknown name is logged and skipped rather than
        raised: a missing optional stage is not worth refusing to start.
    """
    return _build(settings.audio_stages, AUDIO_STAGES, settings, "audio")


def build_text_stages(settings: SpeechSettings) -> List[TextStageInterface]:
    """Construct the post-processing stages named in settings, in order.

    Args:
        settings: Names the stages

    Returns:
        The stages, unknown names skipped.
    """
    return _build(settings.text_stages, TEXT_STAGES, settings, "text")


def _build(names, registry, settings, kind):
    """Look each name up, skipping any that is not registered."""
    stages = []
    for name in names:
        factory = registry.get(name)
        if not factory:
            LOGGER.warning(
                f"Unknown {kind} stage {name!r}; skipping. "
                f"Available: {', '.join(sorted(registry))}",
            )
            continue
        stages.append(factory(settings))
    return stages
