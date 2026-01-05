"""Script to view and populate delay_reason for manager evaluations."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def main() -> None:
    """View manager evaluations and their current delay_reason values."""
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
        # Query all evaluation records
        result = connection.execute(
            text("""
                SELECT 
                    id,
                    sprint_id,
                    developer_name,
                    manager_name,
                    evaluation_month,
                    collaboration_score,
                    alignment_score,
                    total_manager_score,
                    delay_reason,
                    created_at
                FROM manager_evaluations
                ORDER BY evaluation_month DESC, developer_name
            """)
        )
        
        records = result.fetchall()
        
        print("\n" + "=" * 120)
        print(f"{'ID':<6} {'Sprint':<8} {'Developer':<15} {'Manager':<12} {'Month':<10} {'Collab':<8} {'Align':<8} {'Total':<8} {'Delay Reason':<30}")
        print("=" * 120)
        
        for record in records:
            delay_reason = record[8] if record[8] else "(No delay reason)"
            print(
                f"{record[0]:<6} "
                f"{record[1]:<8} "
                f"{record[2]:<15} "
                f"{record[3]:<12} "
                f"{record[4]:<10} "
                f"{str(record[5]) if record[5] else 'NULL':<8} "
                f"{str(record[6]) if record[6] else 'NULL':<8} "
                f"{str(record[7]) if record[7] else 'NULL':<8} "
                f"{delay_reason:<30}"
            )
        
        print("=" * 120)
        print(f"\nTotal records: {len(records)}")
        print("\nNOTE: The 'delay_reason' column has been added to the manager_evaluations table.")
        print("      Currently all records show '(No delay reason)' because this field is not")
        print("      available in Jira API responses.")
        print("\nTo populate delay_reason:")
        print("  1. Managers should manually review sprint delays")
        print("  2. Update records via SQL or admin interface")
        print("  3. Example SQL:")
        print("     UPDATE manager_evaluations")
        print("     SET delay_reason = 'Sprint延期 - dependency on backend team'")
        print("     WHERE id = 1;")


if __name__ == "__main__":
    main()
