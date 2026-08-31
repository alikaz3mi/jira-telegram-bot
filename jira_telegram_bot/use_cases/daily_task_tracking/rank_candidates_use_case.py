"""Rank a person's issues against what they said they worked on.

Handing a model twenty issues and asking which one a sentence means is a
question it answers inconsistently: the same message returned one candidate
on one run and all twenty on the next. Ranking by embedding similarity is
deterministic, so the model is asked a smaller and better-posed question —
pick from these five — and a message that matches nothing can be recognised
as matching nothing instead of being answered with an arbitrary list.
"""
from __future__ import annotations

from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.settings.embedding_settings import EmbeddingSettings


class RankCandidatesUseCase:
    """Orders issues by how closely they match a description of work."""

    def __init__(
        self,
        embedding_service,
        settings: EmbeddingSettings = None,
    ):
        """Initialize the use case.

        Args:
            embedding_service: Turns text into unit-length vectors
            settings: Shortlist size and the similarity floor
        """
        self.embeddings = embedding_service
        self.settings = settings or EmbeddingSettings()

    async def execute(
        self,
        text: str,
        candidates: Sequence[DailyTaskCheck],
    ) -> Optional[List[Tuple[DailyTaskCheck, float]]]:
        """Rank candidates by similarity to the described work.

        Args:
            text: What the user said they did
            candidates: The issues they could have worked on

        Returns:
            The best candidates with their similarity, highest first, or
            None when ranking was unavailable — which tells the caller to
            keep its existing unranked behaviour rather than show nothing.
        """
        if not text.strip() or not candidates:
            return None

        vectors = await self.embeddings.embed(
            [text] + [self._describe(task) for task in candidates],
        )
        if len(vectors) != len(candidates) + 1:
            LOGGER.info("Embeddings unavailable; leaving candidates unranked")
            return None

        query, corpus = vectors[0], vectors[1:]
        scored = [
            (task, self._similarity(query, vector))
            for task, vector in zip(candidates, corpus)
        ]
        scored.sort(key=lambda pair: -pair[1])

        best = scored[0][1]
        if best < self.settings.min_similarity:
            LOGGER.info(
                f"Best match scored {best:.3f}, below "
                f"{self.settings.min_similarity}; reporting no match",
            )
            return []

        runner_up = scored[1][1] if len(scored) > 1 else 0.0
        margin = best - runner_up
        if margin < self.settings.min_margin:
            # Everything scored about the same, which is what a description
            # matching nothing looks like: the top row is the winner of a
            # tie, not an answer. Handing it over as a shortlist invites a
            # confident pick from rows that are all equally unrelated.
            LOGGER.info(
                f"Best {scored[0][0].issue_key} at {best:.3f} leads by only "
                f"{margin:.3f}; reporting no match",
            )
            return []

        shortlist = [
            pair for pair in scored[: self.settings.shortlist_size]
            if pair[1] >= self.settings.min_similarity
        ]
        LOGGER.info(
            f"Ranked {len(candidates)} candidates to {len(shortlist)}; "
            f"best {shortlist[0][0].issue_key} at {best:.3f}",
        )
        return shortlist

    @staticmethod
    def _describe(task: DailyTaskCheck) -> str:
        """Render an issue as the text it is matched on."""
        parts = [task.summary or ""]
        if task.description:
            parts.append(" ".join(task.description.split())[:300])
        return " ".join(part for part in parts if part).strip() or task.issue_key

    @staticmethod
    def _similarity(left: Sequence[float], right: Sequence[float]) -> float:
        """Cosine similarity of two unit-length vectors."""
        return sum(a * b for a, b in zip(left, right))
