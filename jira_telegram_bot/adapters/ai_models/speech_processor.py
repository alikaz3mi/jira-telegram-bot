from __future__ import annotations

import os
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

from jira_telegram_bot.entities.speech import TranscriptionResult
from jira_telegram_bot.settings import OPENAI_SETTINGS
from jira_telegram_bot.use_cases.interface.speech_processor_interface import (
    SpeechProcessorInterface,
)


class SpeechProcessor(SpeechProcessorInterface):
    """Adapter for speech processing using OpenAI's GPT-4o model."""

    def __init__(self):
        self.api_key = OPENAI_SETTINGS.token
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4o-transcribe" 

    async def convert_audio_format(
        self,
        input_path: str,
        target_format: str = "mp3",
    ) -> str:
        pass

    async def transcribe_audio(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> str:
        """Transcribe audio to text using OpenAI's API.

        Parameters
        ----------
        audio_path : str
            Path to the audio file for transcription
        language : Optional[str], optional
            Language code to optimize transcription, by default None

        Returns
        -------
        str
            Transcribed text from the audio

        Raises
        ------
        RuntimeError
            If the speech recognition service encounters an error
        """
        try:
            with open(audio_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    language=language,
                    response_format="text",
                    prompt="This is a tech conversation potentially containing programming terms, API names, and technical concepts.",
                )
                return response
        except Exception as e:
            logger.error(f"Error transcribing audio with Whisper: {e}")
            raise RuntimeError(f"Error with speech recognition service: {e}")

    async def process_voice_message(self, voice_file_path: str) -> TranscriptionResult:
        """Process a voice message file and return structured transcription results.

        Parameters
        ----------
        voice_file_path : str
            Path to the voice message file

        Returns
        -------
        TranscriptionResult
            Entity containing transcription text, language detection results,
            translation if needed, and confidence score

        Raises
        ------
        Exception
            If any processing error occurs during transcription
        """
        mp3_path = voice_file_path
        try:
            text = await self.transcribe_audio(mp3_path)
            is_persian = self.is_persian(text)
            confidence = 0.95

            translation = await self.translate_to_english(text) if is_persian else None

            os.remove(mp3_path)
            return TranscriptionResult(
                text=text,
                is_persian=is_persian,
                translation=translation,
                confidence=confidence,
            )
        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
            raise

    async def translate_to_english(self, text: str) -> str:
        """Translate Persian text to English using GPT-4o.

        Parameters
        ----------
        text : str
            Persian text to translate

        Returns
        -------
        str
            Translated English text, or the original if translation failed

        Notes
        -----
        Preserves technical terms, API names, and programming concepts
        """
        if not self.is_persian(text):
            return text

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Persian to English translator specializing in technical "
                            "content. Preserve programming terms, API names, and technical "
                            "concepts in their original form. Maintain the original meaning "
                            "while making it natural in English."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return text

    @staticmethod
    def is_persian(text: str) -> bool:
        """Determine if text is primarily Persian.

        Parameters
        ----------
        text : str
            Text to analyze for Persian characters

        Returns
        -------
        bool
            True if more than 30% of characters are Persian, False otherwise
        """
        persian_chars = len([c for c in text if "\u0600" <= c <= "\u06FF"])
        return persian_chars > len(text) * 0.3
