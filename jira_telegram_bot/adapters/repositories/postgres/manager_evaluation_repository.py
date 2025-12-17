"""Repository for manager evaluation data."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import text, Table, Column, Integer, String, Boolean, TIMESTAMP, Text, MetaData
from sqlalchemy.orm import Session

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.manager_evaluation import (
    ManagerEvaluation,
    ManagerDeveloperAssignment,
)


class ManagerEvaluationRepository:
    """Repository for managing manager evaluations and assignments."""

    def __init__(self, session: Session):
        """Initialize repository.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session

    # ==================== Manager-Developer Assignments ====================

    def assign_manager_to_developer(
        self,
        manager_name: str,
        developer_name: str,
        department: str,
        project_key: Optional[str] = None,
    ) -> ManagerDeveloperAssignment:
        """Assign a manager to evaluate a developer.
        
        Args:
            manager_name: Name of the manager
            developer_name: Name of the developer
            department: Department name
            project_key: Optional project key for project-specific assignment
            
        Returns:
            Created assignment
        """
        query = text("""
            INSERT INTO manager_developer_assignments 
            (manager_name, developer_name, department, project_key, is_active, created_at, updated_at)
            VALUES (:manager_name, :developer_name, :department, :project_key, TRUE, :now, :now)
            ON CONFLICT (manager_name, developer_name, project_key) 
            WHERE is_active = TRUE
            DO UPDATE SET 
                is_active = TRUE,
                department = EXCLUDED.department,
                updated_at = EXCLUDED.updated_at
            RETURNING id, manager_name, developer_name, department, project_key, is_active, created_at, updated_at
        """)
        
        result = self.session.execute(
            query,
            {
                "manager_name": manager_name,
                "developer_name": developer_name,
                "department": department,
                "project_key": project_key,
                "now": datetime.now(),
            }
        )
        self.session.commit()
        
        row = result.fetchone()
        return ManagerDeveloperAssignment(
            id=row[0],
            manager_name=row[1],
            developer_name=row[2],
            department=row[3],
            project_key=row[4],
            is_active=row[5],
            created_at=row[6],
            updated_at=row[7],
        )

    def get_developers_for_manager(
        self,
        manager_name: str,
        active_only: bool = True,
        project_key: Optional[str] = None,
    ) -> List[ManagerDeveloperAssignment]:
        """Get all developers assigned to a manager.
        
        Args:
            manager_name: Name of the manager
            active_only: Only return active assignments
            project_key: Optional filter by project
            
        Returns:
            List of assignments
        """
        query = text("""
            SELECT id, manager_name, developer_name, department, project_key, is_active, created_at, updated_at
            FROM manager_developer_assignments
            WHERE manager_name = :manager_name
            AND (:active_only = FALSE OR is_active = TRUE)
            AND (:project_key IS NULL OR project_key = :project_key)
            ORDER BY developer_name
        """)
        
        result = self.session.execute(
            query,
            {"manager_name": manager_name, "active_only": active_only, "project_key": project_key}
        )
        
        return [
            ManagerDeveloperAssignment(
                id=row[0],
                manager_name=row[1],
                developer_name=row[2],
                department=row[3],
                project_key=row[4],
                is_active=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            for row in result
        ]

    def get_managers_for_developer(
        self,
        developer_name: str,
        active_only: bool = True,
        project_key: Optional[str] = None,
    ) -> List[ManagerDeveloperAssignment]:
        """Get all managers assigned to evaluate a developer.
        
        Args:
            developer_name: Name of the developer
            active_only: Only return active assignments
            project_key: Optional filter by project
            
        Returns:
            List of assignments
        """
        query = text("""
            SELECT id, manager_name, developer_name, department, project_key, is_active, created_at, updated_at
            FROM manager_developer_assignments
            WHERE developer_name = :developer_name
            AND (:active_only = FALSE OR is_active = TRUE)
            AND (:project_key IS NULL OR project_key = :project_key)
            ORDER BY manager_name
        """)
        
        result = self.session.execute(
            query,
            {"developer_name": developer_name, "active_only": active_only, "project_key": project_key}
        )
        
        return [
            ManagerDeveloperAssignment(
                id=row[0],
                manager_name=row[1],
                developer_name=row[2],
                department=row[3],
                project_key=row[4],
                is_active=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            for row in result
        ]

    def deactivate_assignment(
        self,
        manager_name: str,
        developer_name: str,
        project_key: Optional[str] = None,
    ) -> None:
        """Deactivate a manager-developer assignment.
        
        Args:
            manager_name: Name of the manager
            developer_name: Name of the developer
            project_key: Optional project key to deactivate specific assignment
        """
        query = text("""
            UPDATE manager_developer_assignments
            SET is_active = FALSE, updated_at = :now
            WHERE manager_name = :manager_name 
            AND developer_name = :developer_name
            AND (:project_key IS NULL OR project_key = :project_key)
        """)
        
        self.session.execute(
            query,
            {
                "manager_name": manager_name,
                "developer_name": developer_name,
                "project_key": project_key,
                "now": datetime.now(),
            }
        )
        self.session.commit()

    def get_all_active_assignments(self) -> List[ManagerDeveloperAssignment]:
        """Get all active manager-developer assignments.
        
        Used for creating monthly evaluation records.
        
        Returns:
            List of all active assignments
        """
        query = text("""
            SELECT id, manager_name, developer_name, department, project_key, is_active, created_at, updated_at
            FROM manager_developer_assignments
            WHERE is_active = TRUE
            ORDER BY department, developer_name
        """)
        
        result = self.session.execute(query)
        
        return [
            ManagerDeveloperAssignment(
                id=row[0],
                manager_name=row[1],
                developer_name=row[2],
                department=row[3],
                project_key=row[4],
                is_active=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            for row in result
        ]

    # ==================== Manager Evaluations ====================

    def save_evaluation(self, evaluation: ManagerEvaluation) -> ManagerEvaluation:
        """Save or update a manager evaluation.
        
        Args:
            evaluation: Evaluation to save
            
        Returns:
            Saved evaluation with updated fields
        """
        now = datetime.now()
        
        # Calculate total score if not provided
        total_score = evaluation.total_manager_score
        if total_score is None or total_score == 0:
            total_score = ManagerEvaluation.calculate_total_score(
                evaluation.collaboration_score,
                evaluation.alignment_score,
            )
        
        query = text("""
            INSERT INTO manager_evaluations 
            (sprint_id, developer_name, manager_name, evaluation_month,
             collaboration_score, alignment_score, total_manager_score,
             comments, evaluated_at, created_at, updated_at)
            VALUES (:sprint_id, :developer_name, :manager_name, :evaluation_month,
                    :collaboration_score, :alignment_score, :total_manager_score,
                    :comments, :evaluated_at, :created_at, :updated_at)
            ON CONFLICT (sprint_id, developer_name, manager_name)
            DO UPDATE SET
                collaboration_score = EXCLUDED.collaboration_score,
                alignment_score = EXCLUDED.alignment_score,
                total_manager_score = EXCLUDED.total_manager_score,
                comments = EXCLUDED.comments,
                evaluated_at = EXCLUDED.evaluated_at,
                updated_at = EXCLUDED.updated_at
            RETURNING id, sprint_id, developer_name, manager_name, evaluation_month,
                      collaboration_score, alignment_score, total_manager_score,
                      comments, evaluated_at, created_at, updated_at
        """)
        
        result = self.session.execute(
            query,
            {
                "sprint_id": evaluation.sprint_id,
                "developer_name": evaluation.developer_name,
                "manager_name": evaluation.manager_name,
                "evaluation_month": evaluation.evaluation_month,
                "collaboration_score": evaluation.collaboration_score,
                "alignment_score": evaluation.alignment_score,
                "total_manager_score": total_score,
                "comments": evaluation.comments,
                "evaluated_at": evaluation.evaluated_at or now,
                "created_at": evaluation.created_at or now,
                "updated_at": now,
            }
        )
        self.session.commit()
        
        row = result.fetchone()
        return ManagerEvaluation(
            id=row[0],
            sprint_id=row[1],
            developer_name=row[2],
            manager_name=row[3],
            evaluation_month=row[4],
            collaboration_score=row[5],
            alignment_score=row[6],
            total_manager_score=row[7],
            comments=row[8],
            evaluated_at=row[9],
            created_at=row[10],
            updated_at=row[11],
        )

    def get_evaluations_for_developer(
        self,
        sprint_id: int,
        developer_name: str,
    ) -> List[ManagerEvaluation]:
        """Get all manager evaluations for a developer in a sprint.
        
        Args:
            sprint_id: Sprint ID
            developer_name: Developer name
            
        Returns:
            List of evaluations from different managers
        """
        query = text("""
            SELECT id, sprint_id, developer_name, manager_name, evaluation_month,
                   collaboration_score, alignment_score, total_manager_score,
                   comments, evaluated_at, created_at, updated_at
            FROM manager_evaluations
            WHERE sprint_id = :sprint_id AND developer_name = :developer_name
            ORDER BY evaluated_at DESC
        """)
        
        result = self.session.execute(
            query,
            {"sprint_id": sprint_id, "developer_name": developer_name}
        )
        
        return [
            ManagerEvaluation(
                id=row[0],
                sprint_id=row[1],
                developer_name=row[2],
                manager_name=row[3],
                evaluation_month=row[4],
                collaboration_score=row[5],
                alignment_score=row[6],
                total_manager_score=row[7],
                comments=row[8],
                evaluated_at=row[9],
                created_at=row[10],
                updated_at=row[11],
            )
            for row in result
        ]

    def get_average_manager_score(
        self,
        sprint_id: int,
        developer_name: str,
    ) -> Optional[float]:
        """Get average manager score for a developer in a sprint.
        
        Multiple managers may evaluate the same developer.
        This returns the average of all their scores.
        
        Args:
            sprint_id: Sprint ID
            developer_name: Developer name
            
        Returns:
            Average manager score or None if no evaluations exist
        """
        query = text("""
            SELECT AVG(total_manager_score) as avg_score
            FROM manager_evaluations
            WHERE sprint_id = :sprint_id AND developer_name = :developer_name
        """)
        
        result = self.session.execute(
            query,
            {"sprint_id": sprint_id, "developer_name": developer_name}
        )
        
        row = result.fetchone()
        return float(row[0]) if row and row[0] is not None else None

    def get_evaluations_by_manager(
        self,
        manager_name: str,
        evaluation_month: Optional[str] = None,
    ) -> List[ManagerEvaluation]:
        """Get all evaluations submitted by a manager.
        
        Args:
            manager_name: Manager name
            evaluation_month: Optional month filter (YYYY-MM)
            
        Returns:
            List of evaluations
        """
        query = text("""
            SELECT id, sprint_id, developer_name, manager_name, evaluation_month,
                   collaboration_score, alignment_score, total_manager_score,
                   comments, evaluated_at, created_at, updated_at
            FROM manager_evaluations
            WHERE manager_name = :manager_name
            AND (:evaluation_month IS NULL OR evaluation_month = :evaluation_month)
            ORDER BY evaluated_at DESC
        """)
        
        result = self.session.execute(
            query,
            {"manager_name": manager_name, "evaluation_month": evaluation_month}
        )
        
        return [
            ManagerEvaluation(
                id=row[0],
                sprint_id=row[1],
                developer_name=row[2],
                manager_name=row[3],
                evaluation_month=row[4],
                collaboration_score=row[5],
                alignment_score=row[6],
                total_manager_score=row[7],
                comments=row[8],
                evaluated_at=row[9],
                created_at=row[10],
                updated_at=row[11],
            )
            for row in result
        ]

    def get_evaluation(
        self,
        sprint_id: int,
        developer_name: str,
        manager_name: str,
    ) -> Optional[ManagerEvaluation]:
        """Get a specific evaluation.
        
        Args:
            sprint_id: Sprint ID
            developer_name: Developer name
            manager_name: Manager name
            
        Returns:
            Evaluation or None if not found
        """
        query = text("""
            SELECT id, sprint_id, developer_name, manager_name, evaluation_month,
                   collaboration_score, alignment_score, total_manager_score,
                   comments, evaluated_at, created_at, updated_at
            FROM manager_evaluations
            WHERE sprint_id = :sprint_id 
            AND developer_name = :developer_name
            AND manager_name = :manager_name
        """)
        
        result = self.session.execute(
            query,
            {
                "sprint_id": sprint_id,
                "developer_name": developer_name,
                "manager_name": manager_name,
            }
        )
        
        row = result.fetchone()
        if not row:
            return None
        
        return ManagerEvaluation(
            id=row[0],
            sprint_id=row[1],
            developer_name=row[2],
            manager_name=row[3],
            evaluation_month=row[4],
            collaboration_score=row[5],
            alignment_score=row[6],
            total_manager_score=row[7],
            comments=row[8],
            evaluated_at=row[9],
            created_at=row[10],
            updated_at=row[11],
        )

    def create_placeholder_evaluation(
        self,
        sprint_id: int,
        developer_name: str,
        manager_name: str,
        evaluation_month: str,
    ) -> ManagerEvaluation:
        """Create a placeholder evaluation record with null scores.
        
        This is used to pre-create records at the end of each month that
        managers will fill in later.
        
        Args:
            sprint_id: Sprint ID
            developer_name: Developer name
            manager_name: Manager name
            evaluation_month: Month in YYYY-MM format
            
        Returns:
            Created placeholder evaluation
        """
        query = text("""
            INSERT INTO manager_evaluations 
            (sprint_id, developer_name, manager_name, evaluation_month,
             collaboration_score, alignment_score, total_manager_score,
             created_at, updated_at)
            VALUES (:sprint_id, :developer_name, :manager_name, :evaluation_month,
                    NULL, NULL, NULL, :now, :now)
            RETURNING id, sprint_id, developer_name, manager_name, evaluation_month,
                      collaboration_score, alignment_score, total_manager_score,
                      comments, evaluated_at, created_at, updated_at
        """)
        
        result = self.session.execute(
            query,
            {
                "sprint_id": sprint_id,
                "developer_name": developer_name,
                "manager_name": manager_name,
                "evaluation_month": evaluation_month,
                "now": datetime.now(),
            }
        )
        self.session.commit()
        
        row = result.fetchone()
        return ManagerEvaluation(
            id=row[0],
            sprint_id=row[1],
            developer_name=row[2],
            manager_name=row[3],
            evaluation_month=row[4],
            collaboration_score=row[5],
            alignment_score=row[6],
            total_manager_score=row[7],
            comments=row[8],
            evaluated_at=row[9],
            created_at=row[10],
            updated_at=row[11],
        )
