"""Backends and stages are chosen by name, so swapping one is configuration.

The registry is the whole point of the abstraction: a second backend is a
factory entry here, and nothing outside this module learns its name.
"""
import unittest

from jira_telegram_bot.adapters.speech import registry
from jira_telegram_bot.settings.openai_settings import OpenAISettings
from jira_telegram_bot.settings.speech_settings import SpeechSettings


class TestRegistry(unittest.TestCase):
    """Turning settings into objects."""

    def setUp(self):
        self.openai = OpenAISettings(token="sk-test")

    def test_the_default_provider_builds(self):
        transcriber = registry.build_transcriber(self.openai, SpeechSettings())

        self.assertEqual(transcriber.name, "openai_whisper")

    def test_an_unknown_provider_fails_at_startup(self):
        """A typo must not surface as a broken voice message hours later."""
        settings = SpeechSettings(provider="nope")

        with self.assertRaises(ValueError) as caught:
            registry.build_transcriber(self.openai, settings)

        self.assertIn("openai_whisper", str(caught.exception))

    def test_a_new_backend_needs_only_a_registry_entry(self):
        """What "pluggable" has to mean, asserted rather than claimed."""
        class Fake:
            name = "fake"
            accepts = frozenset({"wav"})

            async def transcribe(self, clip, language=None, vocabulary=""):
                return None

        registry.TRANSCRIBERS["fake"] = lambda openai, speech: Fake()
        try:
            built = registry.build_transcriber(
                self.openai, SpeechSettings(provider="fake"),
            )
            self.assertEqual(built.name, "fake")
        finally:
            registry.TRANSCRIBERS.pop("fake")

    def test_stages_are_built_in_the_configured_order(self):
        settings = SpeechSettings(
            text_stages=["vocabulary", "persian_digits"],
        )

        stages = registry.build_text_stages(settings)

        self.assertEqual(
            [stage.name for stage in stages], ["vocabulary", "persian_digits"],
        )

    def test_an_unknown_stage_is_skipped_not_fatal(self):
        """A missing optional stage is not worth refusing to start over."""
        settings = SpeechSettings(text_stages=["persian_digits", "imaginary"])

        stages = registry.build_text_stages(settings)

        self.assertEqual([stage.name for stage in stages], ["persian_digits"])

    def test_no_stages_configured_means_no_stages_run(self):
        self.assertEqual(registry.build_audio_stages(SpeechSettings(audio_stages=[])), [])


if __name__ == "__main__":
    unittest.main()
