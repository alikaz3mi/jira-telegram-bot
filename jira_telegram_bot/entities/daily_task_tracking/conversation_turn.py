"""Short-term memory of what was just said in a chat."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel
from pydantic import Field

# Enough to resolve "only those two?" or "and the first one?" without letting
# an old topic steer a new question.
MAX_TURNS = 6


class ConversationTurn(BaseModel):
    """One exchange: what the user said and what the bot replied."""

    user: str = Field(description="What the user wrote")
    assistant: str = Field(description="What the bot replied, as plain text")


class ConversationMemory(BaseModel):
    """The last few turns of one chat, oldest first."""

    turns: List[ConversationTurn] = Field(default_factory=list)

    def remember(self, user: str, assistant: str) -> None:
        """Record an exchange, dropping the oldest once the window is full.

        Args:
            user: What the user wrote
            assistant: What the bot replied
        """
        self.turns.append(ConversationTurn(user=user, assistant=assistant))
        del self.turns[:-MAX_TURNS]

    def render(self) -> str:
        """Render the history for a prompt, oldest first.

        Returns:
            The transcript, or an empty string when nothing is remembered.
        """
        if not self.turns:
            return ""
        return "\n".join(
            f"user: {turn.user}\nassistant: {turn.assistant}"
            for turn in self.turns
        )
