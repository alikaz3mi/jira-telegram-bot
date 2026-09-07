"""Post-processing a transcript so the rest of the bot can read it.

A worklog parser looks for a number. A model transcribes "چهار ساعت" as
words, so without this stage the hours are invisible and the user is asked
how long they worked — for a message in which they already said.
"""
import unittest

from jira_telegram_bot.adapters.speech.text_stages import (
    PersianDigitsStage,
    VocabularyStage,
)
from jira_telegram_bot.entities.speech import Transcript


class TestPersianDigitsStage(unittest.IsolatedAsyncioTestCase):
    """Spoken numerals become digits."""

    def setUp(self):
        self.stage = PersianDigitsStage()

    async def _clean(self, text):
        return (await self.stage.apply(Transcript(text=text))).text

    async def test_a_spoken_number_becomes_a_digit(self):
        self.assertEqual(await self._clean("چهار ساعت"), "4 ساعت")

    async def test_persian_digits_become_latin_digits(self):
        self.assertEqual(await self._clean("۴ ساعت"), "4 ساعت")

    async def test_a_half_hour_becomes_a_decimal(self):
        self.assertEqual(await self._clean("دو ساعت و نیم"), "2.5 ساعت")

    async def test_a_quarter_hour_becomes_a_decimal(self):
        self.assertEqual(await self._clean("سه ساعت و ربع"), "3.25 ساعت")

    async def test_several_numbers_are_all_converted(self):
        self.assertEqual(
            await self._clean("دو ساعت پارسچت و سه ساعت آواخرد"),
            "2 ساعت پارسچت و 3 ساعت آواخرد",
        )

    async def test_a_number_inside_a_word_is_left_alone(self):
        """«دهکده» contains «ده» but is not the number ten."""
        self.assertIn("دهکده", await self._clean("دهکده"))

    async def test_text_without_numbers_is_untouched(self):
        text = "روی گزارش کار کردم"

        self.assertEqual(await self._clean(text), text)


class TestVocabularyStage(unittest.IsolatedAsyncioTestCase):
    """The team's own words, which no hosted model has ever seen."""

    def setUp(self):
        self.stage = VocabularyStage(["آواخرد", "پارس‌چت", "APISIX", "خردیار"])

    async def _clean(self, text):
        return (await self.stage.apply(Transcript(text=text))).text

    async def test_a_near_miss_is_repaired(self):
        """A project name that is close but wrong defeats the alias table."""
        self.assertIn("آواخرد", await self._clean("روی آواخرت کار کردم"))

    async def test_a_correct_term_is_left_alone(self):
        self.assertIn("آواخرد", await self._clean("روی آواخرد کار کردم"))

    async def test_a_zwnj_spelling_matches_one_without(self):
        self.assertIn("پارس‌چت", await self._clean("روی پارسچت کار کردم"))

    async def test_an_unrelated_word_is_not_rewritten(self):
        cleaned = await self._clean("روی گزارش کار کردم")

        self.assertNotIn("آواخرد", cleaned)
        self.assertIn("گزارش", cleaned)

    async def test_short_words_are_never_rewritten(self):
        """Two letters are too little evidence to overwrite somebody's words."""
        self.assertEqual(await self._clean("به من بگو"), "به من بگو")

    async def test_an_empty_vocabulary_changes_nothing(self):
        stage = VocabularyStage([])
        text = "روی آواخرت کار کردم"

        self.assertEqual((await stage.apply(Transcript(text=text))).text, text)


if __name__ == "__main__":
    unittest.main()
