"""Unit tests for TelegramPostDataStore.find_group_chat_by_issue prioritization logic."""
import unittest

from jira_telegram_bot.adapters.repositories.file_storage import TelegramPostDataStore


class TestFindGroupChatByIssuePrioritization(unittest.TestCase):
    """Test that find_group_chat_by_issue correctly prioritizes entries with reply_message_id."""

    def setUp(self):
        """Set up test fixtures."""
        self.data_store = TelegramPostDataStore()

    def test_prioritizes_entry_with_reply_message_id_and_forwarded(self):
        """Should return entry with reply_message_id and different group_chat_id first."""
        data = {
            "1637": {
                "type": "jira_issue_mapping",
                "issue_key": "PCT-1090",
                "channel_chat_id": -1002309379531,
                "group_chat_id": -1002309379531,  # Same as channel - not forwarded
                "metadata": {"content_type": "photo"},
            },
            "1638": {
                "type": "jira_issue_mapping",
                "issue_key": "PCT-1090",
                "channel_chat_id": -1002309379531,
                "group_chat_id": -1002491201232,  # Different - forwarded to group
                "reply_message_id": 7952,
                "metadata": {"content_type": "photo", "forwarded_at": 1762934426},
            },
            "1639": {
                "type": "jira_issue_mapping",
                "issue_key": "PCT-1090",
                "channel_chat_id": -1002309379531,
                "group_chat_id": -1002491201232,
                "reply_message_id": 7953,
                "metadata": {"content_type": "photo", "forwarded_at": 1762934426},
            },
        }

        result = self.data_store.find_group_chat_by_issue(data, "PCT-1090")

        self.assertIsNotNone(result)
        self.assertIn("reply_message_id", result)
        self.assertNotEqual(result["group_chat_id"], result["channel_chat_id"])

    def test_returns_entry_with_reply_message_id_when_no_forwarded(self):
        """Should return entry with reply_message_id even if not marked as forwarded."""
        data = {
            "100": {
                "type": "jira_issue_mapping",
                "issue_key": "TEST-1",
                "channel_chat_id": -123,
                "group_chat_id": -123,
                "metadata": {},
            },
            "101": {
                "type": "jira_issue_mapping",
                "issue_key": "TEST-1",
                "channel_chat_id": -123,
                "group_chat_id": -123,
                "reply_message_id": 500,
                "metadata": {},
            },
        }

        result = self.data_store.find_group_chat_by_issue(data, "TEST-1")

        self.assertIsNotNone(result)
        self.assertEqual(result["reply_message_id"], 500)

    def test_returns_first_match_when_no_reply_message_id(self):
        """Should return first match when none have reply_message_id."""
        data = {
            "200": {
                "type": "jira_issue_mapping",
                "issue_key": "TEST-2",
                "channel_chat_id": -456,
                "group_chat_id": -456,
                "metadata": {},
            },
            "201": {
                "type": "jira_issue_mapping",
                "issue_key": "TEST-2",
                "channel_chat_id": -456,
                "group_chat_id": -789,
                "metadata": {},
            },
        }

        result = self.data_store.find_group_chat_by_issue(data, "TEST-2")

        self.assertIsNotNone(result)
        self.assertEqual(result["issue_key"], "TEST-2")

    def test_returns_none_when_no_match(self):
        """Should return None when issue key is not found."""
        data = {
            "300": {
                "type": "jira_issue_mapping",
                "issue_key": "TEST-3",
                "channel_chat_id": -999,
                "group_chat_id": -999,
                "metadata": {},
            },
        }

        result = self.data_store.find_group_chat_by_issue(data, "NONEXISTENT-1")

        self.assertIsNone(result)

    def test_handles_empty_data_store(self):
        """Should return None for empty data store."""
        result = self.data_store.find_group_chat_by_issue({}, "ANY-1")

        self.assertIsNone(result)

    def test_prioritizes_correct_entry_in_media_group(self):
        """Real-world scenario: media group with 3 photos, should pick forwarded entry."""
        data = {
            "1637": {
                "type": "jira_issue_mapping",
                "issue_key": "PCT-1090",
                "channel_chat_id": -1002309379531,
                "group_chat_id": -1002309379531,
                "metadata": {
                    "created_at": 1762934418,
                    "creator_id": 7810734788,
                    "creator_username": "ParschatAI_support202",
                    "content_type": "photo",
                    "message_type": "channel_post",
                },
            },
            "1638": {
                "type": "jira_issue_mapping",
                "issue_key": "PCT-1090",
                "channel_chat_id": -1002309379531,
                "group_chat_id": -1002491201232,
                "metadata": {
                    "created_at": 1762934418,
                    "creator_id": 7810734788,
                    "creator_username": "ParschatAI_support202",
                    "content_type": "photo",
                    "message_type": "channel_post",
                    "forwarded_at": 1762934426,
                },
                "reply_message_id": 7952,
            },
            "1639": {
                "type": "jira_issue_mapping",
                "issue_key": "PCT-1090",
                "channel_chat_id": -1002309379531,
                "group_chat_id": -1002491201232,
                "metadata": {
                    "created_at": 1762934418,
                    "creator_id": 7810734788,
                    "creator_username": "ParschatAI_support202",
                    "content_type": "photo",
                    "message_type": "channel_post",
                    "forwarded_at": 1762934426,
                },
                "reply_message_id": 7953,
            },
        }

        result = self.data_store.find_group_chat_by_issue(data, "PCT-1090")

        # Should pick one of the forwarded entries (1638 or 1639), not 1637
        self.assertIsNotNone(result)
        self.assertIn("reply_message_id", result)
        self.assertEqual(result["group_chat_id"], -1002491201232)
        self.assertIn(result["reply_message_id"], [7952, 7953])


if __name__ == "__main__":
    unittest.main()
