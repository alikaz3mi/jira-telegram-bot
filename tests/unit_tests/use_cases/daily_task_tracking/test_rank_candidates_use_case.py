"""Similarity ranking, and knowing when it has found nothing.

Absolute similarity cannot separate a match from noise on this data:
nonsense scored 0.386 while a genuine near-miss scored 0.375. What does
separate them is the margin over the runner-up — real matches led by
0.15-0.27, non-matches by 0.02-0.04.
"""
import unittest
from unittest.mock import AsyncMock

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.settings.embedding_settings import EmbeddingSettings
from jira_telegram_bot.use_cases.daily_task_tracking.rank_candidates_use_case import (
    RankCandidatesUseCase,
)


def _task(key, summary):
    return DailyTaskCheck(
        issue_key=key,
        summary=summary,
        status="In Progress",
        assignee="a_kazemi",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key="PARSCHAT",
    )


def _unit(*values):
    """A unit-length vector along the given axes."""
    magnitude = sum(value * value for value in values) ** 0.5
    return [value / magnitude for value in values]


class TestRankCandidatesUseCase(unittest.IsolatedAsyncioTestCase):
    """Ranking issues by what the work was described as."""

    def setUp(self):
        self.candidates = [
            _task("PARSCHAT-5980", "حذف فراخوانی os.getenv"),
            _task("PARSCHAT-5813", "بهینه‌سازی کوئری‌های سنگین"),
            _task("PARSCHAT-5830", "مهاجرت داده مشتریان"),
        ]
        self.embeddings = AsyncMock()
        self.use_case = RankCandidatesUseCase(
            embedding_service=self.embeddings,
            settings=EmbeddingSettings(),
        )

    async def test_clear_winner_is_ranked_first(self):
        self.embeddings.embed.return_value = [
            _unit(1, 0, 0),
            _unit(1, 0, 0),
            _unit(0.2, 1, 0),
            _unit(0.1, 0, 1),
        ]

        ranked = await self.use_case.execute("حذف os.getenv", self.candidates)

        self.assertEqual(ranked[0][0].issue_key, "PARSCHAT-5980")

    async def test_a_flat_field_is_reported_as_no_match(self):
        """Everything scoring alike is what matching nothing looks like."""
        self.embeddings.embed.return_value = [
            _unit(1, 1, 1),
            _unit(1, 1, 0.95),
            _unit(1, 0.98, 1),
            _unit(0.97, 1, 1),
        ]

        ranked = await self.use_case.execute("آشپزی و باغبانی", self.candidates)

        self.assertEqual(ranked, [])

    async def test_low_similarity_is_reported_as_no_match(self):
        self.embeddings.embed.return_value = [
            _unit(1, 0, 0),
            _unit(0.05, 1, 0),
            _unit(0.02, 0, 1),
            _unit(0.01, 1, 1),
        ]

        ranked = await self.use_case.execute("چیز نامربوط", self.candidates)

        self.assertEqual(ranked, [])

    async def test_embedding_failure_leaves_candidates_unranked(self):
        """None means "no ranking", which is not the same as "no match"."""
        self.embeddings.embed.return_value = []

        ranked = await self.use_case.execute("هر چیزی", self.candidates)

        self.assertIsNone(ranked)

    async def test_shortlist_is_capped(self):
        many = [_task(f"PARSCHAT-{i}", f"تسک {i}") for i in range(12)]
        vectors = [_unit(1, 0)] + [
            _unit(1, index * 0.05) for index in range(12)
        ]
        self.embeddings.embed.return_value = vectors

        ranked = await self.use_case.execute("کار", many)

        self.assertLessEqual(len(ranked), EmbeddingSettings().shortlist_size)

    async def test_empty_input_is_not_embedded(self):
        self.assertIsNone(await self.use_case.execute("", self.candidates))
        self.assertIsNone(await self.use_case.execute("کار", []))
        self.embeddings.embed.assert_not_called()

    async def test_the_query_is_embedded_with_the_corpus(self):
        """One call, so the query and issues share a batch."""
        self.embeddings.embed.return_value = [
            _unit(1, 0, 0), _unit(1, 0, 0), _unit(0.1, 1, 0), _unit(0.1, 0, 1),
        ]

        await self.use_case.execute("حذف os.getenv", self.candidates)

        texts = self.embeddings.embed.call_args.args[0]
        self.assertEqual(len(texts), 4)
        self.assertEqual(texts[0], "حذف os.getenv")


if __name__ == "__main__":
    unittest.main()
