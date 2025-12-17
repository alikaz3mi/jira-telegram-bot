#!/usr/bin/env python3
"""Create manager evaluation records for past 4 Jalali months.

This script creates placeholder evaluation records (with NULL scores) for all
sprints from the past 4 months for all assigned manager-developer pairs.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import jdatetime
from datetime import datetime
from sqlalchemy import text

from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


def create_records():
    """Create evaluation records for past 4 months."""
    print("=" * 80)
    print("CREATING MANAGER EVALUATION RECORDS FOR PAST 4 JALALI MONTHS")
    print("=" * 80)
    
    # Get database connection and Jira repository
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    task_manager_repo = container[TaskManagerRepositoryInterface]
    
    # Calculate date range (4 months ago to now)
    today = jdatetime.datetime.now()
    four_months_ago = today - jdatetime.timedelta(days=120)  # Approximately 4 months
    
    # Convert to Gregorian for database query
    start_date_gregorian = four_months_ago.togregorian()
    end_date_gregorian = today.togregorian()
    
    print(f"\nDate range (Jalali): {four_months_ago.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    print(f"Date range (Gregorian): {start_date_gregorian.strftime('%Y-%m-%d')} to {end_date_gregorian.strftime('%Y-%m-%d')}")
    
    with db_connection.get_session() as session:
        # Step 1: Get all active manager-developer assignments
        print("\n1. Fetching Active Manager-Developer Assignments")
        print("-" * 80)
        
        assignments_query = text("""
            SELECT 
                manager_name,
                developer_name,
                project_key,
                department
            FROM manager_developer_assignments
            WHERE is_active = true
        """)
        
        assignments = session.execute(assignments_query).fetchall()
        print(f"Found {len(assignments)} active assignments")
        
        if len(assignments) == 0:
            print("⚠ No active assignments found. Run populate_manager_evaluations_direct.py first!")
            return
        
        for row in assignments:
            print(f"  - {row[0]} → {row[1]} ({row[2]}/{row[3]})")
        
        # Step 2: Get all sprints in date range for each project using Jira API
        print("\n2. Fetching Sprints from Past 4 Months (via Jira API)")
        print("-" * 80)
        
        # Get unique project keys
        project_keys = list(set([row[2] for row in assignments]))
        
        all_sprints = []
        for project_key in project_keys:
            try:
                # Get board ID for this project
                board_id = task_manager_repo.get_board_id(project_key)
                
                if not board_id:
                    print(f"⚠ No board found for project {project_key}")
                    continue
                
                # Get sprints for this board
                sprints = task_manager_repo.get_sprints(board_id)
                
                print(f"\nProject {project_key} (Board {board_id}): Found {len(sprints)} total sprints")
                
                # Filter sprints by date range and state
                for sprint in sprints:
                    # Skip future sprints
                    if sprint.state == 'future':
                        continue
                    
                    # Check if sprint end date is in our range
                    if hasattr(sprint, 'endDate') and sprint.endDate:
                        end_date = sprint.endDate if isinstance(sprint.endDate, datetime) else datetime.fromisoformat(str(sprint.endDate))
                        
                        # Remove timezone info for comparison
                        end_date_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
                        
                        if start_date_gregorian <= end_date_naive <= end_date_gregorian:
                            end_jalali = jdatetime.datetime.fromgregorian(datetime=end_date)
                            month_str = end_jalali.strftime('%Y-%m')
                            
                            sprint_info = {
                                'id': sprint.id,
                                'name': sprint.name,
                                'end_date': end_date,
                                'evaluation_month': month_str,
                                'project_key': project_key
                            }
                            all_sprints.append(sprint_info)
                            print(f"  ✓ Sprint {sprint.id}: {sprint.name} (ends {month_str})")
                
                project_sprint_count = len([s for s in all_sprints if s['project_key'] == project_key])
                print(f"  Total matching sprints: {project_sprint_count}")
                
            except Exception as e:
                print(f"✗ Error fetching sprints for {project_key}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\nTotal sprints across all projects: {len(all_sprints)}")
        
        # Step 3: Create evaluation records for each assignment × sprint
        print("\n3. Creating Evaluation Records")
        print("-" * 80)
        
        records_created = 0
        records_skipped = 0
        
        for assignment in assignments:
            manager_name = assignment[0]
            developer_name = assignment[1]
            project_key = assignment[2]
            
            # Filter sprints for this project
            project_sprints = [s for s in all_sprints if s['project_key'] == project_key]
            
            for sprint in project_sprints:
                sprint_id = sprint['id']
                sprint_name = sprint['name']
                evaluation_month = sprint['evaluation_month']
                
                try:
                    # Check if evaluation already exists
                    check_query = text("""
                        SELECT id FROM manager_evaluations
                        WHERE sprint_id = :sprint_id 
                        AND developer_name = :developer 
                        AND manager_name = :manager
                    """)
                    
                    existing = session.execute(check_query, {
                        "sprint_id": sprint_id,
                        "developer": developer_name,
                        "manager": manager_name
                    }).fetchone()
                    
                    if existing:
                        records_skipped += 1
                    else:
                        # Create placeholder evaluation (NULL scores)
                        insert_query = text("""
                            INSERT INTO manager_evaluations
                            (sprint_id, developer_name, manager_name, evaluation_month, 
                             collaboration_score, alignment_score, total_manager_score,
                             created_at, updated_at)
                            VALUES (:sprint_id, :developer, :manager, :month,
                                    NULL, NULL, NULL, NOW(), NOW())
                        """)
                        
                        session.execute(insert_query, {
                            "sprint_id": sprint_id,
                            "developer": developer_name,
                            "manager": manager_name,
                            "month": evaluation_month
                        })
                        
                        session.commit()
                        print(f"  ✓ Created: {manager_name} → {developer_name} | Sprint {sprint_id} ({sprint_name}) | {evaluation_month}")
                        records_created += 1
                        
                except Exception as e:
                    print(f"  ✗ Failed: {manager_name} → {developer_name} | Sprint {sprint_id}: {e}")
                    session.rollback()
        
        # Step 4: Verify results
        print("\n4. Verification")
        print("-" * 80)
        
        verify_query = text("""
            SELECT 
                manager_name,
                COUNT(*) as total_evaluations,
                COUNT(DISTINCT sprint_id) as unique_sprints,
                COUNT(DISTINCT developer_name) as unique_developers
            FROM manager_evaluations
            GROUP BY manager_name
        """)
        
        results = session.execute(verify_query).fetchall()
        
        for row in results:
            print(f"\nManager: {row[0]}")
            print(f"  Total evaluations: {row[1]}")
            print(f"  Unique sprints: {row[2]}")
            print(f"  Unique developers: {row[3]}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"New records created: {records_created}")
    print(f"Existing records skipped: {records_skipped}")
    print(f"Total assignments: {len(assignments)}")
    print(f"Total sprints: {len(all_sprints)}")
    print(f"Expected total: {len(assignments)} assignments × sprints per project")
    
    if records_created > 0:
        print("\n✓ Evaluation records created successfully!")
    elif records_skipped > 0:
        print("\n✓ All records already exist (no duplicates created)")
    
    print("\nNEXT STEPS:")
    print("1. Managers can now fill in scores via admin panel")
    print("2. Scores to fill: collaboration_score and alignment_score (0-100)")
    print("3. System will auto-calculate total_manager_score")
    print("=" * 80)


def main():
    """Entry point that runs the sync function."""
    create_records()


if __name__ == "__main__":
    main()
