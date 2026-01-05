"""Helper script to check configured projects and database sync status."""
from __future__ import annotations

import asyncio
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.jira_sync_settings import JiraSyncSettings
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)


async def check_project_status():
    """Display configured projects and their current sync status."""
    try:
        container = get_container()
        settings = JiraSyncSettings()
        db_connection = container[DatabaseConnectionInterface]
        
        projects = settings.sync_project_keys
        
        print("=" * 80)
        print("CONFIGURED JIRA PROJECTS")
        print("=" * 80)
        print(f"\nTotal configured projects: {len(projects)}")
        print(f"Projects: {', '.join(projects)}")
        print(f"\nSync settings:")
        print(f"  - Interval: {settings.sync_interval_minutes} minutes")
        print(f"  - Full sync: {settings.sync_full_sync}")
        
        print("\n" + "=" * 80)
        print("DATABASE SYNC STATUS")
        print("=" * 80)
        
        session = db_connection.get_session()
        
        try:
            from sqlalchemy import text
            
            print("\nIssues per project in database:")
            print("-" * 80)
            
            result = session.execute(
                text("""
                    SELECT 
                        project,
                        COUNT(*) as issue_count,
                        MAX(last_synced) as last_sync,
                        MIN(created_at) as oldest_issue,
                        MAX(updated_at) as newest_update
                    FROM jira_tasks_enhanced
                    GROUP BY project
                    ORDER BY project
                """)
            )
            
            rows = result.fetchall()
            
            if not rows:
                print("No issues found in database")
            else:
                total_issues = 0
                for row in rows:
                    project = row[0]
                    count = row[1]
                    last_sync = row[2]
                    oldest = row[3]
                    newest = row[4]
                    
                    total_issues += count
                    
                    configured = "✓" if project in projects else "✗"
                    
                    print(f"\n{configured} {project}:")
                    print(f"  Issues: {count}")
                    if last_sync:
                        print(f"  Last synced: {last_sync.strftime('%Y-%m-%d %H:%M:%S')}")
                    if oldest:
                        print(f"  Oldest issue: {oldest.strftime('%Y-%m-%d')}")
                    if newest:
                        print(f"  Newest update: {newest.strftime('%Y-%m-%d %H:%M:%S')}")
                
                print("\n" + "-" * 80)
                print(f"Total issues in database: {total_issues}")
            
            print("\n" + "=" * 80)
            print("SYNC STATUS TRACKING")
            print("=" * 80)
            
            status_result = session.execute(
                text("""
                    SELECT 
                        project_key,
                        last_full_sync,
                        last_incremental_sync,
                        last_sync_status,
                        issues_synced,
                        issues_failed,
                        sync_duration_seconds
                    FROM sync_status
                    ORDER BY project_key
                """)
            )
            
            status_rows = status_result.fetchall()
            
            if not status_rows:
                print("\nNo sync status records found")
            else:
                for row in status_rows:
                    project = row[0]
                    last_full = row[1]
                    last_incr = row[2]
                    status = row[3]
                    synced = row[4]
                    failed = row[5]
                    duration = row[6]
                    
                    configured = "✓" if project in projects else "✗"
                    
                    print(f"\n{configured} {project}:")
                    print(f"  Status: {status}")
                    if last_full:
                        print(f"  Last full sync: {last_full.strftime('%Y-%m-%d %H:%M:%S')}")
                    if last_incr:
                        print(f"  Last incremental: {last_incr.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"  Last sync: {synced} issues synced, {failed} failed")
                    if duration:
                        print(f"  Duration: {duration:.2f} seconds")
            
            print("\n" + "=" * 80)
            print("RECOMMENDATIONS")
            print("=" * 80)
            
            db_projects = {row[0] for row in rows} if rows else set()
            configured_set = set(projects)
            
            missing_in_db = configured_set - db_projects
            extra_in_db = db_projects - configured_set
            
            if missing_in_db:
                print(f"\n⚠ Projects configured but NOT in database:")
                for proj in missing_in_db:
                    print(f"  - {proj}")
                print("\n  → Run: python scripts/sync_projects_date_range.py --projects " + 
                      " ".join(missing_in_db) + " --full-sync")
            
            if extra_in_db:
                print(f"\n⚠ Projects in database but NOT configured:")
                for proj in extra_in_db:
                    print(f"  - {proj}")
                print("\n  → Add to .env file or remove from considerations")
            
            if not missing_in_db and not extra_in_db:
                print("\n✓ All configured projects are synced to database!")
                print("\n  → Keep updated: python scripts/sync_all_projects_last_month.py")
            
            print("\n" + "=" * 80)
            
        finally:
            session.close()
            
    except Exception as e:
        LOGGER.error(f"Failed to check project status: {e}", exc_info=True)
        raise


def main():
    """Entry point."""
    asyncio.run(check_project_status())


if __name__ == "__main__":
    main()
