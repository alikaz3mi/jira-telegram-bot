#!/usr/bin/env python
"""Script to create monthly evaluation records at the end of each Jalali month.

This script should be run via cron at the end of each month (e.g., on the 29th
or 30th of each Jalali month) to pre-create evaluation records for the next month.

Usage:
    python scripts/run_monthly_evaluation_creation.py [--month YYYY-MM]
    
Examples:
    # Create for next month (automatic)
    python scripts/run_monthly_evaluation_creation.py
    
    # Create for specific month
    python scripts/run_monthly_evaluation_creation.py --month 2025-01
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.team_evaluation.create_monthly_evaluation_records import (
    CreateMonthlyEvaluationRecordsUseCase,
)


def main():
    """Run monthly evaluation record creation."""
    parser = argparse.ArgumentParser(
        description="Create monthly evaluation records for manager evaluations"
    )
    parser.add_argument(
        "--month",
        type=str,
        help="Target month in YYYY-MM format (Gregorian). If not provided, uses next month.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created without actually creating records",
    )
    
    args = parser.parse_args()
    
    try:
        # Get container and use case
        container = get_container()
        use_case = container.resolve(CreateMonthlyEvaluationRecordsUseCase)
        
        LOGGER.info("=" * 60)
        LOGGER.info("Starting Monthly Evaluation Record Creation")
        LOGGER.info("=" * 60)
        
        if args.dry_run:
            LOGGER.info("DRY RUN MODE - No records will be created")
        
        # Execute use case
        result = use_case.execute(target_month=args.month)
        
        # Display results
        LOGGER.info(f"\nMonth: {result['month']} (Jalali)")
        LOGGER.info(f"Gregorian Month: {result['gregorian_month']}")
        LOGGER.info(f"Records Created: {result['records_created']}")
        LOGGER.info(f"Assignments Processed: {len(result['assignments_processed'])}")
        
        if "error" in result:
            LOGGER.error(f"Error: {result['error']}")
            return 1
        
        # Show details for each assignment
        if result['assignments_processed']:
            LOGGER.info("\nDetailed Results:")
            LOGGER.info("-" * 60)
            
            for item in result['assignments_processed']:
                status = "✓ Created" if item['created'] else "✗ Skipped"
                reason = f" ({item.get('reason', '')})" if not item['created'] else ""
                LOGGER.info(
                    f"{status}: {item['manager']} → {item['developer']} "
                    f"(Sprint {item['sprint_id']}){reason}"
                )
        
        LOGGER.info("=" * 60)
        LOGGER.info(f"Completed! {result['records_created']} records created.")
        LOGGER.info("=" * 60)
        
        return 0
        
    except Exception as e:
        LOGGER.error(f"Failed to create monthly evaluation records: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
