"""Port for turning text into vectors."""
from __future__ import annotations

from typing import List
from typing import Protocol
from typing import Sequence


class EmbeddingServiceProtocol(Protocol):
    """Embeds text so issues can be ranked by meaning rather than wording."""

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts.

        Args:
            texts: The texts to embed, in order

        Returns:
            One unit-length vector per text, in the same order. An empty
            list when the texts could not be embedded — callers fall back
            to their unranked behaviour rather than failing.
        """
        ...
