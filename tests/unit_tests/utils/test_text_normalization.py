"""Unit tests for Persian/Arabic text normalisation utilities."""
from __future__ import annotations

import unittest

from jira_telegram_bot.utils.text_normalization import (
    build_jql_summary_search,
    escape_jql_string,
    normalize_persian_text,
    summaries_match,
)


class TestNormalizePersianText(unittest.TestCase):
    """Tests for normalize_persian_text."""

    def test_strips_zero_width_non_joiner(self):
        raw = "پیاده\u200cسازی"
        result = normalize_persian_text(raw)
        self.assertEqual(result, "پیادهسازی")
        self.assertNotIn("\u200c", result)

    def test_strips_zero_width_joiner(self):
        raw = "some\u200dtext"
        result = normalize_persian_text(raw)
        self.assertEqual(result, "sometext")

    def test_strips_zero_width_space(self):
        raw = "hello\u200bworld"
        result = normalize_persian_text(raw)
        self.assertEqual(result, "helloworld")

    def test_strips_arabic_keshida(self):
        raw = "کلمـــه"
        result = normalize_persian_text(raw)
        self.assertEqual(result, "کلمه")

    def test_normalises_arabic_yeh_to_persian(self):
        raw = "عربي"
        result = normalize_persian_text(raw)
        self.assertIn("\u06cc", result)
        self.assertNotIn("\u064a", result)

    def test_normalises_arabic_keh_to_persian(self):
        raw = "كلمه"
        result = normalize_persian_text(raw)
        self.assertIn("\u06a9", result)
        self.assertNotIn("\u0643", result)

    def test_collapses_whitespace(self):
        raw = "  hello   world  "
        result = normalize_persian_text(raw)
        self.assertEqual(result, "hello world")

    def test_empty_string(self):
        self.assertEqual(normalize_persian_text(""), "")

    def test_whitespace_only(self):
        self.assertEqual(normalize_persian_text("   "), "")

    def test_latin_text_unchanged(self):
        text = "Hello World"
        self.assertEqual(normalize_persian_text(text), "Hello World")

    def test_full_persian_sentence_with_zwnj(self):
        raw = "پیاده\u200cسازی منطق احراز هویت و ذخیره توکن"
        result = normalize_persian_text(raw)
        self.assertEqual(result, "پیادهسازی منطق احراز هویت و ذخیره توکن")
        self.assertNotIn("\u200c", result)

    def test_mixed_arabic_persian_chars(self):
        raw = "\u064a\u0643"
        expected = "\u06cc\u06a9"
        self.assertEqual(normalize_persian_text(raw), expected)


class TestEscapeJqlString(unittest.TestCase):
    """Tests for escape_jql_string."""

    def test_escapes_double_quotes(self):
        self.assertEqual(escape_jql_string('say "hello"'), 'say \\"hello\\"')

    def test_escapes_backslash(self):
        self.assertEqual(escape_jql_string("path\\to"), "path\\\\to")

    def test_plain_text_unchanged(self):
        self.assertEqual(escape_jql_string("hello world"), "hello world")

    def test_empty_string(self):
        self.assertEqual(escape_jql_string(""), "")

    def test_combined_backslash_and_quotes(self):
        self.assertEqual(
            escape_jql_string('a\\b"c'),
            'a\\\\b\\"c',
        )


class TestBuildJqlSummarySearch(unittest.TestCase):
    """Tests for build_jql_summary_search."""

    def test_basic_query_without_issue_type(self):
        jql = build_jql_summary_search("PROJ", "test summary")
        self.assertIn('project = "PROJ"', jql)
        self.assertIn('summary ~ "test summary"', jql)
        self.assertNotIn("issuetype", jql)

    def test_query_with_issue_type(self):
        jql = build_jql_summary_search("PROJ", "test", issue_type="Story")
        self.assertIn("issuetype = Story", jql)
        self.assertIn('summary ~ "test"', jql)

    def test_persian_summary_normalised(self):
        jql = build_jql_summary_search("PROJ", "پیاده\u200cسازی")
        self.assertNotIn("\u200c", jql)
        self.assertIn("پیادهسازی", jql)

    def test_quotes_in_summary_escaped(self):
        jql = build_jql_summary_search("PROJ", 'say "hi"')
        self.assertIn('\\"hi\\"', jql)

    def test_arabic_chars_normalised_in_jql(self):
        jql = build_jql_summary_search("PROJ", "\u064a\u0643")
        self.assertIn("\u06cc\u06a9", jql)
        self.assertNotIn("\u064a", jql)

    def test_epic_query(self):
        jql = build_jql_summary_search("BOARD", "My Epic", issue_type="Epic")
        self.assertIn("issuetype = Epic", jql)
        self.assertIn('project = "BOARD"', jql)
        self.assertIn('summary ~ "My Epic"', jql)

    def test_exact_match_uses_fuzzy_operator(self):
        jql = build_jql_summary_search("PROJ", "exact title", exact=True)
        self.assertIn('summary ~ "exact title"', jql)

    def test_exact_match_with_issue_type(self):
        jql = build_jql_summary_search(
            "PROJ", "My Story", issue_type="Story", exact=True,
        )
        self.assertIn("issuetype = Story", jql)
        self.assertIn('summary ~ "My Story"', jql)

    def test_exact_match_normalises_persian_text(self):
        jql = build_jql_summary_search("PROJ", "پیاده\u200cسازی", exact=True)
        self.assertNotIn("\u200c", jql)
        self.assertIn("پیادهسازی", jql)

    def test_exact_match_escapes_quotes(self):
        jql = build_jql_summary_search("PROJ", 'say "hi"', exact=True)
        self.assertIn('\\"hi\\"', jql)

    def test_fuzzy_is_default(self):
        jql = build_jql_summary_search("PROJ", "hello")
        self.assertIn("summary ~", jql)


class TestSummariesMatch(unittest.TestCase):
    """Tests for summaries_match."""

    def test_identical_strings(self):
        self.assertTrue(summaries_match("hello", "hello"))

    def test_different_strings(self):
        self.assertFalse(summaries_match("hello", "world"))

    def test_zwnj_difference_ignored(self):
        actual = "پیاده\u200cسازی منطق"
        expected = "پیادهسازی منطق"
        self.assertTrue(summaries_match(actual, expected))

    def test_arabic_vs_persian_yeh(self):
        actual = "عرب\u064a"
        expected = "عرب\u06cc"
        self.assertTrue(summaries_match(actual, expected))

    def test_arabic_vs_persian_keh(self):
        actual = "\u0643لمه"
        expected = "\u06a9لمه"
        self.assertTrue(summaries_match(actual, expected))

    def test_whitespace_differences_ignored(self):
        actual = "  hello   world  "
        expected = "hello world"
        self.assertTrue(summaries_match(actual, expected))

    def test_empty_strings_match(self):
        self.assertTrue(summaries_match("", ""))

    def test_full_persian_with_mixed_issues(self):
        actual = "پیاده\u200cساز" + "\u064a" + " منطق احراز هو" + "\u06cc" + "ت"
        expected = "پیادهسازی منطق احراز هویت"
        self.assertTrue(summaries_match(actual, expected))


if __name__ == "__main__":
    unittest.main()
