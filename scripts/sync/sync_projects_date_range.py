"""Script to sync configured Jira projects within a custom date range.

This script provides flexible date-based synchronization with options for:
- Custom start date
- Specific project selection
- Full project sync or date-filtered sync
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from datetime import timedelta
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.jira_sync_settings import JiraSyncSettings
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import (
    JiraDataServiceInterface,
)
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import (
    JiraReportRepositoryInterface,
)


async def sync_projects_by_date(
    project_keys: Optional[List[str]] = None,
    days_back: int = 30,
    since_date: Optional[datetime] = None,
    full_sync: bool = False,
):
    """Sync projects with flexible date filtering.
    
    Args:
        project_keys: Specific projects to sync (None = all configured projects)
        days_back: Number of days to look back (default: 30)
        since_date: Specific start date (overrides days_back if provided)
        full_sync: If True, sync all issues regardless of date
        
    Returns:
        Dict with sync statistics
    """
    try:
        LOGGER.info("=" * 80)
        LOGGER.info("Starting flexible project synchronization")
        LOGGER.info("=" * 80)
        
        container = get_container()
        jira_service = container[JiraDataServiceInterface]
        report_repository = container[JiraReportRepositoryInterface]
        settings = JiraSyncSettings()
        
        if project_keys:
            projects = [
                p for p in settings.sync_project_keys 
                if p in project_keys
            ]
            if not projects:
                LOGGER.error(
                    f"None of the specified projects {project_keys} found in "
                    f"configured projects {settings.sync_project_keys}"
                )
                return {"synced": 0, "failed": len(project_keys)}
        else:
            projects = settings.sync_project_keys
        
        if not projects:
            LOGGER.warning("No projects configured in sync_project_keys")
            return {"synced": 0, "failed": 0}
        
        if since_date:
            start_date = since_date
        else:
            start_date = datetime.now() - timedelta(days=days_back)
        
        if full_sync:
            LOGGER.info(f"Performing FULL sync for {len(projects)} project(s)")
        else:
            LOGGER.info(
                f"Syncing {len(projects)} project(s) for issues updated since: "
                f"{start_date.strftime('%Y-%m-%d %H:%M:%S')} "
                f"({days_back} days ago)"
            )
        
        results = {
            "total_projects": len(projects),
            "projects_synced": 0,
            "projects_failed": 0,
            "total_issues": 0,
            "project_details": {},
        }
        
        for project_key in projects:
            try:
                LOGGER.info("-" * 80)
                LOGGER.info(f"Processing project: {project_key}")
                
                if full_sync:
                    issues = await jira_service.fetch_project_issues(project_key)
                    LOGGER.info(f"Full sync: fetched {len(issues)} total issues")
                else:
                    issues = await jira_service.fetch_updated_issues(
                        project_key=project_key,
                        since=start_date
                    )
                    LOGGER.info(
                        f"Date-filtered: found {len(issues)} updated issue(s)"
                    )
                
                if not issues:
                    LOGGER.info(f"No issues to sync for {project_key}")
                    results["project_details"][project_key] = {
                        "status": "success",
                        "issues_synced": 0
                    }
                    results["projects_synced"] += 1
                    continue
                
                await report_repository.store_issues(issues)
                
                results["total_issues"] += len(issues)
                results["projects_synced"] += 1
                results["project_details"][project_key] = {
                    "status": "success",
                    "issues_synced": len(issues)
                }
                
                LOGGER.info(
                    f"✓ Successfully synced {len(issues)} issue(s) for {project_key}"
                )
                
            except Exception as e:
                results["projects_failed"] += 1
                results["project_details"][project_key] = {
                    "status": "failed",
                    "error": str(e)
                }
                LOGGER.error(
                    f"✗ Failed to sync project {project_key}: {e}",
                    exc_info=True
                )
        
        LOGGER.info("=" * 80)
        LOGGER.info("Synchronization Summary")
        LOGGER.info("=" * 80)
        LOGGER.info(f"Projects attempted: {results['total_projects']}")
        LOGGER.info(f"Projects synced: {results['projects_synced']}")
        LOGGER.info(f"Projects failed: {results['projects_failed']}")
        LOGGER.info(f"Total issues synced: {results['total_issues']}")
        LOGGER.info("=" * 80)
        
        for project, details in results["project_details"].items():
            status_icon = "✓" if details["status"] == "success" else "✗"
            if details["status"] == "success":
                LOGGER.info(
                    f"{status_icon} {project}: {details['issues_synced']} issues"
                )
            else:
                LOGGER.error(f"{status_icon} {project}: {details['error']}")
        
        LOGGER.info("=" * 80)
        
        return results
        
    except Exception as e:
        LOGGER.error(f"Critical error in sync: {e}", exc_info=True)
        raise


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync Jira projects with flexible date filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync all projects from last month (default)
  python scripts/sync_projects_date_range.py

  # Sync specific projects from last 7 days
  python scripts/sync_projects_date_range.py --projects PROJECT1 PROJECT2 --days 7

  # Sync all projects from a specific date
  python scripts/sync_projects_date_range.py --since 2025-12-01

  # Full sync (all issues, ignore date filter)
  python scripts/sync_projects_date_range.py --full-sync

  # Sync from last 90 days
  python scripts/sync_projects_date_range.py --days 90
        """
    )
    
    parser.add_argument(
        "--projects",
        nargs="+",
        help="Specific project keys to sync (default: all configured projects)"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)"
    )
    
    parser.add_argument(
        "--since",
        type=str,
        help="Sync issues updated since this date (format: YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--full-sync",
        action="store_true",
        help="Perform full sync (ignore date filters)"
    )
    
    return parser.parse_args()


async def main_async():
    """Run the synchronization with CLI arguments."""
    args = parse_args()
    
    since_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            LOGGER.error(
                f"Invalid date format: {args.since}. Use YYYY-MM-DD format."
            )
            return
    
    await sync_projects_by_date(
        project_keys=args.projects,
        days_back=args.days,
        since_date=since_date,
        full_sync=args.full_sync,
    )


def main():
    """Entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
