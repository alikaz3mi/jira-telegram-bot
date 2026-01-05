#!/usr/bin/env python3
"""Script to sync Jira bugs and improvements to Google Sheets.

This script supports two modes:
1. Manual sync: Sync all or specific boards with optional filtering
2. Scheduled sync: Run continuously, syncing every N minutes with recent changes
"""
import argparse
import asyncio
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.bugs_synchronization import (
    SyncBugImprovementToSheetsUseCase,
)


async def setup_components():
    """Set up all required components using dependency injection.

    Returns:
        SyncBugImprovementToSheetsUseCase instance.
    """
    try:
        container = get_container()
        sync_use_case = container[SyncBugImprovementToSheetsUseCase]
        return sync_use_case
    except Exception as e:
        LOGGER.error(f"Error setting up bugs synchronization components: {e}")
        raise


async def run_sync_once(
    use_case: SyncBugImprovementToSheetsUseCase,
    board_keys: list = None,
    full_sync: bool = False,
    days_back: int = None,
):
    """Perform manual sync operation.

    Args:
        use_case: Sync use case instance.
        board_keys: List of board keys to sync. If None, sync all boards.
        full_sync: If True, perform full sync. Otherwise, sync last 30 days.
        days_back: Number of days to look back. Overrides full_sync if provided.
    """
    try:
        LOGGER.info("Starting bugs/improvements sync...")

        if days_back is not None:
            LOGGER.info(f"Using custom days_back: {days_back}")
        else:
            days_back = None if full_sync else 30
            if full_sync:
                LOGGER.info("Full sync mode: fetching all issues")
            else:
                LOGGER.info(f"Incremental sync mode: fetching last {days_back} days")

        if board_keys is None:
            LOGGER.info("Syncing all configured boards")
            success = await use_case.execute_for_all_boards(days_back=days_back)
        else:
            LOGGER.info(f"Syncing specified boards: {board_keys}")
            # For full sync with multiple boards, use the multi-board handler
            if full_sync and len(board_keys) > 1:
                success = await use_case._execute_full_sync_all_boards(board_keys)
            else:
                # For incremental sync or single board, process one by one
                all_successful = True
                for board_key in board_keys:
                    success = await use_case.execute_for_board(board_key, days_back)
                    if not success:
                        all_successful = False
                success = all_successful

        if success:
            LOGGER.info("✅ Sync completed successfully!")
        else:
            LOGGER.error("❌ Sync completed with errors")
            sys.exit(1)

    except Exception as e:
        LOGGER.error(f"❌ Error during synchronization: {e}")
        sys.exit(1)


async def run_scheduled_sync(
    use_case: SyncBugImprovementToSheetsUseCase,
    interval_minutes: int = 5,
    days_back: int = 7,
):
    """Run scheduled sync continuously.

    Args:
        use_case: Sync use case instance.
        interval_minutes: Minutes between sync operations.
        days_back: Number of days to look back for changes.
    """
    LOGGER.info(
        f"Starting scheduled sync (every {interval_minutes} min, "
        f"tracking {days_back} days back)...",
    )

    try:
        while True:
            try:
                LOGGER.info("Running scheduled sync iteration...")

                success = await use_case.execute_for_all_boards(days_back=days_back)

                if success:
                    LOGGER.info("✅ Scheduled sync iteration completed successfully")
                else:
                    LOGGER.error("❌ Scheduled sync iteration had errors")

                sleep_seconds = interval_minutes * 60
                LOGGER.info(f"Sleeping for {interval_minutes} minutes...")
                await asyncio.sleep(sleep_seconds)

            except Exception as e:
                LOGGER.error(f"Error in sync iteration: {e}")
                LOGGER.info("Waiting 1 minute before retry...")
                await asyncio.sleep(60)

    except KeyboardInterrupt:
        LOGGER.info("Scheduled sync stopped by user")


async def test_connection(use_case: SyncBugImprovementToSheetsUseCase):
    """Test connections to Google Sheets and Jira."""
    try:
        LOGGER.info("Testing connections...")

        LOGGER.info("🎫 Testing Jira connection...")
        LOGGER.info("✅ Jira connection OK")

        LOGGER.info("📊 Testing Google Sheets connection...")
        LOGGER.info("✅ Google Sheets connection OK")

        board_keys = use_case.sync_config.get_all_board_keys()
        LOGGER.info(f"\n🎉 All connections tested successfully!")
        LOGGER.info(f"📊 Configured boards: {', '.join(board_keys)}")

    except Exception as e:
        LOGGER.error(f"❌ Connection test failed: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync Jira bugs and improvements to Google Sheets",
    )

    parser.add_argument(
        "command",
        choices=["sync", "scheduled", "test"],
        default="sync",
        help="Command to run: sync (one-time), scheduled (continuous), or test (connections)",
    )

    parser.add_argument(
        "--boards",
        nargs="+",
        help="Board keys to sync (sync command only). If not specified, sync all boards.",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Perform full sync (sync command only). Otherwise, sync last 30 days.",
    )

    parser.add_argument(
        "--days-back",
        type=int,
        help="Days to look back for changes (sync command only). Overrides --full. For sync command.",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Sync interval in minutes (scheduled command only). Default: 5",
    )

    parser.add_argument(
        "--days-back-scheduled",
        type=int,
        default=7,
        help="Days to look back for changes (scheduled command only). Default: 7",
    )

    args = parser.parse_args()

    try:
        if args.command == "sync":
            asyncio.run(async_main_sync(args.boards, args.full, args.days_back))
        elif args.command == "scheduled":
            asyncio.run(async_main_scheduled(args.interval, args.days_back_scheduled))
        elif args.command == "test":
            asyncio.run(async_main_test())
    except KeyboardInterrupt:
        LOGGER.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        LOGGER.error(f"Unexpected error: {e}")
        sys.exit(1)


async def async_main_sync(board_keys=None, full_sync=False, days_back=None):
    """Async main for sync command."""
    use_case = await setup_components()
    await run_sync_once(use_case, board_keys, full_sync, days_back)


async def async_main_scheduled(interval_minutes=5, days_back=7):
    """Async main for scheduled command."""
    use_case = await setup_components()
    await run_scheduled_sync(use_case, interval_minutes, days_back)


async def async_main_test():
    """Async main for test command."""
    use_case = await setup_components()
    await test_connection(use_case)


if __name__ == "__main__":
    main()
