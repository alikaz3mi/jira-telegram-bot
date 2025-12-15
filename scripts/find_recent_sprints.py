"""Quick script to find recent sprint IDs."""
import asyncio
from sqlalchemy import text
from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface


async def find_recent_sprints():
    """Find recent sprint IDs from database."""
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    
    session = db_connection.get_session()
    try:
        result = session.execute(
            text("""
                SELECT DISTINCT sprint_id, sprint_name 
                FROM team_evaluation 
                ORDER BY sprint_id DESC 
                LIMIT 10
            """)
        )
        
        sprints = result.fetchall()
        LOGGER.info("Recent sprints in database:")
        for sprint_id, sprint_name in sprints:
            LOGGER.info(f"  Sprint ID: {sprint_id}, Name: {sprint_name}")
            
        if sprints:
            LOGGER.info(f"\nUse this command to re-run evaluation:")
            LOGGER.info(f"python scripts/manual_team_evaluation.py {sprints[0][0]} PARSCHAT")
            
        return [s[0] for s in sprints]
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(find_recent_sprints())
