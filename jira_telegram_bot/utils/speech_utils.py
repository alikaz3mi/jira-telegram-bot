from __future__ import annotations

import os

import openai
from loguru import logger
from pydub import AudioSegment

from jira_telegram_bot.settings import OPENAI_SETTINGS


class SpeechProcessor:
    def __init__(self):
        self.api_key = OPENAI_SETTINGS.token
        openai.api_key = self.api_key

    async def convert_ogg_to_wav(self, ogg_path: str) -> str:
        """Convert OGG voice message to WAV format."""
        wav_path = ogg_path + ".wav"
        try:
            audio = AudioSegment.from_ogg(ogg_path)
            audio.export(wav_path, format="wav")
            return wav_path
        except Exception as e:
            logger.error(f"Error converting OGG to WAV: {e}")
            raise

    async def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcribe audio file using OpenAI's Whisper model.
        Automatically handles multiple languages including Persian.
        """
        try:
            with open(audio_path, "rb") as audio_file:
                transcription = await openai.Audio.atranscribe(
                    "whisper-1",
                    audio_file,
                )
                return transcription.text

        except Exception as e:
            logger.error(f"Error transcribing audio with Whisper: {e}")
            raise RuntimeError(f"Error with speech recognition service: {e}")

    async def process_voice_message(self, voice_file_path: str) -> str:
        """Process a voice message file and return transcribed text."""
        try:
            # Convert to WAV if needed
            if voice_file_path.endswith(".oga") or voice_file_path.endswith(".ogg"):
                wav_path = await self.convert_ogg_to_wav(voice_file_path)
            else:
                wav_path = voice_file_path

            # Transcribe using Whisper
            text = await self.transcribe_audio(wav_path)

            # Cleanup temporary files
            if wav_path != voice_file_path:
                os.remove(wav_path)

            return text

        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            raise

    @staticmethod
    def is_persian(text: str) -> bool:
        """
        Check if the text contains Persian characters.
        Returns True if more than 30% of characters are Persian.
        """
        persian_chars = len([c for c in text if "\u0600" <= c <= "\u06FF"])
        return persian_chars > len(text) * 0.3

    async def translate_to_english(self, text: str) -> str:
        """
        Translate Persian text to English if needed for processing.
        Uses OpenAI's GPT model for high-quality translation.
        """
        if not self.is_persian(text):
            return text

        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a Persian to English translator.
                                   Translate the following text accurately while preserving technical terms:""",
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return text  # Return original text if translation fails
