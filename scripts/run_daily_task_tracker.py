"""Entry point script for daily task tracker service.

This script runs the daily task tracker as a scheduled service that:
- Checks users' tasks daily at configured time
- Asks for delay reasons if tasks haven't started
- Asks for time spent on in-progress tasks
- Validates worklogs for completed tasks
- Detects status regressions (Review → Backlog)
- Sends notifications in Persian

Usage:
    python run_daily_task_tracker.py [--once]

Arguments:
    --once: Run once and exit (for testing)

Environment Variables:
    DAILY_TASK_TRACKER_ENABLED: Enable/disable tracker (default: true)
    DAILY_TASK_TRACKER_CRON_SCHEDULE: Cron schedule (default: "0 9 * * *")
    DAILY_TASK_TRACKER_TIMEZONE: Timezone (default: "Asia/Tehran")
    DAILY_TASK_TRACKER_EXCLUDE_WEEKENDS: Skip weekends (default: true)
    DAILY_TASK_TRACKER_EXCLUDE_HOLIDAYS: Skip holidays (default: true)
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container


async def main():
    """Main function for daily task tracker."""
    parser = argparse.ArgumentParser(
        description="Daily Task Tracker Service"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for testing)",
    )
    
    args = parser.parse_args()
    
    try:
        container = get_container()
        
        from jira_telegram_bot.frameworks.scheduler.daily_task_tracker_job import (
            DailyTaskTrackerJob,
        )
        
        job = container[DailyTaskTrackerJob]
        
        if args.once:
            LOGGER.info("Running daily task tracker once")
            await job.run_once()
            LOGGER.info("Daily task tracker run complete")
        else:
            LOGGER.info("Starting daily task tracker service")
            await job.start()
            
    except KeyboardInterrupt:
        LOGGER.info("Received interrupt signal, shutting down...")
    except Exception as e:
        LOGGER.error(f"Fatal error in daily task tracker: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
