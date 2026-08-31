"""OpenAI-backed embeddings with an on-disk cache.

Issue summaries change rarely and a person logs time daily, so embedding
the same issues on every message would be paid for many times over. The
cache is keyed on a hash of the text, which makes an edited summary a miss
and an unchanged one a hit without any explicit invalidation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict
from typing import List
from typing import Sequence

from openai import AsyncOpenAI

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.embedding_settings import EmbeddingSettings


class OpenAIEmbeddingService:
    """Embeds text through OpenAI, caching vectors by content hash."""

    def __init__(
        self,
        api_key: str,
        settings: EmbeddingSettings = None,
        cache_path: Path = None,
    ):
        """Initialize the service.

        Args:
            api_key: OpenAI API key
            settings: Model, vector size and thresholds
            cache_path: Where vectors are cached; defaults under the data
                directory beside the other file-backed state
        """
        self.settings = settings or EmbeddingSettings()
        self.client = AsyncOpenAI(api_key=api_key)
        self._path = cache_path or (DEFAULT_PATH / "data" / "embedding_cache.json")
        self._cache: Dict[str, List[float]] = {}
        self._load()

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed texts, calling OpenAI only for the ones not already cached.

        Args:
            texts: The texts to embed, in order

        Returns:
            One unit-length vector per text, or an empty list if the call
            failed. Callers treat an empty result as "no ranking available"
            rather than as an error.
        """
        if not texts:
            return []

        keys = [self._key(text) for text in texts]
        missing = [
            text for text, key in zip(texts, keys) if key not in self._cache
        ]

        if missing:
            fetched = await self._fetch(list(dict.fromkeys(missing)))
            if not fetched:
                return []
            self._save()

        try:
            return [self._cache[key] for key in keys]
        except KeyError:
            LOGGER.error("Embedding cache miss after fetch; skipping ranking")
            return []

    async def _fetch(self, texts: List[str]) -> bool:
        """Embed uncached texts and store them.

        Args:
            texts: Distinct texts with no cached vector

        Returns:
            Whether the call succeeded.
        """
        try:
            response = await self.client.embeddings.create(
                model=self.settings.model,
                input=texts,
                dimensions=self.settings.dimensions,
            )
        except Exception as exc:
            LOGGER.error(f"Embedding call failed for {len(texts)} texts: {exc}")
            return False

        for text, item in zip(texts, response.data):
            self._cache[self._key(text)] = self._normalise(item.embedding)
        LOGGER.info(f"Embedded {len(texts)} new texts")
        return True

    @staticmethod
    def _normalise(vector: Sequence[float]) -> List[float]:
        """Scale a vector to unit length.

        Truncated embeddings are not unit length, and OpenAI's guidance is
        to normalise after shortening. Doing it here means every caller can
        treat a dot product as cosine similarity.

        Args:
            vector: The raw embedding

        Returns:
            The vector scaled to length 1, or unchanged when it is all zeros.
        """
        magnitude = sum(value * value for value in vector) ** 0.5
        if magnitude == 0:
            return list(vector)
        return [value / magnitude for value in vector]

    def _key(self, text: str) -> str:
        """Hash text with the settings that determine its vector."""
        payload = f"{self.settings.model}:{self.settings.dimensions}:{text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load(self) -> None:
        """Read cached vectors, tolerating absence on a first run."""
        if not self._path.exists():
            return
        try:
            self._cache = json.loads(self._path.read_text(encoding="utf-8"))
            LOGGER.info(f"Loaded {len(self._cache)} cached embeddings")
        except Exception as exc:
            LOGGER.error(f"Could not read embedding cache: {exc}")

    def _save(self) -> None:
        """Write cached vectors, tolerating a read-only data directory."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._cache), encoding="utf-8",
            )
        except Exception as exc:
            LOGGER.error(f"Could not write embedding cache: {exc}")
