#!/usr/bin/env python3
"""Test script for the API-based calendar repository."""
from __future__ import annotations

import asyncio
import sys

# Add project root to path
sys.path.insert(0, "/home/ali/projects/Radtharn/jira-telegram-bot")

from jira_telegram_bot import LOGGER  # noqa: E402
from jira_telegram_bot.adapters.repositories.calendar.api_calendar_repository import (  # noqa: E402
    ApiCalendarRepository,
)


async def test_api_calendar():
    """Test the API calendar repository."""
    LOGGER.info("🧪 Testing API Calendar Repository...")

    # Create repository instance
    repo = ApiCalendarRepository()

    # Test getting holidays for current year
    current_year = 2024
    LOGGER.info(f"📅 Getting holidays for {current_year}...")

    try:
        holidays = await repo.get_holidays(current_year)
        LOGGER.info(f"✅ Found {len(holidays)} holidays")

        # Show first few holidays
        sorted_holidays = sorted(holidays)
        for i, holiday in enumerate(sorted_holidays[:5]):
            LOGGER.info(f"   {i+1}. {holiday}")

        if len(sorted_holidays) > 5:
            LOGGER.info(f"   ... and {len(sorted_holidays) - 5} more")

    except Exception as e:
        LOGGER.error(f"❌ Error: {e}")
        return False

    # Test disabled days
    LOGGER.info(f"\n📅 Getting disabled days for {current_year}...")
    try:
        disabled_days = await repo.get_disabled_days(current_year)
        LOGGER.info(
            f"ℹ️  Found {len(disabled_days)} disabled days (expected to be 0 for API implementation)",
        )

    except Exception as e:
        LOGGER.error(f"❌ Error getting disabled days: {e}")
        return False

    # Test calendar header
    LOGGER.info(f"\n📅 Getting calendar header for {current_year}/1...")
    try:
        header = await repo.get_calendar_header(current_year, 1)
        LOGGER.info(f"✅ Calendar header: {header}")

    except Exception as e:
        LOGGER.error(f"❌ Error getting calendar header: {e}")
        return False

    LOGGER.info("\n🎉 All tests passed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_api_calendar())
    sys.exit(0 if success else 1)
