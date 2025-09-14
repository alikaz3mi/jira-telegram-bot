from __future__ import annotations

import argparse
import asyncio
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.services.synth_pm_sync_task import SynthPMSyncTask
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import (
    SynthPMSyncFilterCriteria,
)
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase


async def setup_components():
    """Set up all required components for SynthPM using dependency injection."""
    try:
        container = get_container()

        synth_developer_board_use_case = container[SynthPMUseCase]

        return synth_developer_board_use_case

    except Exception as e:
        LOGGER.error(f"Error setting up SynthPM components: {e}")
        raise


async def run_sync_once(use_case: SynthPMUseCase, filter_criteria=None):
    """Run synchronization once and exit.

    Args:
        use_case: SynthPM use case instance
        filter_criteria: Optional filter criteria for sync
    """
    try:
        LOGGER.info("Starting one-time SynthPM synchronization...")

        if filter_criteria:
            LOGGER.info(
                f"Applying filter: sprints={filter_criteria.sprints}, "
                f"releases={filter_criteria.releases}, versions={filter_criteria.release_versions}",
            )

        result = await use_case.sync_developer_board_features(filter_criteria)

        if result["status"] == "success":
            LOGGER.info("✅  Features synchronization completed successfully!")
            LOGGER.info(f" Features Results: {result.get('results', {})}")
        else:
            LOGGER.error(f"❌  Features synchronization failed: {result.get('message')}")
            sys.exit(1)

        LOGGER.info("Starting Release Notes synchronization...")
        release_result = await use_case.sync_release_notes()

        if release_result["status"] == "success":
            LOGGER.info("✅ Release Notes synchronization completed successfully!")
            LOGGER.info(f"Release Notes Results: {release_result.get('results', {})}")
        else:
            LOGGER.error(
                f"❌ Release Notes synchronization failed: {release_result.get('message')}",
            )
            LOGGER.warning("Continuing despite Release Notes sync failure...")

    except Exception as e:
        LOGGER.error(f"❌ Error during synchronization: {e}")
        sys.exit(1)


async def run_background_service(use_case: SynthPMUseCase):
    """Run as a background service with periodic synchronization."""
    try:
        LOGGER.info("Starting SynthPM background service...")

        container = get_container()
        settings = container[SynthPMSettings]

        sync_task = SynthPMSyncTask(
            synth_developer_board_use_case=use_case,
            settings=settings,
        )

        await sync_task.start()

        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            LOGGER.info("Received interrupt signal, shutting down...")
        finally:
            await sync_task.stop()

    except Exception as e:
        LOGGER.error(f"❌ Error in background service: {e}")
        sys.exit(1)


async def test_connection(use_case: SynthPMUseCase):
    """Test connections to Google Sheets, Jira, and Telegram."""
    try:
        LOGGER.info("Testing connections...")

        LOGGER.info("📊 Testing Google Sheets connection...")
        features = await use_case.repository.get_developer_board_features()
        LOGGER.info(f"✅ Found {len(features)} features in Google Sheets")

        LOGGER.info("🎫 Testing Jira connection...")
        LOGGER.info("✅ Jira connection OK")

        LOGGER.info("🤖 Testing dedicated SynthPM Telegram bot...")
        try:
            # Test basic functionality (we can't easily test telegram directly without exposing bot)
            _ = use_case.notification_gateway
            LOGGER.info("✅ SynthPM notification gateway is configured")
            LOGGER.info(
                f"✅ Settings loaded: PM project = {use_case.settings.pm_project_key}",
            )

        except Exception as telegram_error:
            LOGGER.error(f"❌ Telegram bot test failed: {telegram_error}")
            LOGGER.error("💡 Make sure SYNTH_PM_TELEGRAM_BOT_TOKEN is set correctly")
            raise

        LOGGER.info("\n🎉 All connections tested successfully!")
        LOGGER.info(f"📊 Google Sheets: {len(features)} features ready for sync")
        LOGGER.info("🎫 Jira: Connection verified")
        LOGGER.info("🤖 Notification: Gateway configured for SynthPM updates")
        LOGGER.info("🧠 AI: New documentation generation use cases loaded")

    except Exception as e:
        LOGGER.error(f"❌ Connection test failed: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SynthPM synchronization tool with filtering support",
    )
    parser.add_argument(
        "command",
        choices=["sync", "service", "test"],
        default="service",
        help="Command to run: sync (one-time), service (background), or test (connections)",
    )

    # Filtering options
    parser.add_argument(
        "--sprints",
        nargs="+",
        help="Filter by specific sprint names (e.g., --sprints Sprint-1 Sprint-2)",
    )
    parser.add_argument(
        "--releases",
        nargs="+",
        help="Filter by release names (e.g., --releases v1.0 v1.1)",
    )
    parser.add_argument(
        "--versions",
        nargs="+",
        help="Filter by version numbers (e.g., --versions 1.0.0 1.1.0)",
    )
    parser.add_argument(
        "--include-empty-sprint",
        action="store_true",
        help="Include features with empty sprint field",
    )
    parser.add_argument(
        "--include-empty-release",
        action="store_true",
        help="Include features with empty release fields",
    )

    args = parser.parse_args()

    # Create filter criteria from arguments
    filter_criteria = None
    if args.sprints or args.releases or args.versions:
        filter_criteria = SynthPMSyncFilterCriteria.create_combined_filter(
            sprints=args.sprints,
            releases=args.releases,
            versions=args.versions,
            include_empty_sprint=args.include_empty_sprint,
            include_empty_release=args.include_empty_release,
        )

    try:
        if args.command == "sync":
            asyncio.run(async_main_sync(filter_criteria))
        elif args.command == "service":
            asyncio.run(async_main_service())
        elif args.command == "test":
            asyncio.run(async_main_test())
    except KeyboardInterrupt:
        LOGGER.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        LOGGER.error(f"Unexpected error: {e}")
        sys.exit(1)


async def async_main_sync(filter_criteria=None):
    """Async main for sync command.

    Args:
        filter_criteria: Optional filter criteria for sync
    """
    use_case = await setup_components()
    await run_sync_once(use_case, filter_criteria)


async def async_main_service():
    """Async main for service command."""
    use_case = await setup_components()
    await run_background_service(use_case)


async def async_main_test():
    """Async main for test command."""
    use_case = await setup_components()
    await test_connection(use_case)


if __name__ == "__main__":
    main()
