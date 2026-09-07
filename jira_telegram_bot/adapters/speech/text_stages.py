"""Steps applied to a transcript after a backend has produced it."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Sequence

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.speech import Transcript
from jira_telegram_bot.use_cases.interfaces.transcriber_interface import (
    TextStageInterface,
)

# Spoken Persian numerals, as a transcript writes them. Only the range a
# worklog needs: nobody reports ninety hours in a day.
_SPOKEN_NUMBERS = {
    "صفر": "0", "یک": "1", "یه": "1", "دو": "2", "سه": "3", "چهار": "4",
    "پنج": "5", "شش": "6", "شیش": "7", "هفت": "7", "هشت": "8", "نه": "9",
    "ده": "10", "یازده": "11", "دوازده": "12",
}
_SPOKEN_NUMBERS["شیش"] = "6"

# Fractions attach to an hour rather than stand alone: "دو ساعت و نیم".
_FRACTIONS = {"نیم": ".5", "ربع": ".25"}

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# Below this a candidate is a different word, not a mis-heard one.
_VOCABULARY_FLOOR = 0.82


class PersianDigitsStage(TextStageInterface):
    """Turn spoken numerals into digits the worklog parser can read.

    A model transcribes "چهار ساعت" as words. Every downstream reader of a
    worklog — the parser, the arithmetic check — looks for a number, so a
    spelled-out one is invisible and the report comes back asking how long
    they worked.
    """

    @property
    def name(self) -> str:
        """The name this stage is selected by in settings."""
        return "persian_digits"

    async def apply(self, transcript: Transcript) -> Transcript:
        """Rewrite spoken numbers as digits.

        Args:
            transcript: The text as the backend produced it

        Returns:
            The text with numerals in digit form.
        """
        try:
            text = transcript.text.translate(_PERSIAN_DIGITS)
            text = self._spell_out(text)
        except Exception as exc:
            LOGGER.warning(f"Could not normalise numerals: {exc}")
            return transcript
        return transcript.model_copy(update={"text": text})

    @staticmethod
    def _spell_out(text: str) -> str:
        """Replace number words with digits, handling "و نیم" as a fraction.

        Args:
            text: The transcript

        Returns:
            The transcript with numerals written as digits.
        """
        for word, digit in _SPOKEN_NUMBERS.items():
            text = re.sub(rf"(?<![\w؀-ۿ]){word}(?![\w؀-ۿ])",
                          digit, text)

        # "4 ساعت و نیم" -> "4.5 ساعت". Done after the words become digits so
        # the hour it attaches to is already a number.
        for word, fraction in _FRACTIONS.items():
            text = re.sub(
                rf"(\d+)\s*(ساعت)\s*و\s*{word}",
                lambda match, f=fraction: f"{match.group(1)}{f} {match.group(2)}",
                text,
            )
            text = re.sub(rf"(\d+)\s*و\s*{word}",
                          lambda m, f=fraction: f"{m.group(1)}{f}", text)
        return text


class VocabularyStage(TextStageInterface):
    """Repair the team's own terms when a model mis-hears them.

    A hosted model has never seen "آواخرد" or "APISIX". It writes something
    phonetically close, and a project name that is close but wrong defeats
    every downstream lookup — the alias table matches exact strings.
    """

    def __init__(self, vocabulary: Sequence[str]):
        """Initialize the stage.

        Args:
            vocabulary: The terms worth repairing, from settings
        """
        self._vocabulary = [term for term in vocabulary if term.strip()]

    @property
    def name(self) -> str:
        """The name this stage is selected by in settings."""
        return "vocabulary"

    async def apply(self, transcript: Transcript) -> Transcript:
        """Replace near-misses of known terms with the term itself.

        Args:
            transcript: The text as the backend produced it

        Returns:
            The text with the team's vocabulary spelled correctly.
        """
        if not self._vocabulary:
            return transcript

        try:
            repaired = self._repair(transcript.text)
        except Exception as exc:
            LOGGER.warning(f"Could not repair vocabulary: {exc}")
            return transcript
        return transcript.model_copy(update={"text": repaired})

    def _repair(self, text: str) -> str:
        """Rewrite each word that is a near-miss of a known term.

        Args:
            text: The transcript

        Returns:
            The transcript with near-misses corrected.
        """
        def replace(match: re.Match) -> str:
            word = match.group(0)
            best, score = self._closest(word)
            if best is None or best == word:
                return word
            LOGGER.info(f"Vocabulary repaired {word!r} -> {best!r} ({score:.2f})")
            return best

        return re.sub(r"[\w؀-ۿ‌]+", replace, text)

    def _closest(self, word: str):
        """The known term this word is closest to, when close enough.

        Args:
            word: One word from the transcript

        Returns:
            The term and its score, or (None, 0.0) when nothing is close.
        """
        if len(word) < 3:
            return None, 0.0

        folded = word.replace("‌", "").casefold()
        best, best_score = None, 0.0
        for term in self._vocabulary:
            candidate = term.replace("‌", "").casefold()
            if candidate == folded:
                return term, 1.0
            score = SequenceMatcher(None, folded, candidate).ratio()
            if score > best_score:
                best, best_score = term, score

        return (best, best_score) if best_score >= _VOCABULARY_FLOOR else (None, 0.0)
