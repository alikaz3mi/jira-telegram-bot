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

    async def test_a_flat_field_of_weak_scores_is_no_match(self):
        """Everything scoring alike AND badly is what nothing looks like.

        Measured on real text, a genuine non-match peaks around 0.38. These
        vectors reproduce that: a tie between rows none of which is any good.
        """
        self.embeddings.embed.return_value = [
            _unit(1, 0, 0),
            _unit(0.40, 1, 0),
            _unit(0.38, 0, 1),
            _unit(0.37, 1, 1),
        ]

        ranked = await self.use_case.execute("آشپزی و باغبانی", self.candidates)

        self.assertEqual(ranked, [])

    async def test_a_tie_between_plausible_issues_becomes_a_question(self):
        """Several issues that all fit is not the same as nothing fitting.

        Reproduces a real report: the leader scored 0.496 and led by 0.055,
        which the margin gate refused outright — so work the user had really
        done went unrecorded, and they were asked to type an issue key.
        """
        self.embeddings.embed.return_value = [
            _unit(1, 0, 0),
            _unit(0.496, 1, 0),
            _unit(0.441, 0, 1),
            _unit(0.300, 1, 1),
        ]

        ranked = await self.use_case.execute("توضیح تسک‌ها به تیم", self.candidates)

        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0][0].issue_key, "PARSCHAT-5980")

    async def test_a_candidate_far_behind_does_not_join_the_question(self):
        """Padding the options makes the choice harder, not easier."""
        self.embeddings.embed.return_value = [
            _unit(1, 0, 0),
            _unit(0.50, 1, 0),
            _unit(0.46, 0, 1),
            _unit(0.20, 1, 1),
        ]

        ranked = await self.use_case.execute("کار", self.candidates)

        self.assertNotIn(
            "PARSCHAT-5830", [task.issue_key for task, _ in ranked],
        )

    async def test_a_weak_tie_is_still_refused(self):
        """The tie is only worth asking about when the rows are plausible."""
        self.embeddings.embed.return_value = [
            _unit(1, 0, 0),
            _unit(0.30, 1, 0),
            _unit(0.28, 0, 1),
            _unit(0.27, 1, 1),
        ]

        ranked = await self.use_case.execute("چیز نامربوط", self.candidates)

        self.assertEqual(ranked, [])

    async def test_the_question_is_capped_to_a_readable_size(self):
        many = [_task(f"PARSCHAT-{i}", f"تسک {i}") for i in range(10)]
        self.embeddings.embed.return_value = [_unit(1, 0)] + [
            _unit(0.50 - index * 0.002, 1) for index in range(10)
        ]

        ranked = await self.use_case.execute("کار", many)

        self.assertLessEqual(
            len(ranked), EmbeddingSettings().max_ambiguous_options,
        )

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
