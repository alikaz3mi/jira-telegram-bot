"""Use case for deciding what a free-text message is asking for."""
from __future__ import annotations

from enum import Enum

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    AIServiceProtocol,
)
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import (
    PromptCatalogProtocol,
)

_PROMPT_TASK = "classify_message_intent"


class MessageIntent(str, Enum):
    """What a team member's message is for."""

    WORKLOG = "worklog"
    QUESTION = "question"
    CHITCHAT = "chitchat"


class ClassifyMessageIntentUseCase:
    """Route a free-text message to the flow that can actually serve it.

    Without this every message is read as a work report, so asking "which
    tasks do I deliver this week?" answers with "I didn't understand how many
    hours you spent" — which is both wrong and confusing. Classification is
    one cheap call on a small model before any of the expensive work.
    """

    def __init__(
        self,
        ai_service: AIServiceProtocol,
        prompt_catalog: PromptCatalogProtocol,
    ):
        """Initialize the use case.

        Args:
            ai_service: Service that runs the structured LLM call
            prompt_catalog: Catalog the classification prompt is loaded from
        """
        self.ai_service = ai_service
        self.prompt_catalog = prompt_catalog

    async def execute(self, text: str, history: str = "") -> MessageIntent:
        """Classify one message.

        Args:
            text: The user's message
            history: Recent turns, so a fragment is read as the follow-up it is

        Returns:
            The intent; falls back to ``CHITCHAT`` when unclear, because
            doing nothing is safer than logging time nobody asked to log.
        """
        if not text or not text.strip():
            return MessageIntent.CHITCHAT

        try:
            prompt = await self.prompt_catalog.get_prompt(_PROMPT_TASK)
            result = await self.ai_service.run(
                prompt, {"content": text, "history": history},
            )
            raw = str(result.get("intent", "")).strip().lower()
            return MessageIntent(raw)
        except ValueError:
            LOGGER.warning(f"Unrecognised intent {raw!r}; treating as chitchat")
            return MessageIntent.CHITCHAT
        except Exception as exc:
            LOGGER.error(f"Failed to classify message intent: {exc}")
            return MessageIntent.CHITCHAT
