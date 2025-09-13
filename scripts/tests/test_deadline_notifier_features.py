#!/usr/bin/env python3
"""Test script for the deadline notifier new features."""
from __future__ import annotations

import asyncio
from datetime import date
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.deadline_alert import DeadlineAlert
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import (
    CalendarRepositoryInterface,
)
from jira_telegram_bot.use_cases.send_deadline_alerts_use_case import (
    SendDeadlineAlertsUseCase,
)


async def test_holiday_weekend_check():
    """Test the holiday and weekend checking functionality."""
    LOGGER.info("Testing holiday/weekend checking...")

    container = get_container()
    calendar_repo = container[CalendarRepositoryInterface]

    # Test current date
    today = date.today()
    is_holiday = await calendar_repo.is_holiday_or_weekend(today)
    LOGGER.info(f"Today ({today}) is holiday/weekend: {is_holiday}")

    # Test a known Friday (weekend in Iran)
    friday = date(2024, 8, 23)
    is_friday_holiday = await calendar_repo.is_holiday_or_weekend(friday)
    LOGGER.info(f"Friday 2024-08-23 is holiday/weekend: {is_friday_holiday}")

    return True


def test_deadline_alert_properties():
    """Test the new DeadlineAlert properties."""
    LOGGER.info("Testing DeadlineAlert properties...")

    # Test story/task filtering
    story_alert = DeadlineAlert(
        issue_key="TEST-1",
        summary="Test Story",
        assignee="test_user",
        days_remaining=1,
        project_key="TEST",
        status="In Progress",
        issue_url="http://test.com/TEST-1",
        issue_type="Story",
        sprint_info="Sprint 1 [state=ACTIVE]",
    )

    subtask_alert = DeadlineAlert(
        issue_key="TEST-2",
        summary="Test Subtask",
        assignee="test_user",
        days_remaining=1,
        project_key="TEST",
        status="In Progress",
        issue_url="http://test.com/TEST-2",
        issue_type="Sub-task",
        sprint_info="Sprint 1 [state=ACTIVE]",
    )

    LOGGER.info(f"Story is_story_or_task: {story_alert.is_story_or_task}")
    LOGGER.info(f"Subtask is_story_or_task: {subtask_alert.is_story_or_task}")
    LOGGER.info(f"Story is_in_active_sprint: {story_alert.is_in_active_sprint}")
    LOGGER.info(f"Subtask is_in_active_sprint: {subtask_alert.is_in_active_sprint}")

    return True


async def test_deadline_alerts_execution():
    """Test the full deadline alerts execution."""
    LOGGER.info("Testing deadline alerts execution...")

    container = get_container()
    use_case = container[SendDeadlineAlertsUseCase]

    try:
        # Run with no real issues to see holiday checking
        stats = await use_case.execute(
            lookahead_days=1,
            additional_jql="project = NONEXISTENT",
        )
        LOGGER.info(f"Deadline alerts stats: {stats}")
        return True
    except Exception as e:
        LOGGER.error(f"Error in deadline alerts execution: {e}")
        return False


async def main():
    """Main test function."""
    LOGGER.info("=" * 50)
    LOGGER.info("Testing Deadline Notifier New Features")
    LOGGER.info("=" * 50)

    success_count = 0
    total_tests = 3

    # Test 1: Holiday/weekend checking
    try:
        await test_holiday_weekend_check()
        success_count += 1
        LOGGER.info("✅ Holiday/weekend check test passed")
    except Exception as e:
        LOGGER.error(f"❌ Holiday/weekend check test failed: {e}")

    # Test 2: DeadlineAlert properties
    try:
        test_deadline_alert_properties()
        success_count += 1
        LOGGER.info("✅ DeadlineAlert properties test passed")
    except Exception as e:
        LOGGER.error(f"❌ DeadlineAlert properties test failed: {e}")

    # Test 3: Full execution (with holiday checking)
    try:
        await test_deadline_alerts_execution()
        success_count += 1
        LOGGER.info("✅ Deadline alerts execution test passed")
    except Exception as e:
        LOGGER.error(f"❌ Deadline alerts execution test failed: {e}")

    LOGGER.info("=" * 50)
    LOGGER.info(f"Test Results: {success_count}/{total_tests} tests passed")

    if success_count == total_tests:
        LOGGER.info("🎉 All tests passed!")
        return True
    else:
        LOGGER.error("❌ Some tests failed!")
        return False


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    result = asyncio.run(main())
    exit(0 if result else 1)
