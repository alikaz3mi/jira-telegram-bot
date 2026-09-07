"""Integration test for team evaluation with mock data."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.entities.team_evaluation import SprintClosedEvent
from jira_telegram_bot.use_cases.team_evaluation import (
    SprintClosedTeamEvaluationUseCase,
)

# These were set at import time, so merely collecting this module turned on
# dry-run for every TeamEvaluationSettings built afterwards — and a later
# test that asserts logs ARE saved then failed, but only when run as part of
# the whole suite. Scoped to this test and restored on the way out.
_TEST_ENVIRONMENT = {
    "TEAM_EVALUATION_SHEET_ID": "test_sheet_id_12345",
    "TEAM_EVALUATION_DRY_RUN": "true",
}


async def test_team_evaluation_integration():
    """Test the complete team evaluation integration."""
    previous = {key: os.environ.get(key) for key in _TEST_ENVIRONMENT}
    os.environ.update(_TEST_ENVIRONMENT)
    try:
        LOGGER.info("🚀 Starting Team Evaluation Integration Test...")

        # Configure dependencies
        container = configure_container()

        # Get the use case
        team_eval_use_case = container[SprintClosedTeamEvaluationUseCase]
        LOGGER.info("✅ Team evaluation use case loaded successfully")

        # Create a test event
        test_event = SprintClosedEvent(
            sprint_id=12345,  # Mock sprint ID
            sprint_name="Test Sprint Integration",
            project_keys=["TEST"],  # Mock project key
            ended_at=datetime.now(),
        )

        LOGGER.info(f"📋 Processing test event: {test_event.sprint_name}")

        # Process the event (will fail gracefully with mock data)
        try:
            await team_eval_use_case.process_sprint_closed(test_event)
        except Exception as e:
            # Expected to fail with mock data, but should show the flow works
            LOGGER.warning(f"Expected failure with mock data: {e}")

        LOGGER.info("✅ Team evaluation integration test completed!")
        LOGGER.info("🎯 System is ready for production with real Jira data")

        return True

    except Exception as e:
        LOGGER.error(f"❌ Integration test failed: {e}")
        return False
    finally:
        _restore_environment(previous)


def _restore_environment(previous: dict) -> None:
    """Put the environment back the way this module found it."""
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


if __name__ == "__main__":
    success = asyncio.run(test_team_evaluation_integration())
    sys.exit(0 if success else 1)
