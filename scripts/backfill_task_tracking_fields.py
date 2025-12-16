"""Backfill due_date_first_set_at and involved_users fields in jira_tasks_enhanced."""
import asyncio
from datetime import datetime
from typing import Set, Optional
from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface


async def get_due_date_first_set_from_changelog(
    task_manager_repo: TaskManagerRepositoryInterface,
    issue_key: str
) -> Optional[datetime]:
    """Get the timestamp when due date was first set from changelog.
    
    Args:
        task_manager_repo: Jira repository
        issue_key: Issue key
        
    Returns:
        Timestamp when due date was first set, or None
    """
    try:
        # Get changelogs for the issue (returns dict mapping issue_key -> list of ChangeLogEvent)
        changelogs = await task_manager_repo.get_issue_changelogs([issue_key])
        
        if issue_key not in changelogs:
            return None
            
        # Look for "Due Date" or "duedate" field changes
        # Sort by timestamp to get the earliest
        due_date_events = []
        for event in changelogs[issue_key]:
            if event.field.lower() in ['due date', 'duedate']:
                # Check if it was set from None/null to a value
                if not event.from_status and event.to_status:
                    due_date_events.append(event)
        
        if due_date_events:
            # Return the earliest change
            earliest = min(due_date_events, key=lambda e: e.changed_at)
            return earliest.changed_at
                    
        return None
        
    except Exception as e:
        LOGGER.debug(f"Error getting changelog for {issue_key}: {e}")
        return None


async def get_involved_users_from_jira(
    task_manager_repo: TaskManagerRepositoryInterface,
    issue_key: str
) -> Set[str]:
    """Get list of users involved in the issue (commenters + worklog authors).
    
    Args:
        task_manager_repo: Jira repository
        issue_key: Issue key
        
    Returns:
        Set of usernames
    """
    involved = set()
    
    try:
        # Get the issue to check for comments
        issue = task_manager_repo.get_issue(issue_key)
        
        # Get commenters from issue comments
        if issue and hasattr(issue, 'fields') and hasattr(issue.fields, 'comment'):
            comments = issue.fields.comment.comments if hasattr(issue.fields.comment, 'comments') else []
            for comment in comments:
                if hasattr(comment, 'author') and hasattr(comment.author, 'name'):
                    involved.add(comment.author.name)
                elif hasattr(comment, 'author') and hasattr(comment.author, 'displayName'):
                    involved.add(comment.author.displayName)
        
        # Get worklog authors
        worklogs = await task_manager_repo.get_issue_worklogs([issue_key])
        for worklog in worklogs:
            if worklog.author:
                involved.add(worklog.author)
                
    except Exception as e:
        LOGGER.debug(f"Error getting involved users for {issue_key}: {e}")
        
    return involved


async def backfill_task_tracking_fields():
    """Backfill due_date_first_set_at and involved_users for all tasks."""
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    task_manager_repo = container[TaskManagerRepositoryInterface]
    
    session = db_connection.get_session()
    
    try:
        # Get all tasks that need backfilling
        result = session.execute(
            text("""
                SELECT key, due_date 
                FROM jira_tasks_enhanced 
                WHERE due_date_first_set_at IS NULL OR involved_users IS NULL
                ORDER BY key
            """)
        )
        
        tasks = result.fetchall()
        total_tasks = len(tasks)
        LOGGER.info(f"Found {total_tasks} tasks to backfill")
        
        updated_count = 0
        skipped_count = 0
        
        for idx, (issue_key, due_date) in enumerate(tasks, 1):
            try:
                LOGGER.info(f"[{idx}/{total_tasks}] Processing {issue_key}...")
                
                # Get due date first set timestamp
                due_date_first_set = None
                if due_date:  # Only check changelog if task currently has a due date
                    due_date_first_set = await get_due_date_first_set_from_changelog(
                        task_manager_repo, issue_key
                    )
                    if not due_date_first_set:
                        # If we can't find in changelog, use the current due_date as fallback
                        due_date_first_set = due_date
                
                # Get involved users
                involved_users = await get_involved_users_from_jira(
                    task_manager_repo, issue_key
                )
                involved_users_str = ','.join(sorted(involved_users)) if involved_users else None
                
                # Update the task
                update_query = text("""
                    UPDATE jira_tasks_enhanced 
                    SET due_date_first_set_at = :due_date_first_set,
                        involved_users = :involved_users
                    WHERE key = :key
                """)
                
                session.execute(
                    update_query,
                    {
                        'key': issue_key,
                        'due_date_first_set': due_date_first_set,
                        'involved_users': involved_users_str
                    }
                )
                session.commit()
                
                updated_count += 1
                
                if updated_count % 10 == 0:
                    LOGGER.info(f"Progress: {updated_count}/{total_tasks} tasks updated")
                    
            except Exception as e:
                LOGGER.error(f"Error processing {issue_key}: {e}")
                session.rollback()
                skipped_count += 1
                continue
        
        LOGGER.info(f"\n✓ Backfill complete!")
        LOGGER.info(f"  Updated: {updated_count} tasks")
        LOGGER.info(f"  Skipped: {skipped_count} tasks")
        
    except Exception as e:
        LOGGER.error(f"Error during backfill: {e}", exc_info=True)
        raise
    finally:
        session.close()


async def verify_backfill():
    """Verify the backfill results."""
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    
    session = db_connection.get_session()
    
    try:
        # Check filled counts
        result = session.execute(
            text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(due_date_first_set_at) as with_due_date_first_set,
                    COUNT(involved_users) as with_involved_users,
                    COUNT(CASE WHEN due_date_first_set_at IS NOT NULL THEN 1 END) as due_date_filled,
                    COUNT(CASE WHEN involved_users IS NOT NULL AND involved_users != '' THEN 1 END) as involved_filled
                FROM jira_tasks_enhanced
            """)
        )
        
        row = result.fetchone()
        total, with_due_date, with_involved, due_filled, involved_filled = row
        
        LOGGER.info("\n" + "=" * 70)
        LOGGER.info("BACKFILL VERIFICATION")
        LOGGER.info("=" * 70)
        LOGGER.info(f"Total tasks: {total}")
        LOGGER.info(f"Tasks with due_date_first_set_at: {due_filled} ({due_filled/total*100:.1f}%)")
        LOGGER.info(f"Tasks with involved_users: {involved_filled} ({involved_filled/total*100:.1f}%)")
        
        # Show sample
        result = session.execute(
            text("""
                SELECT key, due_date, due_date_first_set_at, involved_users
                FROM jira_tasks_enhanced
                WHERE due_date_first_set_at IS NOT NULL OR involved_users IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 5
            """)
        )
        
        LOGGER.info("\nSample records:")
        for row in result:
            key, due_date, first_set, involved = row
            LOGGER.info(f"  {key}: due_date={due_date}, first_set={first_set}, involved={involved}")
        
    finally:
        session.close()


if __name__ == "__main__":
    LOGGER.info("=" * 70)
    LOGGER.info("TASK TRACKING FIELDS BACKFILL")
    LOGGER.info("=" * 70)
    
    asyncio.run(backfill_task_tracking_fields())
    asyncio.run(verify_backfill())
