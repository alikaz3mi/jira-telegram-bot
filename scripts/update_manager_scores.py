"""Script to update manager evaluation scores for team members."""
import asyncio
from typing import Optional
from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface


async def list_recent_evaluations(limit: int = 20):
    """List recent team evaluations that need manager scoring.
    
    Args:
        limit: Maximum number of evaluations to show
    """
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    session = db_connection.get_session()
    
    try:
        result = session.execute(
            text("""
                SELECT 
                    id,
                    sprint_name,
                    developer_name,
                    department,
                    project,
                    system_score,
                    manager_evaluation_score,
                    final_score,
                    created_at
                FROM team_evaluation
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        
        evaluations = result.fetchall()
        
        print("\n" + "=" * 100)
        print("RECENT TEAM EVALUATIONS")
        print("=" * 100)
        print(f"{'ID':<6} {'Sprint':<20} {'Developer':<20} {'Dept':<12} {'System':<8} {'Manager':<8} {'Final':<8}")
        print("-" * 100)
        
        for row in evaluations:
            eval_id, sprint, dev, dept, _, system, manager, final, _ = row
            system_str = str(system) if system is not None else "N/A"
            manager_str = str(manager) if manager is not None else "---"
            final_str = str(final) if final is not None else "N/A"
            
            print(f"{eval_id:<6} {sprint:<20} {dev:<20} {dept:<12} {system_str:<8} {manager_str:<8} {final_str:<8}")
        
        print("=" * 100)
        
    finally:
        session.close()


async def update_manager_score(
    evaluation_id: int,
    manager_score: int,
    recalculate_final: bool = True
):
    """Update manager evaluation score for a specific evaluation.
    
    Args:
        evaluation_id: The ID of the team evaluation record
        manager_score: Manager's evaluation score (0-100)
        recalculate_final: Whether to recalculate the final score
    """
    if not 0 <= manager_score <= 100:
        LOGGER.error(f"Manager score must be between 0 and 100, got {manager_score}")
        return
    
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    session = db_connection.get_session()
    
    try:
        if recalculate_final:
            # Update manager score and recalculate final score (70% system + 30% manager)
            session.execute(
                text("""
                    UPDATE team_evaluation
                    SET manager_evaluation_score = :manager_score,
                        final_score = ROUND(
                            COALESCE(system_score, quality_score) * 0.7 + :manager_score * 0.3
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :eval_id
                """),
                {"eval_id": evaluation_id, "manager_score": manager_score}
            )
        else:
            # Just update manager score
            session.execute(
                text("""
                    UPDATE team_evaluation
                    SET manager_evaluation_score = :manager_score,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :eval_id
                """),
                {"eval_id": evaluation_id, "manager_score": manager_score}
            )
        
        session.commit()
        
        # Fetch and display updated record
        result = session.execute(
            text("""
                SELECT 
                    sprint_name, developer_name, department,
                    system_score, manager_evaluation_score, final_score
                FROM team_evaluation
                WHERE id = :eval_id
            """),
            {"eval_id": evaluation_id}
        )
        
        row = result.fetchone()
        if row:
            sprint, dev, dept, system, manager, final = row
            print(f"\n✓ Updated evaluation #{evaluation_id}")
            print(f"  Developer: {dev} ({dept})")
            print(f"  Sprint: {sprint}")
            print(f"  System Score: {system}")
            print(f"  Manager Score: {manager}")
            print(f"  Final Score: {final}")
        else:
            print(f"\n✗ Evaluation #{evaluation_id} not found")
            
    except Exception as e:
        session.rollback()
        LOGGER.error(f"Error updating manager score: {e}")
        raise
    finally:
        session.close()


async def bulk_update_by_sprint(
    sprint_name: str,
    developer_scores: dict[str, int]
):
    """Bulk update manager scores for all developers in a sprint.
    
    Args:
        sprint_name: Name of the sprint
        developer_scores: Dictionary mapping developer names to scores
    """
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    session = db_connection.get_session()
    
    try:
        updated_count = 0
        
        for developer, score in developer_scores.items():
            if not 0 <= score <= 100:
                LOGGER.warning(f"Skipping {developer}: score {score} out of range")
                continue
            
            result = session.execute(
                text("""
                    UPDATE team_evaluation
                    SET manager_evaluation_score = :score,
                        final_score = ROUND(
                            COALESCE(system_score, quality_score) * 0.7 + :score * 0.3
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE sprint_name = :sprint
                    AND developer_name = :developer
                """),
                {
                    "sprint": sprint_name,
                    "developer": developer,
                    "score": score
                }
            )
            
            if result.rowcount > 0:
                updated_count += result.rowcount
                print(f"✓ Updated {developer}: {score}")
            else:
                print(f"✗ Not found: {developer}")
        
        session.commit()
        print(f"\n✓ Bulk update complete: {updated_count} records updated")
        
    except Exception as e:
        session.rollback()
        LOGGER.error(f"Error in bulk update: {e}")
        raise
    finally:
        session.close()


async def interactive_mode():
    """Interactive mode for updating manager scores."""
    print("\n" + "=" * 60)
    print("MANAGER EVALUATION SCORE UPDATER")
    print("=" * 60)
    
    while True:
        print("\nOptions:")
        print("1. List recent evaluations")
        print("2. Update single evaluation")
        print("3. Bulk update by sprint")
        print("4. Exit")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            limit = input("Number of records to show (default 20): ").strip()
            limit = int(limit) if limit.isdigit() else 20
            await list_recent_evaluations(limit)
            
        elif choice == "2":
            eval_id = input("Enter evaluation ID: ").strip()
            if not eval_id.isdigit():
                print("Invalid ID")
                continue
            
            score = input("Enter manager score (0-100): ").strip()
            if not score.isdigit() or not 0 <= int(score) <= 100:
                print("Invalid score")
                continue
            
            await update_manager_score(int(eval_id), int(score))
            
        elif choice == "3":
            sprint = input("Enter sprint name: ").strip()
            print("Enter developer scores (format: developer_name=score)")
            print("Enter empty line when done")
            
            scores = {}
            while True:
                line = input("> ").strip()
                if not line:
                    break
                    
                try:
                    dev, score = line.split("=")
                    scores[dev.strip()] = int(score.strip())
                except ValueError:
                    print("Invalid format. Use: developer_name=score")
            
            if scores:
                await bulk_update_by_sprint(sprint, scores)
            else:
                print("No scores entered")
                
        elif choice == "4":
            print("Goodbye!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Command line mode
        if sys.argv[1] == "list":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            asyncio.run(list_recent_evaluations(limit))
        elif sys.argv[1] == "update":
            if len(sys.argv) < 4:
                print("Usage: python update_manager_scores.py update <eval_id> <score>")
                sys.exit(1)
            eval_id = int(sys.argv[2])
            score = int(sys.argv[3])
            asyncio.run(update_manager_score(eval_id, score))
        else:
            print("Unknown command")
            sys.exit(1)
    else:
        # Interactive mode
        asyncio.run(interactive_mode())
