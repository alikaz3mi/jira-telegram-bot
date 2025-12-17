"""Use case for creating monthly evaluation records at the end of each Jalali month."""
from datetime import datetime
from typing import List

import jdatetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.manager_evaluation_repository import (
    ManagerEvaluationRepository,
)
from jira_telegram_bot.entities.manager_evaluation import ManagerDeveloperAssignment
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)


class CreateMonthlyEvaluationRecordsUseCase:
    """Create evaluation records for the upcoming month based on active assignments.
    
    This use case should be run at the end of each Jalali month to prepare
    evaluation records for all active manager-developer assignments.
    """

    def __init__(
        self,
        manager_eval_repo: ManagerEvaluationRepository,
        db_connection: DatabaseConnectionInterface,
    ) -> None:
        """Initialize use case.
        
        Args:
            manager_eval_repo: Manager evaluation repository
            db_connection: Database connection
        """
        self.manager_eval_repo = manager_eval_repo
        self.db_connection = db_connection

    def execute(self, target_month: str = None) -> dict:
        """Create evaluation records for the target month.
        
        Args:
            target_month: Target month in YYYY-MM format (Gregorian).
                If None, uses next month.
                
        Returns:
            Dictionary with creation results:
            {
                "month": "1403-10",  # Jalali month
                "gregorian_month": "2024-12",
                "records_created": 15,
                "assignments_processed": [
                    {"manager": "...", "developer": "...", "created": True},
                    ...
                ]
            }
        """
        # Determine target month
        if target_month is None:
            target_month = self._get_next_month()
        
        # Convert to Jalali for display
        jalali_month = self._gregorian_to_jalali_month(target_month)
        
        LOGGER.info(f"Creating evaluation records for month {jalali_month} ({target_month})")
        
        # Get all active manager-developer assignments
        assignments = self._get_active_assignments()
        
        if not assignments:
            LOGGER.warning("No active manager-developer assignments found")
            return {
                "month": jalali_month,
                "gregorian_month": target_month,
                "records_created": 0,
                "assignments_processed": [],
            }
        
        LOGGER.info(f"Found {len(assignments)} active assignments")
        
        # Get all sprints in this month
        sprint_ids = self._get_sprints_in_month(target_month)
        
        if not sprint_ids:
            LOGGER.warning(f"No sprints found for month {target_month}")
            return {
                "month": jalali_month,
                "gregorian_month": target_month,
                "records_created": 0,
                "assignments_processed": [],
                "error": "No sprints found for target month",
            }
        
        # Create evaluation records
        results = []
        records_created = 0
        
        for assignment in assignments:
            for sprint_id in sprint_ids:
                # Check if evaluation already exists
                existing = self.manager_eval_repo.get_evaluation(
                    sprint_id=sprint_id,
                    developer_name=assignment.developer_name,
                    manager_name=assignment.manager_name,
                )
                
                if existing:
                    LOGGER.debug(
                        f"Evaluation already exists for {assignment.developer_name} "
                        f"by {assignment.manager_name} in sprint {sprint_id}"
                    )
                    results.append({
                        "manager": assignment.manager_name,
                        "developer": assignment.developer_name,
                        "sprint_id": sprint_id,
                        "created": False,
                        "reason": "Already exists",
                    })
                    continue
                
                # Create placeholder evaluation record
                try:
                    self.manager_eval_repo.create_placeholder_evaluation(
                        sprint_id=sprint_id,
                        developer_name=assignment.developer_name,
                        manager_name=assignment.manager_name,
                        evaluation_month=target_month,
                    )
                    
                    records_created += 1
                    results.append({
                        "manager": assignment.manager_name,
                        "developer": assignment.developer_name,
                        "sprint_id": sprint_id,
                        "created": True,
                    })
                    
                    LOGGER.info(
                        f"Created evaluation record for {assignment.developer_name} "
                        f"by {assignment.manager_name} in sprint {sprint_id}"
                    )
                    
                except Exception as e:
                    LOGGER.error(
                        f"Failed to create evaluation for {assignment.developer_name}: {e}"
                    )
                    results.append({
                        "manager": assignment.manager_name,
                        "developer": assignment.developer_name,
                        "sprint_id": sprint_id,
                        "created": False,
                        "error": str(e),
                    })
        
        LOGGER.info(f"Created {records_created} evaluation records for {jalali_month}")
        
        return {
            "month": jalali_month,
            "gregorian_month": target_month,
            "records_created": records_created,
            "total_assignments": len(assignments),
            "sprints_found": len(sprint_ids),
            "assignments_processed": results,
        }

    def _get_next_month(self) -> str:
        """Get next month in YYYY-MM format.
        
        Returns:
            Next month string (Gregorian)
        """
        now = datetime.now()
        
        # Get next month
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        
        return next_month.strftime("%Y-%m")

    def _gregorian_to_jalali_month(self, gregorian_month: str) -> str:
        """Convert Gregorian month to Jalali.
        
        Args:
            gregorian_month: Month in YYYY-MM format
            
        Returns:
            Jalali month in YYYY-MM format
        """
        try:
            year, month = map(int, gregorian_month.split("-"))
            gregorian_date = datetime(year, month, 1)
            jalali_date = jdatetime.date.fromgregorian(date=gregorian_date.date())
            return f"{jalali_date.year:04d}-{jalali_date.month:02d}"
        except Exception as e:
            LOGGER.error(f"Error converting date: {e}")
            return gregorian_month

    def _get_active_assignments(self) -> List[ManagerDeveloperAssignment]:
        """Get all active manager-developer assignments.
        
        Returns:
            List of active assignments
        """
        return self.manager_eval_repo.get_all_active_assignments()

    def _get_sprints_in_month(self, target_month: str) -> List[int]:
        """Get all sprint IDs in the target month.
        
        Args:
            target_month: Month in YYYY-MM format
            
        Returns:
            List of sprint IDs
        """
        session = self.db_connection.get_session()
        
        try:
            from sqlalchemy import text
            
            query = text("""
                SELECT DISTINCT sprint_id
                FROM team_evaluation
                WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', :month::date)
                ORDER BY sprint_id
            """)
            
            result = session.execute(query, {"month": f"{target_month}-01"})
            return [row[0] for row in result]
            
        except Exception as e:
            LOGGER.error(f"Error getting sprints: {e}")
            return []
        finally:
            session.close()
