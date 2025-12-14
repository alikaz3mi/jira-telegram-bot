"""Backfill team evaluation scores for historical sprints."""
from __future__ import annotations

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser as date_parser

sys.path.insert(0, str(Path(__file__).parent.parent))

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.team_evaluation.sprint_closed_team_evaluation_use_case import (
    SprintClosedTeamEvaluationUseCase,
)
from jira_telegram_bot.entities.team_evaluation import SprintClosedEvent


def fetch_closed_sprints_last_4_months(
    task_manager_repo: TaskManagerRepositoryInterface,
    scrum_boards: list
) -> list[dict]:
    """Fetch all closed sprints from the last 4 months.
    
    Args:
        task_manager_repo: Task manager repository
        scrum_boards: List of Scrum board objects
        
    Returns:
        List of sprint data dictionaries
    """
    LOGGER.info(f"Fetching closed sprints from last 4 months for {len(scrum_boards)} Scrum boards")
    
    # Calculate date 4 months ago
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)  # Approximately 4 months
    
    closed_sprints = []
    
    for board in scrum_boards:
        try:
            project_key = board.name.replace(' board', '').strip()
            LOGGER.info(f"Fetching sprints for board {board.id} ({board.name})")
            
            # Get all sprints for this board directly
            sprints = task_manager_repo.jira.sprints(board.id)
            
            LOGGER.info(f"Found {len(sprints)} sprints for board {board.id}")
            
            for sprint in sprints:
                LOGGER.debug(f"Sprint {sprint.name}: state={sprint.state}, endDate={getattr(sprint, 'endDate', None)}, completeDate={getattr(sprint, 'completeDate', None)}")
                
                # Check if sprint is closed and within date range
                if sprint.state.lower() != 'closed':
                    LOGGER.debug(f"  Skipping {sprint.name} - state is {sprint.state}, not closed")
                    continue
                
                if not hasattr(sprint, 'endDate') or not sprint.endDate:
                    LOGGER.debug(f"  Skipping {sprint.name} - no endDate")
                    continue
                
                # Parse endDate (it's a string)
                try:
                    sprint_end = date_parser.parse(sprint.endDate)
                except Exception as e:
                    LOGGER.warning(f"  Skipping {sprint.name} - could not parse endDate: {e}")
                    continue
                
                # Convert to naive datetime for comparison if needed
                if hasattr(sprint_end, 'tzinfo') and sprint_end.tzinfo is not None:
                    sprint_end_naive = sprint_end.replace(tzinfo=None)
                else:
                    sprint_end_naive = sprint_end
                
                if sprint_end_naive < start_date:
                    LOGGER.debug(f"  Skipping {sprint.name} - ended {sprint_end_naive}, before cutoff {start_date}")
                    continue
                
                sprint_start = None
                if hasattr(sprint, 'startDate') and sprint.startDate:
                    try:
                        sprint_start = date_parser.parse(sprint.startDate)
                    except Exception:
                        pass
                
                closed_sprints.append({
                    'id': sprint.id,
                    'name': sprint.name,
                    'project_key': project_key,
                    'board_id': board.id,
                    'started_at': sprint_start,
                    'ended_at': sprint_end,
                })
                
                LOGGER.info(
                    f"Found closed sprint: {sprint.name} "
                    f"(board: {board.name}, ended: {sprint_end.strftime('%Y-%m-%d')})"
                )
        
        except Exception as e:
            LOGGER.error(f"Error fetching sprints for project {project_key}: {e}", exc_info=True)
            continue
    
    LOGGER.info(f"Found {len(closed_sprints)} closed sprints in total")
    return closed_sprints


def get_sprint_developers(
    task_manager_repo: TaskManagerRepositoryInterface,
    sprint_id: int,
    project_keys: list[str]
) -> list[str]:
    """Get list of developers who worked on a sprint.
    
    Args:
        task_manager_repo: Task manager repository
        sprint_id: Sprint ID
        project_keys: Project keys to search
        
    Returns:
        List of developer usernames
    """
    try:
        # Build JQL to get issues for the sprint
        projects_filter = " OR ".join([f'project = "{key}"' for key in project_keys])
        jql = f"({projects_filter}) AND sprint = {sprint_id}"
        
        # Get all issues in the sprint
        issues = task_manager_repo.search_for_issues(jql, max_results=1000)
        
        # Extract unique assignees
        developers = set()
        for issue in issues:
            if hasattr(issue, 'fields') and hasattr(issue.fields, 'assignee'):
                assignee = issue.fields.assignee
                if assignee and hasattr(assignee, 'name'):
                    developers.add(assignee.name)
        
        return list(developers)
    
    except Exception as e:
        LOGGER.error(f"Error getting developers for sprint {sprint_id}: {e}", exc_info=True)
        return []


async def backfill_team_evaluations():
    """Backfill team evaluation scores for all closed sprints in last 4 months."""
    LOGGER.info("Starting team evaluation backfill process")
    
    # Get dependencies from container
    container = get_container()
    task_manager_repo = container[TaskManagerRepositoryInterface]
    evaluation_use_case = container[SprintClosedTeamEvaluationUseCase]
    
    # Discover all Scrum boards automatically
    LOGGER.info("Discovering all Scrum boards in Jira...")
    all_boards = task_manager_repo.jira.boards()
    scrum_boards = [board for board in all_boards if board.type == 'scrum']
    
    board_names = [board.name for board in scrum_boards]
    LOGGER.info(f"Found {len(scrum_boards)} Scrum boards: {', '.join(board_names)}")
    
    # Fetch all closed sprints
    closed_sprints = fetch_closed_sprints_last_4_months(task_manager_repo, scrum_boards)
    
    if not closed_sprints:
        LOGGER.warning("No closed sprints found in the last 4 months")
        return
    
    # Process each sprint
    processed_count = 0
    error_count = 0
    
    for sprint_data in closed_sprints:
        try:
            LOGGER.info(f"Processing sprint: {sprint_data['name']} (ID: {sprint_data['id']})")
            
            # Get developers for this sprint
            developers = get_sprint_developers(
                task_manager_repo,
                sprint_data['id'],
                [sprint_data['project_key']]
            )
            
            if not developers:
                LOGGER.warning(f"No developers found for sprint {sprint_data['name']}, skipping")
                continue
            
            LOGGER.info(f"Found {len(developers)} developers: {', '.join(developers)}")
            
            # Create sprint closed event
            event = SprintClosedEvent(
                sprint_id=sprint_data['id'],
                sprint_name=sprint_data['name'],
                project_keys=[sprint_data['project_key']],
                started_at=sprint_data['started_at'],
                ended_at=sprint_data['ended_at'],
            )
            
            # Execute evaluation use case (it's async)
            await evaluation_use_case.process_sprint_closed(event)
            
            processed_count += 1
            LOGGER.info(
                f"Successfully processed sprint {sprint_data['name']} "
                f"({processed_count}/{len(closed_sprints)})"
            )
        
        except Exception as e:
            error_count += 1
            LOGGER.error(
                f"Error processing sprint {sprint_data.get('name', 'Unknown')}: {e}",
                exc_info=True
            )
            continue
    
    # Summary
    LOGGER.info("=" * 80)
    LOGGER.info("Backfill completed:")
    LOGGER.info(f"  Total sprints found: {len(closed_sprints)}")
    LOGGER.info(f"  Successfully processed: {processed_count}")
    LOGGER.info(f"  Errors: {error_count}")
    LOGGER.info("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(backfill_team_evaluations())
    except Exception as e:
        LOGGER.error(f"Backfill failed: {e}", exc_info=True)
        sys.exit(1)
