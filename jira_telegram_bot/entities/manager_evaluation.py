"""Manager evaluation entities."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from jira_telegram_bot.entities.member_project_role import MemberProjectRole


class ManagerDeveloperAssignment(BaseModel):
    """Assignment of a manager to evaluate a developer.
    
    Attributes:
        id: Primary key
        manager_name: Name of the manager
        developer_name: Name of the developer being evaluated
        department: Department name
        project_key: Project key for project-specific assignments
        is_active: Whether this assignment is currently active
        created_at: When assignment was created
        updated_at: When assignment was last updated
    """
    
    id: Optional[int] = None
    manager_name: str
    developer_name: str
    department: str
    project_key: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ManagerEvaluation(BaseModel):
    """Manager's evaluation of a developer's performance.
    
    This represents the 30% qualitative component of the total evaluation score.
    
    Attributes:
        id: Primary key
        sprint_id: ID of the sprint being evaluated
        developer_name: Name of the developer being evaluated
        manager_name: Name of the evaluating manager
        evaluation_month: Month of evaluation in YYYY-MM format
        collaboration_score: Score for collaboration with tech lead (0-100)
        alignment_score: Score for alignment with company goals (0-100)
        total_manager_score: Combined manager score (0-100)
        comments: Optional comments from manager
        evaluated_at: When evaluation was submitted
        created_at: When record was created
        updated_at: When record was last updated
    """
    
    id: Optional[int] = None
    sprint_id: int
    developer_name: str
    manager_name: str
    evaluation_month: str = Field(..., description="Format: YYYY-MM")
    collaboration_score: Optional[int] = Field(None, ge=0, le=100, description="Cooperation with tech lead (15%)")
    alignment_score: Optional[int] = Field(None, ge=0, le=100, description="Alignment with company goals (15%)")
    total_manager_score: Optional[int] = Field(None, ge=0, le=100, description="Combined manager evaluation score")
    comments: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def calculate_total_score(cls, collaboration_score: int, alignment_score: int) -> int:
        """Calculate total manager score from component scores.
        
        Each component is worth 50% of the total manager score.
        
        Args:
            collaboration_score: Score for collaboration (0-100)
            alignment_score: Score for alignment (0-100)
            
        Returns:
            Total manager score (0-100)
        """
        return int((collaboration_score * 0.5) + (alignment_score * 0.5))


class DeveloperPerformanceData(BaseModel):
    """Developer performance data shown to managers for evaluation.
    
    This aggregates system metrics and work items to help managers
    make informed evaluation decisions.
    
    Attributes:
        developer_name: Name of the developer
        sprint_id: Sprint ID
        sprint_name: Sprint name
        department: Department name
        system_score: Calculated system score (70% component)
        deadline_score: Score for deadline adherence
        worklog_score: Score for time logging
        priority_score: Score for high priority task completion
        quality_score: Score for code quality (bug metrics)
        development_count: Number of development tasks
        bug_count: Number of bugs
        support_count: Number of support tasks
        high_priority_completed: Number of high priority tasks completed
        registered_hours: Hours logged in sprint
        expected_hours: Expected hours for sprint
        avg_deadline_delivery_days: Average delivery relative to deadline
        stories_worked_on: List of story keys/summaries
        features_delivered: List of features delivered
        review_back_count: Number of times sent back from review
        existing_manager_score: Existing manager evaluation if any
    """
    
    developer_name: str
    sprint_id: int
    sprint_name: str
    department: str
    evaluation_month: str
    
    # Role information
    member_role: Optional[MemberProjectRole] = None
    
    # System scores
    system_score: float
    deadline_score: float
    worklog_score: float
    priority_score: float
    quality_score: float
    
    # Metrics
    development_count: int
    bug_count: int
    support_count: int
    high_priority_completed: int
    registered_hours: float
    expected_hours: int
    avg_deadline_delivery_days: Optional[float]
    review_back_count: int
    
    # Work items
    stories_worked_on: list[str] = Field(default_factory=list)
    features_delivered: list[str] = Field(default_factory=list)
    
    # Existing evaluation
    existing_manager_score: Optional[int] = None
    existing_collaboration_score: Optional[int] = None
    existing_alignment_score: Optional[int] = None
    existing_comments: Optional[str] = None
