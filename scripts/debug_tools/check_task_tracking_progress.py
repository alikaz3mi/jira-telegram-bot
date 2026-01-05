"""Check progress of task tracking fields backfill."""
from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface


def check_progress():
    """Check the current progress of backfill."""
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    
    session = db_connection.get_session()
    
    try:
        # Check filled counts
        result = session.execute(
            text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN due_date_first_set_at IS NOT NULL THEN 1 END) as due_date_filled,
                    COUNT(CASE WHEN involved_users IS NOT NULL AND involved_users != '' THEN 1 END) as involved_filled
                FROM jira_tasks_enhanced
            """)
        )
        
        row = result.fetchone()
        total, due_filled, involved_filled = row
        
        print("=" * 70)
        print("TASK TRACKING FIELDS PROGRESS")
        print("=" * 70)
        print(f"Total tasks: {total}")
        print(f"Tasks with due_date_first_set_at: {due_filled} ({due_filled/total*100:.1f}%)")
        print(f"Tasks with involved_users: {involved_filled} ({involved_filled/total*100:.1f}%)")
        print()
        
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
        
        print("Sample records:")
        for row in result:
            key, due_date, first_set, involved = row
            print(f"  {key}:")
            print(f"    due_date: {due_date}")
            print(f"    first_set: {first_set}")
            print(f"    involved: {involved}")
        
    finally:
        session.close()


if __name__ == "__main__":
    check_progress()
