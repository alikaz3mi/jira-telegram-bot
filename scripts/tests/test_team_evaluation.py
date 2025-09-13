#!/usr/bin/env python3
"""Script to test team evaluation functionality."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.team_evaluation import SprintClosedEvent
from jira_telegram_bot.use_cases.team_evaluation import (
    SprintClosedTeamEvaluationUseCase,
)


async def test_team_evaluation():
    """Test the team evaluation functionality."""
    try:
        # Configure dependencies
        container = get_container()

        # Get the use case
        team_eval_use_case = container[SprintClosedTeamEvaluationUseCase]

        # Create a test event - replace with actual sprint data
        test_event = SprintClosedEvent(
            sprint_id=123,  # Replace with actual sprint ID
            sprint_name="PARSCHAT Sprint 47",
            project_keys=["PARSCHAT"],  # Replace with actual project keys
            ended_at=datetime.now(),
        )

        LOGGER.info("Starting team evaluation test...")

        # Process the event
        await team_eval_use_case.process_sprint_closed(test_event)

        LOGGER.info("Team evaluation test completed successfully!")

    except Exception as e:
        LOGGER.error(f"Team evaluation test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_team_evaluation())
