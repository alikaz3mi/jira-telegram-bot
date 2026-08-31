"""Embedding cache behaviour and the normalisation truncation requires."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from jira_telegram_bot.settings.embedding_settings import EmbeddingSettings


def _response(*vectors):
    return Mock(data=[Mock(embedding=list(v)) for v in vectors])


class TestOpenAIEmbeddingService(unittest.IsolatedAsyncioTestCase):
    """Vectors are cached by content and returned unit-length."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "cache.json"
        self.patcher = patch(
            "jira_telegram_bot.adapters.ai_models.openai_embedding_service"
            ".AsyncOpenAI",
        )
        self.client = self.patcher.start().return_value
        self.client.embeddings.create = AsyncMock()

        from jira_telegram_bot.adapters.ai_models.openai_embedding_service import (
            OpenAIEmbeddingService,
        )
        self.factory = OpenAIEmbeddingService

    def tearDown(self):
        self.patcher.stop()
        self.directory.cleanup()

    def _service(self, **kwargs):
        return self.factory(
            api_key="k",
            settings=EmbeddingSettings(**kwargs),
            cache_path=self.path,
        )

    async def test_vectors_are_normalised(self):
        """Truncated embeddings are not unit length; callers assume they are."""
        self.client.embeddings.create.return_value = _response([3.0, 4.0])

        vectors = await self._service().embed(["متن"])

        self.assertAlmostEqual(sum(v * v for v in vectors[0]) ** 0.5, 1.0, places=6)
        self.assertAlmostEqual(vectors[0][0], 0.6, places=6)

    async def test_repeated_text_is_not_embedded_twice(self):
        self.client.embeddings.create.return_value = _response([1.0, 0.0])
        service = self._service()

        await service.embed(["متن"])
        await service.embed(["متن"])

        self.client.embeddings.create.assert_awaited_once()

    async def test_cache_survives_a_restart(self):
        self.client.embeddings.create.return_value = _response([1.0, 0.0])
        await self._service().embed(["متن"])

        self.client.embeddings.create.reset_mock()
        await self._service().embed(["متن"])

        self.client.embeddings.create.assert_not_awaited()

    async def test_changed_text_is_a_cache_miss(self):
        """An edited summary must not keep its old vector."""
        self.client.embeddings.create.return_value = _response([1.0, 0.0])
        service = self._service()
        await service.embed(["عنوان اول"])

        await service.embed(["عنوان دوم"])

        self.assertEqual(self.client.embeddings.create.await_count, 2)

    async def test_changed_dimensions_invalidate_the_cache(self):
        """A 512-vector cannot answer a request for 256 dimensions."""
        self.client.embeddings.create.return_value = _response([1.0, 0.0])
        await self._service(dimensions=512).embed(["متن"])

        self.client.embeddings.create.reset_mock()
        await self._service(dimensions=256).embed(["متن"])

        self.client.embeddings.create.assert_awaited_once()

    async def test_only_uncached_texts_are_sent(self):
        self.client.embeddings.create.return_value = _response([1.0, 0.0])
        service = self._service()
        await service.embed(["الف"])

        self.client.embeddings.create.reset_mock()
        self.client.embeddings.create.return_value = _response([0.0, 1.0])
        await service.embed(["الف", "ب"])

        sent = self.client.embeddings.create.await_args.kwargs["input"]
        self.assertEqual(sent, ["ب"])

    async def test_api_failure_returns_nothing_rather_than_raising(self):
        """A failed call must leave the caller unranked, not broken."""
        self.client.embeddings.create.side_effect = Exception("429")

        self.assertEqual(await self._service().embed(["متن"]), [])

    async def test_dimensions_are_requested_from_the_api(self):
        self.client.embeddings.create.return_value = _response([1.0, 0.0])

        await self._service(dimensions=512).embed(["متن"])

        kwargs = self.client.embeddings.create.await_args.kwargs
        self.assertEqual(kwargs["dimensions"], 512)

    async def test_an_unreadable_cache_file_is_survivable(self):
        self.path.write_text("{ not json", encoding="utf-8")
        self.client.embeddings.create.return_value = _response([1.0, 0.0])

        vectors = await self._service().embed(["متن"])

        self.assertEqual(len(vectors), 1)

    async def test_empty_input_makes_no_call(self):
        self.assertEqual(await self._service().embed([]), [])
        self.client.embeddings.create.assert_not_awaited()

    async def test_a_zero_vector_does_not_divide_by_zero(self):
        self.client.embeddings.create.return_value = _response([0.0, 0.0])

        self.assertEqual(await self._service().embed(["متن"]), [[0.0, 0.0]])

    async def test_the_cache_is_written_to_disk(self):
        self.client.embeddings.create.return_value = _response([1.0, 0.0])

        await self._service().embed(["متن"])

        self.assertEqual(len(json.loads(self.path.read_text(encoding="utf-8"))), 1)


if __name__ == "__main__":
    unittest.main()
