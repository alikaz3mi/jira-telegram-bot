from __future__ import annotations

import os
from typing import Optional

import openai
from loguru import logger
from pydub import AudioSegment

from jira_telegram_bot.entities.speech import TranscriptionResult
from jira_telegram_bot.settings import OPENAI_SETTINGS
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import (
    SpeechProcessorInterface,
)


class SpeechProcessor(SpeechProcessorInterface):
    """Adapter for speech processing using OpenAI's GPT-4 model."""

    def __init__(self):
        self.api_key = OPENAI_SETTINGS.token
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "whisper-1"  # Updated to use Whisper model

    async def convert_audio_format(
        self,
        input_path: str,
        target_format: str = "mp3",
    ) -> str:
        pass
        # """Convert audio to a format suitable for OpenAI's API."""
        # try:
        #     output_path = f"{input_path}.{target_format}"
        #     audio = AudioSegment.from_file(input_path)
        #     audio.export(output_path, format=target_format)
        #     return output_path
        # except Exception as e:
        #     logger.error(f"Error converting audio format: {e}")
        #     raise

    async def transcribe_audio(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio using OpenAI's Whisper model.
        Automatically handles Persian and English.
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
        """
        Process a voice message file and return a TranscriptionResult entity.
        """
        try:
            # Convert to MP3 for OpenAI API
            mp3_path = voice_file_path  # await self.convert_audio_format(voice_file_path, "mp3")

            # First try without language specification
            text = await self.transcribe_audio(mp3_path)

            # Check if it's Persian
            is_persian = self.is_persian(text)
            confidence = 0.95  # Default high confidence for GPT-4

            if is_persian:
                # Translate to English if Persian
                translation = await self.translate_to_english(text)
            else:
                translation = None

            # Cleanup temporary files
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
        """
        Translate Persian text to English for processing.
        Uses GPT-4 for high-quality technical translation.
        """
        if not self.is_persian(text):
            return text

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
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
            return text  # Return original text if translation fails

    @staticmethod
    def is_persian(text: str) -> bool:
        """
        Check if the text contains Persian characters.
        Returns True if more than 30% of characters are Persian.
        """
        persian_chars = len([c for c in text if "\u0600" <= c <= "\u06FF"])
        return persian_chars > len(text) * 0.3
