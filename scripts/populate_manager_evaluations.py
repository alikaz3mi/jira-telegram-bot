#!/usr/bin/env python3
"""Populate manager-developer assignments and create evaluation records.

This script:
1. Creates manager-developer assignments for PARSCHAT project
2. Creates evaluation records for past 4 Jalali months
3. Handles multiple sprints per month
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import jdatetime
from datetime import datetime

from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.adapters.repositories.postgres.manager_evaluation_repository import (
    ManagerEvaluationRepository,
)
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)


def main():
    """Populate manager evaluations for PARSCHAT project."""
    # Manager and developers mapping (from user_config.json)
    manager_name = "a_kazemi"
    developers = {
        "ghasemi": "m_ghasemi",
        "samei": "M_Samei",
        "smmms": "m_Mousavi",
        "lotfian": "z_lotfian",
        "emamdadi": "n_emamdadi",
        "jhamed": "jhamed.dp",
    }
    
    project_key = "PARSCHAT"
    department = "AI"  # Can be adjusted per developer if needed
    
    # Get dependencies
    container = get_container()
    db_connection = container.resolve(DatabaseConnectionInterface)
    manager_eval_repo = container.resolve(ManagerEvaluationRepository)
    
    print("=" * 80)
    print("POPULATING MANAGER-DEVELOPER ASSIGNMENTS AND EVALUATIONS")
    print("=" * 80)
    
    # Step 1: Create manager-developer assignments
    print("\n1. Creating Manager-Developer Assignments")
    print("-" * 80)
    
    assignments_created = 0
    for nickname, jira_username in developers.items():
        try:
            assignment = manager_eval_repo.assign_manager_to_developer(
                manager_name=manager_name,
                developer_name=jira_username,
                department=department,
                project_key=project_key,
            )
            print(f"✓ Assigned {manager_name} → {jira_username} ({nickname}) in {project_key}/{department}")
            assignments_created += 1
        except Exception as e:
            print(f"✗ Failed to assign {jira_username}: {e}")
    
    print(f"\nTotal assignments created: {assignments_created}/{len(developers)}")
    
    # Step 2: Get sprints from past 4 Jalali months
    print("\n2. Identifying Sprints from Past 4 Jalali Months")
    print("-" * 80)
    
    # Calculate date range (4 months ago to now)
    today = jdatetime.datetime.now()
    four_months_ago = today - jdatetime.timedelta(days=120)  # Approximately 4 months
    
    # Convert to Gregorian for database query
    start_date_gregorian = four_months_ago.togregorian()
    end_date_gregorian = today.togregorian()
    
    print(f"Date range (Jalali): {four_months_ago.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    print(f"Date range (Gregorian): {start_date_gregorian} to {end_date_gregorian}")
    
    # Fetch all sprints for PARSCHAT in date range
    try:
        with db_connection.get_session() as session:
            query = """
                SELECT DISTINCT 
                    s.id, 
                    s.name, 
                    s.start_date, 
                    s.end_date,
                    s.board_id
                FROM sprints s
                JOIN boards b ON s.board_id = b.id
                WHERE b.project_key = :project_key
                AND s.end_date >= :start_date
                AND s.start_date <= :end_date
                AND s.state != 'future'
                ORDER BY s.start_date
            """
            
            result = session.execute(
                query,
                {
                    "project_key": project_key,
                    "start_date": start_date_gregorian,
                    "end_date": end_date_gregorian,
                }
            )
            
            sprints = []
            for row in result:
                sprint_info = {
                    "id": row[0],
                    "name": row[1],
                    "start_date": row[2],
                    "end_date": row[3],
                    "board_id": row[4],
                }
                sprints.append(sprint_info)
                
                # Convert to Jalali for display
                end_jalali = jdatetime.datetime.fromgregorian(datetime=row[3])
                month_str = end_jalali.strftime('%Y-%m')
                
                print(f"  Sprint {row[0]}: {row[1]} (ends {month_str})")
            
            print(f"\nTotal sprints found: {len(sprints)}")
    
    except Exception as e:
        print(f"✗ Error fetching sprints: {e}")
        sprints = []
    
    # Step 3: Create evaluation records for each developer × sprint
    print("\n3. Creating Evaluation Records (Placeholders)")
    print("-" * 80)
    
    records_created = 0
    records_skipped = 0
    
    for sprint in sprints:
        # Determine evaluation month from sprint end date
        end_date_jalali = jdatetime.datetime.fromgregorian(datetime=sprint["end_date"])
        evaluation_month = end_date_jalali.strftime('%Y-%m')
        
        print(f"\nSprint {sprint['id']}: {sprint['name']} → Month {evaluation_month}")
        
        for nickname, jira_username in developers.items():
            try:
                # Create placeholder evaluation (NULL scores)
                evaluation = manager_eval_repo.create_placeholder_evaluation(
                    sprint_id=sprint["id"],
                    developer_name=jira_username,
                    manager_name=manager_name,
                    evaluation_month=evaluation_month,
                )
                print(f"  ✓ Created placeholder for {jira_username} ({nickname})")
                records_created += 1
                
            except Exception as e:
                # Likely duplicate - skip
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    print(f"  - Skipped {jira_username} (already exists)")
                    records_skipped += 1
                else:
                    print(f"  ✗ Failed for {jira_username}: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Manager-Developer Assignments: {assignments_created}")
    print(f"Sprints Identified: {len(sprints)}")
    print(f"Evaluation Records Created: {records_created}")
    print(f"Evaluation Records Skipped (duplicates): {records_skipped}")
    print(f"\nTotal expected records: {len(developers)} developers × {len(sprints)} sprints = {len(developers) * len(sprints)}")
    print(f"Total processed: {records_created + records_skipped}")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("1. Managers can now fill in the evaluation scores via admin panel")
    print("2. Scores to fill: collaboration_score and alignment_score (0-100)")
    print("3. The system will auto-calculate total_manager_score")
    print("4. Monthly automation will create new records at end of each Jalali month")
    print("\nTo view records:")
    print("  SELECT * FROM manager_evaluations WHERE manager_name = 'a_kazemi' ORDER BY evaluation_month, sprint_id;")


if __name__ == "__main__":
    main()
