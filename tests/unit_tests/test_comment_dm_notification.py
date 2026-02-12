"""Unit tests for comment DM notification to assignee."""
import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from jira_telegram_bot.frameworks.fast_api.create_ticket import handle_comment_event


class TestCommentDMNotification(unittest.IsolatedAsyncioTestCase):
    """Test that assignees receive DM when someone else comments on their task."""

    async def test_sends_dm_to_assignee_when_comment_from_other_user(self):
        """Should send DM to assignee when comment is from a different user."""
        # Setup mock data
        issue_key = "PROJ1-1090"
        body = {
            "comment": {
                "body": "Please review this task urgently.",
                "author": {"name": "a_kazemi"},
            }
        }
        
        # Mock assignee is different from commenter
        mock_assignee = MagicMock()
        mock_assignee.name = "m_Mousavi"
        
        mock_issue = MagicMock()
        mock_issue.fields.assignee = mock_assignee
        mock_issue.fields.summary = "Test task"
        
        with patch("jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository") as mock_jira_repo, \
             patch("jira_telegram_bot.frameworks.fast_api.create_ticket.send_telegram_message") as mock_send, \
             patch("jira_telegram_bot.frameworks.fast_api.create_ticket.lookup_user_config_by_jira_username") as mock_lookup:
            
            mock_jira_repo.jira.issue.return_value = mock_issue
            
            # Mock user configs
            commenter_cfg = MagicMock()
            commenter_cfg.telegram_username = "admin_user"
            commenter_cfg.telegram_user_chat_id = 100375147
            
            assignee_cfg = MagicMock()
            assignee_cfg.telegram_username = "Mousavi_Shoushtari"
            assignee_cfg.telegram_user_chat_id = 163558016
            
            def lookup_side_effect(username):
                if username == "a_kazemi":
                    return commenter_cfg
                elif username == "m_Mousavi":
                    return assignee_cfg
                return None
            
            mock_lookup.side_effect = lookup_side_effect
            
            # Execute
            await handle_comment_event(body, -1002491201232, 7952, issue_key)
            
            # Verify: Should send 2 messages (1 to group, 1 DM to assignee)
            self.assertEqual(mock_send.call_count, 2)
            
            # Check DM to assignee
            dm_call = mock_send.call_args_list[1]
            self.assertEqual(dm_call[0][0], 163558016)  # assignee's chat_id
            self.assertIn("@admin_user", dm_call[0][1])  # commenter mention
            self.assertIn("PROJ1-1090", dm_call[0][1])  # issue key
            self.assertIn("Please review this task urgently", dm_call[0][1])  # comment body

    async def test_does_not_send_dm_when_assignee_comments_on_own_task(self):
        """Should NOT send DM to assignee when they comment on their own task."""
        issue_key = "PROJ1-1090"
        body = {
            "comment": {
                "body": "I'm working on this.",
                "author": {"name": "m_Mousavi"},
            }
        }
        
        # Mock assignee is same as commenter
        mock_assignee = MagicMock()
        mock_assignee.name = "m_Mousavi"
        
        mock_issue = MagicMock()
        mock_issue.fields.assignee = mock_assignee
        
        with patch("jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository") as mock_jira_repo, \
             patch("jira_telegram_bot.frameworks.fast_api.create_ticket.send_telegram_message") as mock_send, \
             patch("jira_telegram_bot.frameworks.fast_api.create_ticket.lookup_user_config_by_jira_username") as mock_lookup:
            
            mock_jira_repo.jira.issue.return_value = mock_issue
            
            assignee_cfg = MagicMock()
            assignee_cfg.telegram_username = "Mousavi_Shoushtari"
            assignee_cfg.telegram_user_chat_id = 163558016
            
            mock_lookup.return_value = assignee_cfg
            
            # Execute
            await handle_comment_event(body, -1002491201232, 7952, issue_key)
            
            # Verify: Should send only 1 message (to group), no DM
            self.assertEqual(mock_send.call_count, 1)

    async def test_does_not_send_dm_when_no_assignee(self):
        """Should NOT send DM when task has no assignee."""
        issue_key = "PROJ1-1090"
        body = {
            "comment": {
                "body": "Anyone wants to take this?",
                "author": {"name": "a_kazemi"},
            }
        }
        
        # Mock no assignee
        mock_issue = MagicMock()
        mock_issue.fields.assignee = None
        
        with patch("jira_telegram_bot.frameworks.fast_api.create_ticket.jira_repository") as mock_jira_repo, \
             patch("jira_telegram_bot.frameworks.fast_api.create_ticket.send_telegram_message") as mock_send, \
             patch("jira_telegram_bot.frameworks.fast_api.create_ticket.lookup_user_config_by_jira_username") as mock_lookup:
            
            mock_jira_repo.jira.issue.return_value = mock_issue
            
            commenter_cfg = MagicMock()
            commenter_cfg.telegram_username = "admin_user"
            mock_lookup.return_value = commenter_cfg
            
            # Execute
            await handle_comment_event(body, -1002491201232, 7952, issue_key)
            
            # Verify: Should send only 1 message (to group), no DM
            self.assertEqual(mock_send.call_count, 1)

    async def test_skips_telegram_originated_comments(self):
        """Should skip comments that originated from Telegram (to avoid loops)."""
        issue_key = "PROJ1-1090"
        body = {
            "comment": {
                "body": "h6. Comment from @admin_user:\n\nThis comment came from Telegram",
                "author": {"name": "a_kazemi"},
            }
        }
        
        with patch("jira_telegram_bot.frameworks.fast_api.create_ticket.send_telegram_message") as mock_send:
            # Execute
            await handle_comment_event(body, -1002491201232, 7952, issue_key)
            
            # Verify: Should send NO messages (comment is from Telegram)
            mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
