"""Normalisation for Persian text before any matching is attempted.

Persian arrives from Telegram in several encodings of the same word: Arabic
ي/ك where Persian ی/ک is meant, zero-width non-joiners inside compounds,
Arabic-Indic or Persian digits, and honorifics glued to names. Matching on
the raw string therefore misses obvious equivalences — "خانوم لطفیان" and
"لطفیان" are the same person, and trigram similarity cannot bridge them on
its own because the honorific is most of the string.

Everything that compares user text to a stored alias runs through
``normalize`` first, so the comparison is between comparable forms.
"""
from __future__ import annotations

import re

# Arabic code points that Persian keyboards and copy-paste routinely produce.
_CHAR_MAP = {
    "ي": "ی",  # Arabic yeh      -> Persian yeh
    "ى": "ی",  # Alef maksura    -> Persian yeh
    "ك": "ک",  # Arabic kaf      -> Persian keheh
    "ة": "ه",  # Teh marbuta     -> heh
    "أ": "ا",  # Alef with hamza above
    "إ": "ا",  # Alef with hamza below
    "آ": "ا",  # Alef with madda
    "ؤ": "و",  # Waw with hamza
    "ئ": "ی",  # Yeh with hamza
}

# Persian and Arabic-Indic digits, so "۱۲" and "١٢" both read as 12.
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# Diacritics, tatweel and the zero-width non-joiner carry no matching signal.
_STRIP_CHARS = re.compile(r"[ً-ْـ‌‏‎]")

# Titles people put in front of a name. Removing them leaves the name itself.
_HONORIFICS = (
    "خانوم", "خانم", "اقای", "آقای", "اقا", "آقا", "جناب", "سرکار",
    "دکتر", "مهندس", "استاد", "mr", "mrs", "ms", "dr", "eng",
)

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s؀-ۿ]+")


def normalize(text: str) -> str:
    """Reduce Persian or Latin text to a form two spellings can be compared in.

    Args:
        text: Raw text as the user typed it

    Returns:
        The normalised form: unified characters, ASCII digits, no diacritics,
        no honorifics, collapsed whitespace, lower case.
    """
    if not text:
        return ""

    result = text.strip()
    for source, target in _CHAR_MAP.items():
        result = result.replace(source, target)
    result = result.translate(_DIGIT_MAP)
    result = _STRIP_CHARS.sub("", result)
    result = _PUNCTUATION.sub(" ", result)
    result = result.casefold()

    words = [word for word in _WHITESPACE.split(result) if word]
    # Only drop a leading honorific: "دکتر" alone may be a real search term.
    while len(words) > 1 and words[0] in _HONORIFICS:
        words.pop(0)

    return " ".join(words)


def similarity(left: str, right: str) -> float:
    """Score two strings by shared trigrams, the way ``pg_trgm`` does.

    Kept in Python so alias matching works without a database round-trip;
    the scores are close enough to Postgres' to share one threshold.

    Args:
        left: First string, already normalised
        right: Second string, already normalised

    Returns:
        A score between 0.0 and 1.0.
    """
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    left_grams = _trigrams(left)
    right_grams = _trigrams(right)
    if not left_grams or not right_grams:
        return 0.0

    shared = len(left_grams & right_grams)
    return shared / len(left_grams | right_grams)


def _trigrams(text: str) -> set[str]:
    """Return the padded trigram set of a string, as ``pg_trgm`` defines it."""
    padded = f"  {text} "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}
