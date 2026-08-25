"""Unit tests for ConversationMemory."""
import unittest

from jira_telegram_bot.entities.daily_task_tracking.conversation_turn import (
    ConversationMemory,
    MAX_TURNS,
)


class TestConversationMemory(unittest.TestCase):
    """Test cases for ConversationMemory."""

    def test_empty_memory_renders_nothing(self):
        """A first message has no history to reason about."""
        self.assertEqual(ConversationMemory().render(), "")

    def test_turns_render_oldest_first(self):
        """Order matters: a follow-up refers to the most recent reply."""
        memory = ConversationMemory()
        memory.remember("سلام", "سلام!")
        memory.remember("تسکام چیه؟", "دو تا داری")

        rendered = memory.render()

        self.assertLess(rendered.index("سلام"), rendered.index("تسکام چیه؟"))
        self.assertIn("assistant: دو تا داری", rendered)

    def test_window_keeps_only_the_recent_turns(self):
        """Old topics must not steer a new question."""
        memory = ConversationMemory()
        for index in range(MAX_TURNS + 4):
            memory.remember(f"q{index}", f"a{index}")

        self.assertEqual(len(memory.turns), MAX_TURNS)
        self.assertEqual(memory.turns[-1].user, f"q{MAX_TURNS + 3}")
        self.assertNotIn("q0", memory.render())


if __name__ == "__main__":
    unittest.main()
