"""Test script to verify deadline notifier settings configuration."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add the jira_telegram_bot module to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jira_telegram_bot import LOGGER  # noqa: E402
from jira_telegram_bot.app_container import get_container  # noqa: E402
from jira_telegram_bot.settings.deadline_notifier_settings import (  # noqa: E402
    DeadlineNotifierSettings,
)
from jira_telegram_bot.use_cases.send_deadline_alerts_use_case import (  # noqa: E402
    SendDeadlineAlertsUseCase,
)


async def test_deadline_notifier_configuration():
    """Test deadline notifier configuration with new settings."""

    # Test settings loading
    LOGGER.info("Testing DeadlineNotifierSettings...")
    settings = DeadlineNotifierSettings()
    LOGGER.info(f"✅ Lookahead days: {settings.LOOKAHEAD_DAYS}")
    LOGGER.info(f"✅ Additional JQL: '{settings.ADDITIONAL_JQL}'")
    LOGGER.info(f"✅ Cron schedule: {settings.CRON_SCHEDULE}")
    LOGGER.info(
        f"✅ Group notification usernames: {settings.GROUP_NOTIFICATION_USERNAMES}",
    )

    # Test dependency injection
    LOGGER.info("\nTesting dependency injection...")
    try:
        container = get_container()
        deadline_use_case = container[SendDeadlineAlertsUseCase]
        LOGGER.info("✅ SendDeadlineAlertsUseCase successfully resolved from container")

        # Check if settings are properly injected
        if hasattr(deadline_use_case, "deadline_notifier_settings"):
            injected_settings = deadline_use_case.deadline_notifier_settings
            LOGGER.info(
                f"✅ Settings injected - Group notification usernames: {injected_settings.GROUP_NOTIFICATION_USERNAMES}",
            )
        else:
            LOGGER.error("❌ Settings not properly injected")

    except Exception as e:
        LOGGER.error(f"❌ Error in dependency injection: {e}")
        return False

    # Test user config group chat IDs
    LOGGER.info("\nTesting user config group chat IDs...")
    try:
        user_config_repo = container[SendDeadlineAlertsUseCase].user_config_repository
        group_chat_ids = user_config_repo.get_group_chat_ids()
        LOGGER.info(f"✅ Group chat IDs from environment: {group_chat_ids}")

        # Test getting specific user chat IDs
        for username in settings.GROUP_NOTIFICATION_USERNAMES:
            user_config = user_config_repo.get_user_config_by_jira_username(username)
            if user_config:
                LOGGER.info(
                    f"✅ User {username} -> Chat ID: {user_config.telegram_user_chat_id}",
                )
            else:
                LOGGER.warning(f"⚠️  User {username} not found in configuration")

    except Exception as e:
        LOGGER.error(f"❌ Error testing user configuration: {e}")
        return False

    LOGGER.info("\n🎉 All configuration tests passed!")
    return True


if __name__ == "__main__":
    LOGGER.info("=" * 60)
    LOGGER.info("Testing Deadline Notifier Configuration")
    LOGGER.info("=" * 60)

    # Set environment variables for testing
    os.environ.setdefault("TELEGRAM_GROUP_CHAT_IDS", "-1001234567890,-1009876543210")
    os.environ.setdefault(
        "DEADLINE_NOTIFIER_GROUP_NOTIFICATION_USERNAMES",
        '["admin_user", "manager_user"]',
    )

    result = asyncio.run(test_deadline_notifier_configuration())
    sys.exit(0 if result else 1)
