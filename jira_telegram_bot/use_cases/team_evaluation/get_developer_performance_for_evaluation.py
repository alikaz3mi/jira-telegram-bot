"""Use case for getting developer performance data for manager evaluation."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import text

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.manager_evaluation_repository import (
    ManagerEvaluationRepository,
)
from jira_telegram_bot.adapters.repositories.postgres.member_project_role_repository import (
    MemberProjectRoleRepository,
)
from jira_telegram_bot.entities.manager_evaluation import DeveloperPerformanceData
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


class GetDeveloperPerformanceForEvaluation:
    """Get developer performance data for manager evaluation.
    
    This use case aggregates:
    - System-calculated scores (70% component)
    - Work items (stories, features)
    - Existing manager evaluations if any
    
    This data is presented to managers so they can make informed
    evaluations based on both quantitative metrics and qualitative work.
    """

    def __init__(
        self,
        db_connection: DatabaseConnectionInterface,
        task_manager_repo: TaskManagerRepositoryInterface,
        manager_eval_repo: ManagerEvaluationRepository,
        member_role_repo: MemberProjectRoleRepository,
    ):
        """Initialize use case.
        
        Args:
            db_connection: Database connection
            task_manager_repo: Jira repository
            manager_eval_repo: Manager evaluation repository
            member_role_repo: Member project role repository
        """
        self.db_connection = db_connection
        self.task_manager_repo = task_manager_repo
        self.manager_eval_repo = manager_eval_repo
        self.member_role_repo = member_role_repo

    def execute(
        self,
        sprint_id: int,
        developer_name: str,
    ) -> Optional[DeveloperPerformanceData]:
        """Get performance data for a developer in a sprint.
        
        Args:
            sprint_id: Sprint ID
            developer_name: Developer name
            
        Returns:
            Performance data or None if not found
        """
        session = self.db_connection.get_session()
        
        try:
            # Get team evaluation data (system scores)
            query = text("""
                SELECT 
                    sprint_id,
                    sprint_name,
                    developer_name,
                    department,
                    quality_score,
                    deadline_score,
                    worklog_score,
                    high_priority_score,
                    defect_score,
                    development_count,
                    bug_count,
                    support_count,
                    high_priority_completed_count,
                    registered_hours_week,
                    expected_hours_week,
                    avg_deadline_delivery_days,
                    review_back_count
                FROM team_evaluation
                WHERE sprint_id = :sprint_id AND developer_name = :developer_name
            """)
            
            result = session.execute(
                query,
                {"sprint_id": sprint_id, "developer_name": developer_name}
            )
            
            row = result.fetchone()
            if not row:
                LOGGER.warning(
                    f"No team evaluation found for {developer_name} in sprint {sprint_id}"
                )
                return None
            
            # Extract sprint month for evaluation
            sprint_name = row[1]
            # Assuming sprint_name format includes date info, otherwise use created_at
            evaluation_month = datetime.now().strftime("%Y-%m")
            
            # Calculate system score (70% component)
            deadline_score = row[5] or 0
            worklog_score = row[6] or 0
            priority_score = row[7] or 0
            quality_score = row[4] or 0
            
            system_score = (
                deadline_score * 0.25 +
                worklog_score * 0.20 +
                priority_score * 0.40 +
                quality_score * 0.15
            )
            
            # Get stories/features the developer worked on
            stories = self._get_developer_stories(sprint_id, developer_name)
            features = self._get_developer_features(sprint_id, developer_name)
            
            # Get existing manager evaluation if any
            evaluations = self.manager_eval_repo.get_evaluations_for_developer(
                sprint_id, developer_name
            )
            
            # Calculate average existing scores
            avg_manager_score = None
            avg_collaboration = None
            avg_alignment = None
            combined_comments = None
            
            if evaluations:
                avg_manager_score = sum(e.total_manager_score for e in evaluations) / len(evaluations)
                avg_collaboration = sum(e.collaboration_score for e in evaluations) / len(evaluations)
                avg_alignment = sum(e.alignment_score for e in evaluations) / len(evaluations)
                combined_comments = "\n\n".join(
                    f"[{e.manager_name}]: {e.comments}" 
                    for e in evaluations if e.comments
                )
            
            # Parse avg_deadline_delivery_days
            avg_delivery = None
            if row[15]:
                try:
                    avg_delivery = float(str(row[15]).replace('d', ''))
                except (ValueError, AttributeError):
                    pass
            
            # Get developer's role information
            # Try to get account_id from developer name first
            developer_account_id = self._get_developer_account_id(developer_name)
            member_role = None
            if developer_account_id:
                role_summary = self.member_role_repo.get_member_role_summary(developer_account_id)
                # Get effective role (project-specific if exists, otherwise overall)
                project_key = self._extract_project_key_from_sprint(sprint_id)
                member_role = role_summary.get_effective_role(project_key)
            
            return DeveloperPerformanceData(
                developer_name=developer_name,
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                department=row[3],
                evaluation_month=evaluation_month,
                member_role=member_role,
                system_score=system_score,
                deadline_score=deadline_score,
                worklog_score=worklog_score,
                priority_score=priority_score,
                quality_score=quality_score,
                development_count=row[9],
                bug_count=row[10],
                support_count=row[11],
                high_priority_completed=row[12],
                registered_hours=row[13],
                expected_hours=row[14],
                avg_deadline_delivery_days=avg_delivery,
                review_back_count=row[16],
                stories_worked_on=stories,
                features_delivered=features,
                existing_manager_score=int(avg_manager_score) if avg_manager_score else None,
                existing_collaboration_score=int(avg_collaboration) if avg_collaboration else None,
                existing_alignment_score=int(avg_alignment) if avg_alignment else None,
                existing_comments=combined_comments,
            )
            
        finally:
            session.close()

    def _get_developer_stories(self, sprint_id: int, developer_name: str) -> List[str]:
        """Get list of stories the developer worked on.
        
        Args:
            sprint_id: Sprint ID
            developer_name: Developer name
            
        Returns:
            List of story keys with summaries
        """
        session = self.db_connection.get_session()
        
        try:
            query = text("""
                SELECT DISTINCT key, summary
                FROM jira_tasks_enhanced
                WHERE sprint_id = :sprint_id
                AND (assignee = :developer_name OR involved_users LIKE :developer_pattern)
                AND issue_type IN ('Story', 'Task')
                ORDER BY key
                LIMIT 20
            """)
            
            result = session.execute(
                query,
                {
                    "sprint_id": sprint_id,
                    "developer_name": developer_name,
                    "developer_pattern": f"%{developer_name}%",
                }
            )
            
            return [f"{row[0]}: {row[1]}" for row in result]
            
        except Exception as e:
            LOGGER.error(f"Error getting stories: {e}")
            return []
        finally:
            session.close()

    def _get_developer_features(self, sprint_id: int, developer_name: str) -> List[str]:
        """Get list of features/epics the developer contributed to.
        
        Args:
            sprint_id: Sprint ID
            developer_name: Developer name
            
        Returns:
            List of epic/feature names
        """
        session = self.db_connection.get_session()
        
        try:
            query = text("""
                SELECT DISTINCT epic_key, epic_name
                FROM jira_tasks_enhanced
                WHERE sprint_id = :sprint_id
                AND (assignee = :developer_name OR involved_users LIKE :developer_pattern)
                AND epic_key IS NOT NULL
                ORDER BY epic_key
                LIMIT 10
            """)
            
            result = session.execute(
                query,
                {
                    "sprint_id": sprint_id,
                    "developer_name": developer_name,
                    "developer_pattern": f"%{developer_name}%",
                }
            )
            
            return [f"{row[0]}: {row[1]}" for row in result if row[1]]
            
        except Exception as e:
            LOGGER.error(f"Error getting features: {e}")
            return []
        finally:
            session.close()

    def _get_developer_account_id(self, developer_name: str) -> Optional[str]:
        """Get Jira account ID for a developer by name.
        
        Args:
            developer_name: Developer display name
            
        Returns:
            Jira account ID or None if not found
        """
        session = self.db_connection.get_session()
        
        try:
            query = text("""
                SELECT DISTINCT assignee_account_id
                FROM jira_tasks_enhanced
                WHERE assignee = :developer_name
                LIMIT 1
            """)
            
            result = session.execute(query, {"developer_name": developer_name})
            row = result.fetchone()
            return row[0] if row else None
            
        except Exception as e:
            LOGGER.error(f"Error getting account ID: {e}")
            return None
        finally:
            session.close()

    def _extract_project_key_from_sprint(self, sprint_id: int) -> Optional[str]:
        """Extract project key from a sprint.
        
        Args:
            sprint_id: Sprint ID
            
        Returns:
            Project key or None
        """
        session = self.db_connection.get_session()
        
        try:
            query = text("""
                SELECT DISTINCT project_key
                FROM jira_tasks_enhanced
                WHERE sprint_id = :sprint_id
                LIMIT 1
            """)
            
            result = session.execute(query, {"sprint_id": sprint_id})
            row = result.fetchone()
            return row[0] if row else None
            
        except Exception as e:
            LOGGER.error(f"Error getting project key: {e}")
            return None
        finally:
            session.close()

    def get_developers_needing_evaluation(
        self,
        manager_name: str,
        evaluation_month: str,
    ) -> List[DeveloperPerformanceData]:
        """Get all developers assigned to a manager who need evaluation.
        
        Args:
            manager_name: Manager name
            evaluation_month: Month in YYYY-MM format
            
        Returns:
            List of developer performance data
        """
        # Get assigned developers
        assignments = self.manager_eval_repo.get_developers_for_manager(manager_name)
        
        if not assignments:
            return []
        
        session = self.db_connection.get_session()
        
        try:
            # Get sprints in this month
            query = text("""
                SELECT DISTINCT sprint_id, developer_name
                FROM team_evaluation
                WHERE developer_name = ANY(:developers)
                AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', :month::date)
            """)
            
            result = session.execute(
                query,
                {
                    "developers": [a.developer_name for a in assignments],
                    "month": f"{evaluation_month}-01",
                }
            )
            
            performance_data = []
            for row in result:
                sprint_id = row[0]
                developer_name = row[1]
                
                data = self.execute(sprint_id, developer_name)
                if data:
                    performance_data.append(data)
            
            return performance_data
            
        finally:
            session.close()
