"""The pipeline around a speech backend, independent of which backend it is.

The point of the seam is that none of this changes when the provider does:
the limits, the ordering, and what happens when an optional stage fails are
all decided here rather than inside an adapter.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.speech import AudioClip, Transcript
from jira_telegram_bot.settings.speech_settings import SpeechSettings
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    TranscriptionError,
)
from jira_telegram_bot.use_cases.speech.transcribe_voice_use_case import (
    TranscribeVoiceUseCase,
)


def _stage(name, result=None, fails=False):
    stage = Mock()
    stage.name = name
    if fails:
        stage.apply = AsyncMock(side_effect=RuntimeError("stage broke"))
    else:
        stage.apply = AsyncMock(side_effect=lambda given: result or given)
    return stage


class TestTranscribeVoiceUseCase(unittest.IsolatedAsyncioTestCase):
    """What happens between a file arriving and text coming back."""

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "voice.oga"
        self.path.write_bytes(b"audio")

        self.transcriber = Mock()
        self.transcriber.name = "fake"
        self.transcriber.transcribe = AsyncMock(
            return_value=Transcript(text="چهار ساعت", provider="fake"),
        )
        self.settings = SpeechSettings()

    def tearDown(self):
        self.directory.cleanup()

    def _use_case(self, audio=(), text=(), settings=None):
        return TranscribeVoiceUseCase(
            transcriber=self.transcriber,
            settings=settings or self.settings,
            audio_stages=audio,
            text_stages=text,
        )

    async def test_the_transcript_comes_back(self):
        result = await self._use_case().execute(self.path)

        self.assertEqual(result.text, "چهار ساعت")

    async def test_the_configured_language_reaches_the_backend(self):
        await self._use_case().execute(self.path)

        self.assertEqual(
            self.transcriber.transcribe.await_args.kwargs["language"], "fa",
        )

    async def test_the_vocabulary_is_offered_to_the_backend(self):
        """A hosted model has never seen «آواخرد»; the prompt is the only lever."""
        await self._use_case().execute(self.path)

        vocabulary = self.transcriber.transcribe.await_args.kwargs["vocabulary"]
        self.assertIn("آواخرد", vocabulary)

    async def test_audio_stages_run_before_the_backend(self):
        converted = AudioClip(path=self.path.with_suffix(".wav"))
        stage = _stage("normalise", converted)

        await self._use_case(audio=[stage]).execute(self.path)

        stage.apply.assert_awaited()
        sent = self.transcriber.transcribe.await_args.args[0]
        self.assertEqual(sent.path.suffix, ".wav")

    async def test_stages_run_in_the_order_they_are_listed(self):
        order = []
        first, second = _stage("first"), _stage("second")
        first.apply = AsyncMock(side_effect=lambda c: order.append("first") or c)
        second.apply = AsyncMock(side_effect=lambda c: order.append("second") or c)

        await self._use_case(audio=[first, second]).execute(self.path)

        self.assertEqual(order, ["first", "second"])

    async def test_a_failing_audio_stage_never_costs_the_recording(self):
        """An optional improvement must not lose a usable recording."""
        result = await self._use_case(audio=[_stage("bad", fails=True)]).execute(
            self.path,
        )

        self.assertEqual(result.text, "چهار ساعت")

    async def test_a_failing_text_stage_never_costs_the_transcript(self):
        result = await self._use_case(text=[_stage("bad", fails=True)]).execute(
            self.path,
        )

        self.assertEqual(result.text, "چهار ساعت")

    async def test_text_stages_shape_the_result(self):
        polished = _stage("x", Transcript(text="4 ساعت", provider="fake"))

        result = await self._use_case(text=[polished]).execute(self.path)

        self.assertEqual(result.text, "4 ساعت")

    async def test_a_long_recording_is_refused_before_it_is_sent(self):
        """The limit exists to avoid paying for a doomed request."""
        with self.assertRaises(TranscriptionError):
            await self._use_case().execute(self.path, duration_seconds=99_999)

        self.transcriber.transcribe.assert_not_awaited()

    async def test_an_oversized_file_is_refused_before_it_is_sent(self):
        settings = SpeechSettings(max_bytes=2)

        with self.assertRaises(TranscriptionError):
            await self._use_case(settings=settings).execute(self.path)

        self.transcriber.transcribe.assert_not_awaited()

    async def test_a_missing_file_is_reported_as_a_transcription_error(self):
        with self.assertRaises(TranscriptionError):
            await self._use_case().execute(self.path.with_name("gone.oga"))

    async def test_an_empty_transcript_is_an_error_not_a_result(self):
        """Silence must not become an empty worklog report."""
        self.transcriber.transcribe.return_value = Transcript(text="   ")

        with self.assertRaises(TranscriptionError):
            await self._use_case().execute(self.path)

    async def test_a_backend_failure_reaches_the_caller(self):
        self.transcriber.transcribe.side_effect = TranscriptionError("down")

        with self.assertRaises(TranscriptionError):
            await self._use_case().execute(self.path)


if __name__ == "__main__":
    unittest.main()
