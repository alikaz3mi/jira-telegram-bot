"""Topic search, and the floor that decides a subject is absent.

Asked what was planned for Instagram, the assistant listed all six epics in
the sprint — four of them unrelated — because no tool could filter by
subject. A keyword filter would have been little better: it finds only the
issues that spell the word out, missing «ویترین» and «کامنت» that are
plainly the same work.

The floor here is higher than the worklog floor. A worklog names one issue;
a topic spans an epic, and a subject the project has never heard of still
scores ~0.35 against dozens of summaries.
"""
import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.settings.embedding_settings import EmbeddingSettings
from jira_telegram_bot.use_cases.daily_task_tracking.rank_candidates_use_case import (
    RankCandidatesUseCase,
)


def _unit(*values):
    magnitude = sum(value * value for value in values) ** 0.5
    return [value / magnitude for value in values]


class TestTopicSearch(unittest.IsolatedAsyncioTestCase):
    """Ranking arbitrary texts, and recognising nothing matched."""

    def setUp(self):
        self.embeddings = AsyncMock()
        self.use_case = RankCandidatesUseCase(
            embedding_service=self.embeddings,
            settings=EmbeddingSettings(),
        )

    async def test_related_texts_are_returned_best_first(self):
        self.embeddings.embed.return_value = [
            _unit(1, 0),
            _unit(0.2, 1),
            _unit(1, 0.1),
            _unit(1, 0.5),
        ]

        ranked = await self.use_case.rank_texts("اینستاگرام", ["a", "b", "c"])

        self.assertEqual([index for index, _ in ranked], [1, 2])

    async def test_an_absent_subject_returns_nothing(self):
        """A topic the project never heard of still scores ~0.35 on noise."""
        self.embeddings.embed.return_value = [
            _unit(1, 0, 0),
            _unit(0.35, 1, 0),
            _unit(0.34, 0, 1),
            _unit(0.30, 1, 1),
        ]

        ranked = await self.use_case.rank_texts("بلاکچین", ["a", "b", "c"])

        self.assertEqual(ranked, [])

    async def test_the_topic_floor_is_stricter_than_the_worklog_floor(self):
        settings = EmbeddingSettings()

        self.assertGreater(settings.min_topic_similarity, settings.min_similarity)

    async def test_embedding_failure_is_distinguishable_from_no_match(self):
        """None means "could not search"; [] means "searched, found nothing"."""
        self.embeddings.embed.return_value = []

        self.assertIsNone(await self.use_case.rank_texts("x", ["a"]))

    async def test_empty_input_is_not_embedded(self):
        self.assertIsNone(await self.use_case.rank_texts("", ["a"]))
        self.assertIsNone(await self.use_case.rank_texts("x", []))
        self.embeddings.embed.assert_not_called()

    async def test_the_query_leads_the_batch(self):
        self.embeddings.embed.return_value = [_unit(1, 0), _unit(1, 0)]

        await self.use_case.rank_texts("اینستاگرام", ["a"])

        self.assertEqual(self.embeddings.embed.call_args.args[0][0], "اینستاگرام")

    async def test_results_are_capped(self):
        many = [f"t{i}" for i in range(60)]
        self.embeddings.embed.return_value = [_unit(1, 0)] + [
            _unit(1, 0.01) for _ in many
        ]

        ranked = await self.use_case.rank_texts("x", many)

        self.assertLessEqual(len(ranked), EmbeddingSettings().topic_matches)


if __name__ == "__main__":
    unittest.main()
