"""Who is asking, and what they are allowed to see.

Identity is bound here, outside the model. The agent never receives a
username it can choose to change: a tool reads the caller from this context
and decides authorisation in Python, so no prompt can talk the assistant
into reading somebody else's work.
"""
from __future__ import annotations

from dataclasses import dataclass

from jira_telegram_bot.entities.assistant_entities import UserRole


@dataclass
class AssistantContext:
    """The caller's identity for one request."""

    jira_username: str
    telegram_username: str
    role: UserRole = UserRole.MEMBER

    def may_read(self, target_jira_username: str) -> bool:
        """Whether this caller may read the target's tasks.

        Args:
            target_jira_username: Whose work is being asked about

        Returns:
            True for their own work always, or anyone's when the role allows.
        """
        if target_jira_username.lower() == self.jira_username.lower():
            return True
        return self.role.may_read_others
