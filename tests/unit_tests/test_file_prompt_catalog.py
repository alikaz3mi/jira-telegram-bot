from __future__ import annotations

import unittest

from jira_telegram_bot.adapters.repositories.file_storage.prompt_catalog import (
    FilePromptCatalog,
)
from jira_telegram_bot.entities.structured_prompt import StructuredPrompt


class MyTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.catalog = FilePromptCatalog()
        self.task = "generate_user_story"
        self.department = "test_department"
        self.user_id = "test_user_id"

    async def test_get_prompt(self):
        prompt = await self.catalog.get_prompt(self.task, self.department, self.user_id)

        self.assertIsInstance(prompt, StructuredPrompt)
        self.assertTrue(hasattr(prompt, "template"))
        self.assertTrue(hasattr(prompt, "schemas"))


if __name__ == "__main__":
    unittest.main()
