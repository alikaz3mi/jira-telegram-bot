#!/usr/bin/env python3
"""Check manager evaluation tables population status."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)


def main():
    """Check manager evaluation tables."""
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    
    manager_name = "a_kazemi"
    
    print("=" * 80)
    print("MANAGER EVALUATION TABLES STATUS")
    print("=" * 80)
    
    with db_connection.get_session() as session:
        # Check manager_developer_assignments
        print("\n1. manager_developer_assignments table:")
        print("-" * 80)
        
        assignments_query = text("""
            SELECT 
                manager_name,
                developer_name,
                department,
                project_key,
                is_active
            FROM manager_developer_assignments
            WHERE manager_name = :manager
            ORDER BY developer_name
        """)
        
        assignments = session.execute(assignments_query, {"manager": manager_name}).fetchall()
        
        if assignments:
            print(f"\nFound {len(assignments)} assignments:")
            for row in assignments:
                status = "✓ Active" if row[4] else "✗ Inactive"
                print(f"  {status} - {row[0]} → {row[1]} ({row[2]}, {row[3]})")
        else:
            print("  ⚠ No assignments found!")
        
        # Check manager_evaluations
        print("\n2. manager_evaluations table:")
        print("-" * 80)
        
        eval_count_query = text("""
            SELECT 
                COUNT(*) as total_evaluations,
                COUNT(DISTINCT sprint_id) as unique_sprints,
                COUNT(DISTINCT developer_name) as unique_developers
            FROM manager_evaluations
            WHERE manager_name = :manager
        """)
        
        counts = session.execute(eval_count_query, {"manager": manager_name}).fetchone()
        
        print(f"\nTotal evaluations: {counts[0]}")
        print(f"Unique sprints: {counts[1]}")
        print(f"Unique developers: {counts[2]}")
        
        if counts[0] > 0:
            # Breakdown by developer
            breakdown_query = text("""
                SELECT 
                    developer_name,
                    COUNT(*) as evaluation_count
                FROM manager_evaluations
                WHERE manager_name = :manager
                GROUP BY developer_name
                ORDER BY developer_name
            """)
            
            breakdown = session.execute(breakdown_query, {"manager": manager_name}).fetchall()
            
            print("\nEvaluations per developer:")
            for row in breakdown:
                print(f"  {row[0]}: {row[1]} evaluations")
            
            # Sample records
            sample_query = text("""
                SELECT 
                    sprint_id,
                    developer_name,
                    evaluation_month,
                    collaboration_score,
                    alignment_score,
                    total_manager_score
                FROM manager_evaluations
                WHERE manager_name = :manager
                ORDER BY evaluation_month DESC, sprint_id
                LIMIT 5
            """)
            
            samples = session.execute(sample_query, {"manager": manager_name}).fetchall()
            
            print("\nSample records (most recent 5):")
            for row in samples:
                scores = f"C:{row[3] or 'NULL'} A:{row[4] or 'NULL'} T:{row[5] or 'NULL'}"
                print(f"  Sprint {row[0]} | {row[1]} | {row[2]} | {scores}")
        else:
            print("\n⚠ No evaluation records found!")
            print("\nYou need to run the monthly evaluation creation script:")
            print("  python scripts/run_monthly_evaluation_creation.py")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if len(assignments) > 0 and counts[0] > 0:
        print("✓ Both tables are populated correctly!")
        print(f"  - {len(assignments)} manager-developer assignments")
        print(f"  - {counts[0]} evaluation records across {counts[1]} sprints")
    elif len(assignments) > 0:
        print("⚠ Assignments exist but evaluations missing!")
        print("  Run: python scripts/run_monthly_evaluation_creation.py")
    else:
        print("✗ No data found. Run populate script first.")


if __name__ == "__main__":
    main()
