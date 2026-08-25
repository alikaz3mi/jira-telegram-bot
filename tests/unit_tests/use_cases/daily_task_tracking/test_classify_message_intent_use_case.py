"""Unit tests for ClassifyMessageIntentUseCase."""
import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.use_cases.daily_task_tracking.classify_message_intent_use_case import (
    ClassifyMessageIntentUseCase,
    MessageIntent,
)


class TestClassifyMessageIntentUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for ClassifyMessageIntentUseCase."""

    def setUp(self):
        self.ai_service = AsyncMock()
        self.use_case = ClassifyMessageIntentUseCase(
            ai_service=self.ai_service,
            prompt_catalog=AsyncMock(),
        )

    async def test_each_intent_is_returned(self):
        """Every documented intent maps to its enum member."""
        for raw, expected in [
            ("worklog", MessageIntent.WORKLOG),
            ("question", MessageIntent.QUESTION),
            ("chitchat", MessageIntent.CHITCHAT),
        ]:
            self.ai_service.run.return_value = {"intent": raw}
            self.assertIs(await self.use_case.execute("..."), expected)

    async def test_unknown_intent_falls_back_to_chitchat(self):
        """An unrecognised label must not be treated as a worklog."""
        self.ai_service.run.return_value = {"intent": "banana"}

        self.assertIs(
            await self.use_case.execute("..."), MessageIntent.CHITCHAT,
        )

    async def test_model_failure_falls_back_to_chitchat(self):
        """A failed call does nothing rather than logging time."""
        self.ai_service.run.side_effect = Exception("openai down")

        self.assertIs(
            await self.use_case.execute("..."), MessageIntent.CHITCHAT,
        )

    async def test_empty_message_skips_the_model(self):
        """Blank text is not worth a call."""
        self.assertIs(
            await self.use_case.execute("   "), MessageIntent.CHITCHAT,
        )
        self.ai_service.run.assert_not_called()

    async def test_case_and_spacing_are_tolerated(self):
        """The model's casing should not change the routing."""
        self.ai_service.run.return_value = {"intent": "  WorkLog "}

        self.assertIs(await self.use_case.execute("..."), MessageIntent.WORKLOG)


if __name__ == "__main__":
    unittest.main()
