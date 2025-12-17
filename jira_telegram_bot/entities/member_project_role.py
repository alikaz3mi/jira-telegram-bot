"""Member project role entities."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MemberProjectRole(BaseModel):
    """Represents a member's role and rank in a project or overall.
    
    Members can have different roles in different projects, as well as
    an overall role that spans across all projects.
    """

    id: Optional[int] = None
    member_id: str = Field(..., description="Jira account ID of the member")
    project_key: Optional[str] = Field(
        None, description="Jira project key (None for overall role)"
    )
    role: str = Field(..., description="Role of the member (e.g., Developer, Lead, QA)")
    rank: Optional[str] = Field(
        None, description="Rank of the member (e.g., Junior, Mid, Senior, Principal)"
    )
    is_overall: bool = Field(
        False, description="Whether this is the overall role (not project-specific)"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True

    def is_project_specific(self) -> bool:
        """Check if this role is project-specific.
        
        Returns:
            True if role is for a specific project, False if overall.
        """
        return self.project_key is not None and not self.is_overall

    def display_name(self) -> str:
        """Generate a display name for this role.
        
        Returns:
            Human-readable role description.
        """
        rank_prefix = f"{self.rank} " if self.rank else ""
        project_suffix = f" in {self.project_key}" if self.project_key else " (Overall)"
        return f"{rank_prefix}{self.role}{project_suffix}"


class MemberRoleSummary(BaseModel):
    """Summary of a member's roles across all projects."""

    member_id: str
    overall_role: Optional[MemberProjectRole] = None
    project_roles: list[MemberProjectRole] = Field(default_factory=list)

    def has_overall_role(self) -> bool:
        """Check if member has an overall role defined.
        
        Returns:
            True if overall role exists.
        """
        return self.overall_role is not None

    def get_role_for_project(self, project_key: str) -> Optional[MemberProjectRole]:
        """Get member's role for a specific project.
        
        Args:
            project_key: Jira project key.
            
        Returns:
            Role for the project, or None if not found.
        """
        for role in self.project_roles:
            if role.project_key == project_key:
                return role
        return None

    def get_effective_role(self, project_key: Optional[str] = None) -> Optional[MemberProjectRole]:
        """Get effective role for a context (project-specific or overall).
        
        Args:
            project_key: Optional project key. If provided, looks for project-specific
                role first, then falls back to overall role.
                
        Returns:
            Most specific applicable role, or None if no role defined.
        """
        if project_key:
            project_role = self.get_role_for_project(project_key)
            if project_role:
                return project_role
        return self.overall_role
