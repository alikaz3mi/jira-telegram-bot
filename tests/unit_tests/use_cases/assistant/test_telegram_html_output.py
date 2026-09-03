"""The reply is sent as HTML, so Markdown in it renders as literal characters.

The tools already emit Telegram HTML. A model that decorates its relay with
`**bold**` puts asterisks on the user's screen, and one that rewrites an
`<a href>` as `[title](url)` puts a raw URL there and takes the link away —
both of which happened to a real briefing. Instructing the model not to is
unreliable, because the formatting is a habit rather than a decision, so the
conversion happens in Python where the guarantee holds.
"""
import unittest

from jira_telegram_bot.use_cases.assistant.task_assistant_agent import (
    TaskAssistantAgent,
)


class TestTelegramHtmlOutput(unittest.TestCase):
    """What survives the trip from the model to Telegram."""

    def _clean(self, text):
        return TaskAssistantAgent._as_telegram_html(text)

    def test_double_asterisks_are_removed(self):
        self.assertEqual(self._clean("**پروژه Kheradyar**"), "پروژه Kheradyar")

    def test_underscores_are_removed(self):
        self.assertEqual(self._clean("__bold__"), "bold")

    def test_single_asterisk_emphasis_is_removed(self):
        self.assertEqual(self._clean("*emphasis* here"), "emphasis here")

    def test_emphasis_spanning_lines_is_removed(self):
        self.assertEqual(self._clean("**multi\nline**"), "multi\nline")

    def test_html_tags_are_left_alone(self):
        markup = '<b>bold</b> and <a href="x">link</a>'

        self.assertEqual(self._clean(markup), markup)

    def test_a_lone_asterisk_is_content_not_markup(self):
        """A multiplication sign or a SQL star is not emphasis."""
        for text in ("2 * 3 = 6", "SELECT * FROM t", "a * b * c"):
            with self.subTest(text=text):
                self.assertEqual(self._clean(text), text)

    def test_a_markdown_link_becomes_an_anchor(self):
        """A relayed link must survive as a link, not become a bare URL."""
        result = self._clean(
            "[US-013 — گیت سرویس](https://jira.example.com/browse/PARSCHAT-5807)",
        )

        self.assertEqual(
            result,
            '<a href="https://jira.example.com/browse/PARSCHAT-5807">'
            "US-013 — گیت سرویس</a>",
        )

    def test_a_link_inside_emphasis_survives_both_passes(self):
        result = self._clean("**[کار](https://j/x)**")

        self.assertEqual(result, '<a href="https://j/x">کار</a>')

    def test_whitespace_around_the_url_is_tolerated(self):
        result = self._clean("[title]( https://j/x )")

        self.assertEqual(result, '<a href="https://j/x">title</a>')

    def test_a_query_string_is_escaped_inside_the_attribute(self):
        """An unescaped & in an href makes Telegram reject the message."""
        result = self._clean("[a & b](https://j/x?q=1&r=2)")

        self.assertEqual(
            result, '<a href="https://j/x?q=1&amp;r=2">a &amp; b</a>',
        )

    def test_brackets_that_are_not_links_are_left_alone(self):
        for text in ("see [1] and (2)", "[not a link](mailto:x@y.z)"):
            with self.subTest(text=text):
                self.assertEqual(self._clean(text), text)

    def test_a_url_repeated_beside_its_own_link_is_removed(self):
        """A Jira search URL is 200 characters of encoded JQL."""
        url = "https://j/issues/?jql=assignee%20%3D%20%22a_kazemi%22"

        result = self._clean(f'<a href="{url}">همه تسک‌ها</a>\n{url}')

        self.assertEqual(result, f'<a href="{url}">همه تسک‌ها</a>')

    def test_a_url_in_parentheses_beside_its_link_is_removed(self):
        url = "https://j/issues/?jql=x"

        result = self._clean(f'<a href="{url}">همه</a> ({url})')

        self.assertEqual(result, f'<a href="{url}">همه</a>')

    def test_an_unrelated_url_is_left_alone(self):
        """Only a duplicate of a link already present is noise."""
        markup = '<a href="https://j/x">t</a> and https://other/y'

        self.assertEqual(self._clean(markup), markup)

    def test_indentation_survives_url_removal(self):
        """A detail line sits under its own title, and must stay there."""
        markup = (
            '• <a href="https://j/browse/P-1">کار</a>\n'
            "   🟣 Review · P-1"
        )

        self.assertEqual(self._clean(markup), markup)

    def test_a_rendered_briefing_passes_through_unchanged(self):
        briefing = (
            "🔴 <b>۱ باگ فوری روی شما</b>\n"
            '• <a href="https://j/browse/P-1">کار</a>\n'
            "   🟣 Review · تا ۱۲ شهریور · P-1"
        )

        self.assertEqual(self._clean(briefing), briefing)


if __name__ == "__main__":
    unittest.main()
