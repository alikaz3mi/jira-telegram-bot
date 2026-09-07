"""A voice note becomes text and then takes the path a typed message takes.

Voice used to exist only in two side flows — a /voice_report conversation
and task creation — while the chat people actually use was text-only. And a
parallel voice pipeline would drift from the text one: every fix to
classification, narrowing or ranking would have to be made twice.
"""
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.constants import persian_messages
from jira_telegram_bot.entities.speech import Transcript
from jira_telegram_bot.frameworks.telegram.daily_task_tracking_handler import (
    DailyTaskTrackingHandler,
)
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    TranscriptionError,
)


class TestVoiceRouting(unittest.IsolatedAsyncioTestCase):
    """What happens when somebody speaks instead of typing."""

    def setUp(self):
        self.handler = DailyTaskTrackingHandler.__new__(DailyTaskTrackingHandler)
        self.handler.transcribe_voice = AsyncMock()
        self.handler.transcribe_voice.execute.return_value = Transcript(
            text="دیروز 4 ساعت روی گزارش کار کردم", provider="fake",
        )
        self.handler.handle_text_message = AsyncMock()

        self.telegram_file = AsyncMock()
        self.telegram_file.file_path = "voice/file_1.oga"
        self.telegram_file.download_to_drive = AsyncMock(
            side_effect=lambda custom_path: Path(custom_path).write_bytes(b"a"),
        )

        self.voice = Mock()
        self.voice.mime_type = "audio/ogg"
        self.voice.duration = 12
        self.voice.get_file = AsyncMock(return_value=self.telegram_file)

        self.notice = AsyncMock()
        self.message = Mock()
        self.message.voice = self.voice
        self.message.audio = None
        self.message.reply_text = AsyncMock(return_value=self.notice)

        self.update = Mock()
        self.update.message = self.message
        self.context = Mock()

    async def test_the_transcript_is_routed_as_text(self):
        await self.handler.handle_voice_message(self.update, self.context)

        self.handler.handle_text_message.assert_awaited()
        routed = self.handler.handle_text_message.await_args.args[0]
        self.assertEqual(routed.message.text, "دیروز 4 ساعت روی گزارش کار کردم")

    async def test_the_stand_in_still_answers_like_a_real_message(self):
        """Everything but the text must reach the real message."""
        await self.handler.handle_voice_message(self.update, self.context)

        routed = self.handler.handle_text_message.await_args.args[0]
        self.assertIs(routed.message.reply_text, self.message.reply_text)

    async def test_what_was_heard_is_shown_before_it_is_acted_on(self):
        """A misheard report acted on silently writes the wrong hours."""
        await self.handler.handle_voice_message(self.update, self.context)

        shown = self.notice.edit_text.await_args.args[0]
        self.assertIn("دیروز 4 ساعت روی گزارش کار کردم", shown)

    async def test_the_duration_reaches_the_pipeline(self):
        """The length limit cannot be enforced without it."""
        await self.handler.handle_voice_message(self.update, self.context)

        self.assertEqual(
            self.handler.transcribe_voice.execute.await_args.kwargs[
                "duration_seconds"
            ],
            12,
        )

    async def test_a_failed_transcription_is_said_plainly(self):
        self.handler.transcribe_voice.execute.side_effect = TranscriptionError("x")

        await self.handler.handle_voice_message(self.update, self.context)

        self.notice.edit_text.assert_awaited_with(persian_messages.VOICE_FAILED)
        self.handler.handle_text_message.assert_not_awaited()

    async def test_an_unexpected_failure_does_not_leave_the_user_waiting(self):
        self.handler.transcribe_voice.execute.side_effect = RuntimeError("boom")

        await self.handler.handle_voice_message(self.update, self.context)

        self.notice.edit_text.assert_awaited_with(persian_messages.VOICE_FAILED)

    async def test_without_a_transcriber_the_user_is_told_to_type(self):
        self.handler.transcribe_voice = None

        await self.handler.handle_voice_message(self.update, self.context)

        self.message.reply_text.assert_awaited_with(
            persian_messages.VOICE_UNAVAILABLE,
        )

    async def test_an_audio_file_is_accepted_like_a_voice_note(self):
        self.message.voice = None
        self.message.audio = self.voice

        await self.handler.handle_voice_message(self.update, self.context)

        self.handler.handle_text_message.assert_awaited()

    async def test_a_message_with_neither_is_ignored(self):
        self.message.voice = None
        self.message.audio = None

        await self.handler.handle_voice_message(self.update, self.context)

        self.message.reply_text.assert_not_awaited()

    async def test_the_downloaded_file_is_cleaned_up(self):
        await self.handler.handle_voice_message(self.update, self.context)

        downloaded = Path(
            self.telegram_file.download_to_drive.await_args.kwargs["custom_path"],
        )
        self.assertFalse(downloaded.parent.exists())


if __name__ == "__main__":
    unittest.main()
