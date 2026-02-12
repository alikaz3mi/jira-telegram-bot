"""Script to view jira_tasks_enhanced with delay_reason column."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def main() -> None:
    """View jira_tasks_enhanced records with delay_reason."""
    # Load .env file
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
    
    # Get database settings from environment
    db_user = os.getenv("db_user", "telegram_bot").strip('"')
    db_password = os.getenv("db_password", "").strip('"')
    db_host = os.getenv("db_host", "localhost").strip('"')
    db_port = os.getenv("db_port", "57235").strip('"')
    db_name = os.getenv("db_name", "jira_telegram_bot").strip('"')
    
    # URL-encode password to handle special characters
    db_password_encoded = quote_plus(db_password)
    
    # Create engine
    connection_string = f"postgresql://{db_user}:{db_password_encoded}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(connection_string)
    
    with engine.connect() as connection:
        # First, verify the column exists
        result = connection.execute(
            text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'jira_tasks_enhanced' 
                AND column_name = 'delay_reason'
            """)
        )
        
        column_info = result.fetchone()
        if column_info:
            print(f"✓ Column 'delay_reason' exists in jira_tasks_enhanced table")
            print(f"  Type: {column_info[1]}\n")
        else:
            print("✗ Column 'delay_reason' NOT FOUND in jira_tasks_enhanced table\n")
            return
        
        # Query sample tasks with delay_reason
        result = connection.execute(
            text("""
                SELECT 
                    key,
                    summary,
                    status,
                    assignee,
                    due_date,
                    delay_reason,
                    updated_at
                FROM jira_tasks_enhanced
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 20
            """)
        )
        
        records = result.fetchall()
        
        print("=" * 140)
        print(f"{'Issue Key':<15} {'Status':<15} {'Assignee':<15} {'Due Date':<12} {'Delay Reason':<40} {'Summary':<30}")
        print("=" * 140)
        
        for record in records:
            key = record[0]
            summary = (record[1][:27] + "...") if record[1] and len(record[1]) > 30 else (record[1] or "")
            status = record[2] or "N/A"
            assignee = record[3] or "Unassigned"
            due_date = record[4].strftime("%Y-%m-%d") if record[4] else "No due date"
            delay_reason = record[5] if record[5] else "(No delay reason)"
            
            print(
                f"{key:<15} "
                f"{status:<15} "
                f"{assignee:<15} "
                f"{due_date:<12} "
                f"{delay_reason:<40} "
                f"{summary:<30}"
            )
        
        print("=" * 140)
        print(f"\nShowing {len(records)} most recently updated tasks")
        print("\nNOTE: The 'delay_reason' column has been successfully added to jira_tasks_enhanced table.")
        print("      This field can store reasons why tasks were delayed.")
        print("      Currently all records show '(No delay reason)' because this field is not")
        print("      automatically populated from Jira API.")
        print("\nTo populate delay_reason:")
        print("  1. Extract from Jira comments (if teams document delays there)")
        print("  2. Manually update via SQL based on task analysis")
        print("  3. Example SQL:")
        print("     UPDATE jira_tasks_enhanced")
        print("     SET delay_reason = 'Blocked by external dependency'")
        print("     WHERE key = 'MYPROJECT-1234';")


if __name__ == "__main__":
    main()
