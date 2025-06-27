from typing import Optional

from jira_telegram_bot.adapters.ai_models.speech_to_text import SpeechProcessor
from jira_telegram_bot.entities.speech import Speech


class SpeechRecogniser:
    """Adapter for speech recognition using existing SpeechProcessor."""

    def __init__(self, speech_processor: SpeechProcessor):
        """Initialize the speech recognizer with processor.

        Args:
            speech_processor: The speech processing service.
        """
        self._speech_processor = speech_processor

    async def transcribe_audio(self, audio_data: bytes, file_format: str = "ogg") -> Optional[str]:
        """Transcribe audio data to text.

        Args:
            audio_data: The audio data bytes.
            file_format: The audio file format.

        Returns:
            Transcribed text or None if transcription fails.

        Raises:
            Exception: If transcription fails.
        """
        try:
            speech = Speech(
                audio_data=audio_data,
                file_format=file_format,
            )
            
            result = await self._speech_processor.speech_to_text(speech)
            return result.transcript if result else None
            
        except Exception as e:
            raise Exception(f"Speech transcription failed: {str(e)}")

    async def transcribe_voice_message(self, voice_file_path: str) -> Optional[str]:
        """Transcribe a voice message file to text.

        Args:
            voice_file_path: Path to the voice message file.

        Returns:
            Transcribed text or None if transcription fails.

        Raises:
            Exception: If transcription fails.
        """
        try:
            with open(voice_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            # Determine format from file extension
            file_format = voice_file_path.split('.')[-1].lower()
            if file_format not in ['ogg', 'mp3', 'wav', 'm4a']:
                file_format = 'ogg'  # Default format for Telegram voice messages
            
            return await self.transcribe_audio(audio_data, file_format)
            
        except Exception as e:
            raise Exception(f"Voice message transcription failed: {str(e)}")
