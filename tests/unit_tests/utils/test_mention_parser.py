"""Unit tests for Jira mention parsing utilities."""

import unittest

from jira_telegram_bot.utils.mention_parser import extract_jira_mentions


class TestMentionParser(unittest.TestCase):
    """Test cases for Jira mention parsing."""
    
    def test_extract_markup_mentions(self):
        """Test extracting mentions in [~username] format."""
        text = "Hey [~john_doe], can you review this? Also CC [~jane_smith]"
        mentions = extract_jira_mentions(text)
        self.assertIn("john_doe", mentions)
        self.assertIn("jane_smith", mentions)
        self.assertEqual(len(mentions), 2)
    
    def test_extract_plain_mentions(self):
        """Test extracting mentions in ~username format."""
        text = "Hey ~john_doe can you review this? Also CC ~jane_smith"
        mentions = extract_jira_mentions(text)
        self.assertIn("john_doe", mentions)
        self.assertIn("jane_smith", mentions)
        self.assertEqual(len(mentions), 2)
    
    def test_extract_mixed_mentions(self):
        """Test extracting both markup and plain mentions."""
        text = "Hey [~john_doe] and ~jane_smith, please review"
        mentions = extract_jira_mentions(text)
        self.assertIn("john_doe", mentions)
        self.assertIn("jane_smith", mentions)
        self.assertEqual(len(mentions), 2)
    
    def test_extract_no_mentions(self):
        """Test text with no mentions."""
        text = "This is just a regular comment with no mentions"
        mentions = extract_jira_mentions(text)
        self.assertEqual(len(mentions), 0)
    
    def test_extract_mention_with_underscores_and_dots(self):
        """Test mentions with underscores and dots."""
        text = "Please check [~first.last_123] and ~user_name.test"
        mentions = extract_jira_mentions(text)
        self.assertIn("first.last_123", mentions)
        self.assertIn("user_name.test", mentions)
    
    def test_extract_persian_text_with_mentions(self):
        """Test mentions in Persian text."""
        text = "سلام [~a_nasim] این کار رو چک کن"
        mentions = extract_jira_mentions(text)
        self.assertIn("a_nasim", mentions)
    
    def test_extract_mention_at_start(self):
        """Test mention at the start of text."""
        text = "~username please review this"
        mentions = extract_jira_mentions(text)
        self.assertIn("username", mentions)
    
    def test_extract_mention_at_end(self):
        """Test mention at the end of text."""
        text = "please review this ~username"
        mentions = extract_jira_mentions(text)
        self.assertIn("username", mentions)
    
    def test_extract_duplicate_mentions(self):
        """Test that duplicate mentions are deduplicated."""
        text = "[~john_doe] please check. Hey ~john_doe are you there?"
        mentions = extract_jira_mentions(text)
        self.assertEqual(mentions.count("john_doe"), 1)
    
    def test_extract_empty_text(self):
        """Test empty text."""
        mentions = extract_jira_mentions("")
        self.assertEqual(len(mentions), 0)
    
    def test_extract_none_text(self):
        """Test None text."""
        mentions = extract_jira_mentions(None)
        self.assertEqual(len(mentions), 0)


if __name__ == "__main__":
    unittest.main()
