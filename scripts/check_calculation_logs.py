"""Check if calculation logs table has data."""
import asyncio
from sqlalchemy import text
from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface


async def check_calculation_logs():
    """Check calculation log table."""
    container = get_container()
    db_connection = container[DatabaseConnectionInterface]
    
    session = db_connection.get_session()
    try:
        # Check if table exists and has data
        result = session.execute(
            text("SELECT COUNT(*) FROM team_evaluation_calculation_log")
        )
        count = result.scalar()
        LOGGER.info(f"Total calculation log entries: {count}")
        
        if count > 0:
            # Show sample logs
            result = session.execute(
                text("""
                    SELECT sprint_id, developer_name, calculation_type, metric_name, metric_value
                    FROM team_evaluation_calculation_log
                    ORDER BY id DESC
                    LIMIT 10
                """)
            )
            
            LOGGER.info("\nRecent calculation logs:")
            for row in result:
                LOGGER.info(f"  Sprint {row[0]}, {row[1]}: {row[2]} - {row[3]} = {row[4]}")
        else:
            LOGGER.info("No calculation logs found yet. The table is empty.")
            
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(check_calculation_logs())
