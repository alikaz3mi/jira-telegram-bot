"""Script to manually trigger team evaluation for a specific sprint."""
import asyncio
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.team_evaluation import SprintClosedEvent
from jira_telegram_bot.use_cases.team_evaluation.sprint_closed_team_evaluation_use_case import (
    SprintClosedTeamEvaluationUseCase,
)


async def run_team_evaluation_for_sprint(sprint_id: int, project_keys: list[str]):
    """Run team evaluation for a specific sprint.
    
    Args:
        sprint_id: The Jira sprint ID
        project_keys: List of project keys (e.g., ['MYPROJECT'])
    """
    LOGGER.info(f"Running team evaluation for sprint {sprint_id}")
    LOGGER.info(f"Projects: {', '.join(project_keys)}")
    
    try:
        # Get container
        container = get_container()
        use_case = container[SprintClosedTeamEvaluationUseCase]
        
        # Create sprint closed event
        event = SprintClosedEvent(
            sprint_id=sprint_id,
            sprint_name=f"Sprint {sprint_id}",  # Will be updated from Jira
            project_keys=project_keys,
            started_at=datetime.now(),  # Will be updated from Jira
            ended_at=datetime.now()  # Will be updated from Jira
        )
        
        # Process the event
        await use_case.process_sprint_closed(event)
        
        LOGGER.info("✓ Team evaluation completed successfully!")
        LOGGER.info("Check the database tables:")
        LOGGER.info("  - team_evaluation: for evaluation rows")
        LOGGER.info("  - team_evaluation_calculation_log: for detailed calculation logs")
        
    except Exception as e:
        LOGGER.error(f"✗ Error running team evaluation: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import sys
    
    # Get sprint ID from command line or use default
    sprint_id = int(sys.argv[1]) if len(sys.argv) > 1 else 392
    project_keys = sys.argv[2:] if len(sys.argv) > 2 else ["MYPROJECT"]
    
    LOGGER.info("=" * 70)
    LOGGER.info("MANUAL TEAM EVALUATION RUN")
    LOGGER.info("=" * 70)
    
    asyncio.run(run_team_evaluation_for_sprint(sprint_id, project_keys))
