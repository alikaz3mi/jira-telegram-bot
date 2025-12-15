"""Backfill calculation logs from existing team_evaluation data."""
import asyncio
from sqlalchemy import text
from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface
from jira_telegram_bot.use_cases.interfaces.team_evaluation_calculation_log_repository_interface import (
    TeamEvaluationCalculationLogRepositoryInterface
)
from jira_telegram_bot.use_cases.team_evaluation.calculation_logger import CalculationLogger
from jira_telegram_bot.settings.team_evaluation_settings import TeamEvaluationSettings


async def backfill_calculation_logs():
    """Backfill calculation logs from existing team_evaluation records."""
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    calc_log_repo = container[TeamEvaluationCalculationLogRepositoryInterface]
    settings = TeamEvaluationSettings()
    
    session = db_connection.get_session()
    
    try:
        # Get all team_evaluation rows that don't have calculation logs yet
        result = session.execute(
            text("""
                SELECT DISTINCT te.id, te.sprint_id, te.sprint_name, te.developer_name, 
                       te.department, te.project, te.development_count, te.bug_count,
                       te.support_count, te.high_priority_count, te.registered_hours_week,
                       te.expected_hours_week, te.development_hours, te.bug_hours,
                       te.support_hours, te.high_priority_completed_count,
                       te.avg_support_bugs_per_story, te.avg_tester_bugs_per_story,
                       te.quality_score
                FROM team_evaluation te
                LEFT JOIN team_evaluation_calculation_log cl 
                    ON te.sprint_id = cl.sprint_id AND te.developer_name = cl.developer_name
                WHERE cl.id IS NULL
                ORDER BY te.sprint_id DESC, te.developer_name
            """)
        )
        
        rows = result.fetchall()
        LOGGER.info(f"Found {len(rows)} team_evaluation rows without calculation logs")
        
        total_logs_created = 0
        
        for row in rows:
            (eval_id, sprint_id, sprint_name, developer_name, department, project,
             dev_count, bug_count, support_count, high_priority_count,
             registered_hours, expected_hours, dev_hours, bug_hours, support_hours,
             high_priority_completed, support_bugs_per_story, tester_bugs_per_story,
             quality_score) = row
            
            logs = []
            
            # Task classification logs
            logs.extend(CalculationLogger.log_task_classification(
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                developer=developer_name,
                department=department,
                project=project,
                dev_count=dev_count or 0,
                bug_count=bug_count or 0,
                support_count=support_count or 0,
                high_priority_count=high_priority_count or 0,
                total_issues=(dev_count or 0) + (bug_count or 0) + (support_count or 0)
            ))
            
            # Time metrics logs
            logs.extend(CalculationLogger.log_time_metrics(
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                developer=developer_name,
                department=department,
                project=project,
                total_hours=registered_hours or 0,
                expected_hours=expected_hours or 0,
                dev_hours=dev_hours or 0,
                bug_hours=bug_hours or 0,
                support_hours=support_hours or 0,
                worklog_count=0,  # Not available from evaluation data
                filtered_count=0
            ))
            
            # Worklog score
            worklog_score = (registered_hours / expected_hours * 100) if expected_hours > 0 else 0
            logs.append(CalculationLogger.log_worklog_score(
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                developer=developer_name,
                department=department,
                project=project,
                registered_hours=registered_hours or 0,
                expected_hours=expected_hours or 0,
                worklog_score=worklog_score,
                weight=settings.score_weights.worklog
            ))
            
            # High priority score
            high_priority_score = (high_priority_completed / high_priority_count * 100) if high_priority_count > 0 else 0
            logs.append(CalculationLogger.log_high_priority_score(
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                developer=developer_name,
                department=department,
                project=project,
                required_tasks=high_priority_count or 0,
                completed_required=high_priority_completed or 0,
                high_priority_score=high_priority_score,
                weight=settings.score_weights.high_priority
            ))
            
            # Defect score
            logs.append(CalculationLogger.log_defect_score(
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                developer=developer_name,
                department=department,
                project=project,
                support_bugs_per_story=support_bugs_per_story or 0,
                tester_bugs_per_story=tester_bugs_per_story or 0,
                defect_score=100,  # Approximate
                weight=settings.score_weights.defects,
                support_threshold=0.3,
                tester_threshold=0.4
            ))
            
            # Final score
            logs.append(CalculationLogger.log_final_score(
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                developer=developer_name,
                department=department,
                project=project,
                composite_score=quality_score or 0,
                penalties_applied=0,
                bonuses_applied=0,
                final_score=quality_score or 0
            ))
            
            # Save all logs for this developer
            calc_log_repo.save_logs_batch(logs)
            total_logs_created += len(logs)
            
            LOGGER.info(f"Created {len(logs)} calculation logs for {developer_name} in sprint {sprint_id}")
        
        LOGGER.info(f"\n✓ Backfill complete! Created {total_logs_created} calculation log entries for {len(rows)} evaluations")
        
    except Exception as e:
        LOGGER.error(f"Error during backfill: {e}", exc_info=True)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    LOGGER.info("=" * 70)
    LOGGER.info("CALCULATION LOG BACKFILL")
    LOGGER.info("=" * 70)
    asyncio.run(backfill_calculation_logs())
