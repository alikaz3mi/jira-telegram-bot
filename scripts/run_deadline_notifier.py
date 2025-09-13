#!/usr/bin/env python3
"""
Standalone script to run the deadline notifier cron job.

This script can be run as a standalone process or in a container to periodically
check for Jira issues with approaching deadlines and send notifications.

Usage:
    python run_deadline_notifier.py [--once]

Environment Variables:
    DEADLINE_NOTIFIER_CRON: Cron schedule (default: random time between 8-9 AM daily)
    DEADLINE_NOTIFIER_LOOKAHEAD_DAYS: Days to look ahead (default: 7)
    DEADLINE_NOTIFIER_ADDITIONAL_JQL: Additional JQL filter (optional)
    TELEGRAM_GROUP_CHAT_IDS: Comma-separated group chat IDs for group notifications
    DEADLINE_NOTIFIER_START_HOUR: Start hour for random scheduling (default: 8)
    DEADLINE_NOTIFIER_END_HOUR: End hour for random scheduling (default: 9)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from pathlib import Path

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.frameworks.scheduler.cron_job import CronJob
from jira_telegram_bot.use_cases.send_deadline_alerts_use_case import (
    SendDeadlineAlertsUseCase,
)


def generate_random_cron_schedule(start_hour: int = 8, end_hour: int = 9) -> str:
    """Generate a random cron schedule between start_hour and end_hour.

    Args:
        start_hour: Start hour (inclusive, 0-23)
        end_hour: End hour (exclusive, 0-23)

    Returns:
        Cron schedule string (e.g., "25 8 * * *" for 8:25 AM daily)
    """
    # Generate random minute (0-59)
    random_minute = random.randint(0, 59)

    # Generate random hour between start_hour and end_hour-1
    random_hour = random.randint(start_hour, end_hour - 1)

    # Return daily cron schedule: "minute hour * * *"
    return f"{random_minute} {random_hour} * * *"


async def main():
    """Main function for the deadline notifier."""
    parser = argparse.ArgumentParser(description="Jira Deadline Notifier")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once instead of as a continuous cron job",
    )
    parser.add_argument(
        "--cron",
        default=os.environ.get("DEADLINE_NOTIFIER_CRON"),
        help="Cron schedule expression (default: random time between 8-9 AM daily)",
    )
    parser.add_argument(
        "--start-hour",
        type=int,
        default=int(os.environ.get("DEADLINE_NOTIFIER_START_HOUR", "8")),
        help="Start hour for random scheduling (default: 8)",
    )
    parser.add_argument(
        "--end-hour",
        type=int,
        default=int(os.environ.get("DEADLINE_NOTIFIER_END_HOUR", "9")),
        help="End hour for random scheduling (default: 9)",
    )
    parser.add_argument(
        "--lookahead-days",
        type=int,
        default=int(os.environ.get("DEADLINE_NOTIFIER_LOOKAHEAD_DAYS", "7")),
        help="Number of days to look ahead for deadlines (default: 7)",
    )
    parser.add_argument(
        "--additional-jql",
        default=os.environ.get("DEADLINE_NOTIFIER_ADDITIONAL_JQL"),
        help="Additional JQL filter to apply",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    import logging

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        LOGGER.info("Starting Jira Deadline Notifier...")

        # Generate random cron schedule if not explicitly provided
        if not args.cron:
            args.cron = generate_random_cron_schedule(args.start_hour, args.end_hour)

        LOGGER.info(f"Configuration:")
        LOGGER.info(f"  Run once: {args.once}")
        LOGGER.info(f"  Cron schedule: {args.cron}")
        LOGGER.info(f"  Lookahead days: {args.lookahead_days}")
        LOGGER.info(f"  Additional JQL: {args.additional_jql or 'None'}")
        LOGGER.info(f"  Log level: {args.log_level}")

        # Get dependencies from container
        container = get_container()
        use_case = container[SendDeadlineAlertsUseCase]

        if args.once:
            # Run once
            LOGGER.info("Running deadline notifier once...")
            stats = await use_case.execute(
                lookahead_days=args.lookahead_days,
                additional_jql=args.additional_jql,
            )
            LOGGER.info(f"Deadline notifier completed with stats: {stats}")
        else:
            # Run as cron job
            cron_job = CronJob(
                send_deadline_alerts_use_case=use_case,
                cron_schedule=args.cron,
                lookahead_days=args.lookahead_days,
                additional_jql=args.additional_jql,
            )

            await cron_job.start()

    except KeyboardInterrupt:
        LOGGER.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        LOGGER.error(f"Error running deadline notifier: {e}")
        sys.exit(1)

    LOGGER.info("Deadline notifier stopped")


if __name__ == "__main__":
    # Install required dependencies if missing
    try:
        import croniter
    except ImportError:
        LOGGER.error("croniter package is required. Install with: pip install croniter")
        sys.exit(1)

    asyncio.run(main())
