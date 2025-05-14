from __future__ import annotations

import os
import shutil
import asyncio
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.speech import TranscriptionResult
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import (
    SpeechProcessorInterface,
)
from jira_telegram_bot.settings.openai_settings import OpenAISettings


class SpeechProcessor(SpeechProcessorInterface):
    """Adapter for speech processing using OpenAI's GPT-4o model."""

    def __init__(self, settings: OpenAISettings):
        # TODO: remove openai and add to agents
        self.api_key = settings.token
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4o-transcribe" 

    async def convert_audio_format(
        self,
        input_path: str,
        target_format: str = "mp3",
    ) -> str:
        """Convert audio file to a specified format using FFmpeg.
        
        Parameters
        ----------
        input_path : str
            Path to the input audio file
        target_format : str, optional
            Target audio format, by default "mp3"
            
        Returns
        -------
        str
            Path to the converted audio file
            
        Raises
        ------
        RuntimeError
            If the conversion process fails or FFmpeg is not available
        """
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            LOGGER.error("FFmpeg not found. Please install FFmpeg to process audio files.")
            raise RuntimeError(
                "FFmpeg is required but not installed. Install it with 'apt-get install ffmpeg'"
            )
        
        input_path_obj = Path(input_path)
        output_path = str(input_path_obj.parent / f"{input_path_obj.stem}.{target_format}")
        
        try:
            command = [
                ffmpeg_path,
                "-i", input_path,
                "-y",  # Overwrite output file if it exists
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                LOGGER.error(f"FFmpeg error: {stderr.decode()}")
                raise RuntimeError(f"Failed to convert audio: {stderr.decode()}")
            
            LOGGER.info(f"Successfully converted {input_path} to {output_path}")
            return output_path
        except FileNotFoundError:
            error_msg = "FFmpeg executable not found in PATH"
            LOGGER.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            LOGGER.error(f"Error converting audio format: {e}")
            raise RuntimeError(f"Audio conversion failed: {e}")

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
            LOGGER.error(f"Error transcribing audio: {e}")
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
        original_path = voice_file_path
        converted_path = None
        
        try:
            file_ext = Path(voice_file_path).suffix.lower().lstrip('.')
            
            # Convert if not already in a compatible format
            if file_ext not in ['mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm']:
                LOGGER.info(f"Converting {file_ext} format to mp3")
                converted_path = await self.convert_audio_format(voice_file_path, "mp3")
                audio_path = converted_path
            else:
                audio_path = voice_file_path
            
            text = await self.transcribe_audio(audio_path)
            is_persian = self.is_persian(text)
            confidence = 0.95

            translation = await self.translate_to_english(text) if is_persian else None

            return TranscriptionResult(
                text=text,
                is_persian=is_persian,
                translation=translation,
                confidence=confidence,
            )
        except Exception as e:
            LOGGER.error(f"Error processing voice message: {e}")
            raise
        finally:
            # Clean up temporary files
            try:
                if converted_path and os.path.exists(converted_path):
                    os.remove(converted_path)
                if os.path.exists(original_path):
                    os.remove(original_path)
            except Exception as e:
                LOGGER.warning(f"Failed to clean up audio files: {e}")

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
            LOGGER.error(f"Error translating text: {e}")
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
