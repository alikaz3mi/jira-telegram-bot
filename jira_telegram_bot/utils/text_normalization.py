"""Utilities for normalising Persian / Arabic text before JQL queries."""
from __future__ import annotations

import re
import unicodedata
from typing import List

ZERO_WIDTH_NON_JOINER = "\u200c"
ZERO_WIDTH_JOINER = "\u200d"
ZERO_WIDTH_SPACE = "\u200b"
ARABIC_KESHIDA = "\u0640"

_ZERO_WIDTH_RE = re.compile(
    f"[{ZERO_WIDTH_NON_JOINER}{ZERO_WIDTH_JOINER}{ZERO_WIDTH_SPACE}]",
)

_ARABIC_YEH = "\u064a"
_PERSIAN_YEH = "\u06cc"
_ARABIC_KEH = "\u0643"
_PERSIAN_KEH = "\u06a9"

_JQL_RESERVED_RE = re.compile(r'([\\"\'])')


def normalize_persian_text(text: str) -> str:
    """Normalise Persian/Arabic text for reliable comparison.

    Strips zero-width characters, normalises Arabic ي/ك to
    Persian ی/ک, collapses redundant whitespace, and applies
    Unicode NFC normalisation.

    Args:
        text: Raw input string.

    Returns:
        Normalised string suitable for comparison.
    """
    result = unicodedata.normalize("NFC", text)
    result = _ZERO_WIDTH_RE.sub("", result)
    result = result.replace(ARABIC_KESHIDA, "")
    result = result.replace(_ARABIC_YEH, _PERSIAN_YEH)
    result = result.replace(_ARABIC_KEH, _PERSIAN_KEH)
    result = " ".join(result.split())
    return result.strip()


def escape_jql_string(text: str) -> str:
    """Escape a string so it can be safely embedded in a JQL query.

    Args:
        text: Raw string to embed in JQL.

    Returns:
        Escaped string safe for use inside JQL double-quotes.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def build_jql_summary_search(
    project_key: str,
    summary: str,
    issue_type: str | None = None,
    exact: bool = False,
) -> str:
    """Build a JQL query for finding issues by summary.

    When ``exact=True`` the query uses ``summary = "..."`` for a
    strict string comparison (recommended for story/epic lookups).
    When ``exact=False`` the summary is normalised and the query
    uses ``summary ~ "..."`` for Lucene full-text search.

    Args:
        project_key: Jira project key (e.g. ``PARSCHAT``).
        summary: Human-readable summary to search for.
        issue_type: Optional issue type filter (e.g. ``Story``).
        exact: Use ``summary =`` instead of ``summary ~``.

    Returns:
        Ready-to-use JQL string.
    """
    if exact:
        escaped = escape_jql_string(summary)
        operator = "="
    else:
        normalised = normalize_persian_text(summary)
        escaped = escape_jql_string(normalised)
        operator = "~"

    if issue_type:
        jql = (
            f'project = "{project_key}" AND issuetype = {issue_type} '
            f'AND summary {operator} "{escaped}"'
        )
    else:
        jql = f'project = "{project_key}" AND summary {operator} "{escaped}"'
    return jql


def summaries_match(actual: str, expected: str) -> bool:
    """Compare two summaries after Persian normalisation.

    Args:
        actual: Summary from Jira issue.
        expected: Summary from Google Sheet / user input.

    Returns:
        True if the normalised texts are equal.
    """
    return normalize_persian_text(actual) == normalize_persian_text(expected)
