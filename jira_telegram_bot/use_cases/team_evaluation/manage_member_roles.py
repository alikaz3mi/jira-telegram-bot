"""Use case for managing member project roles."""

from typing import Optional

from jira_telegram_bot.adapters.repositories.postgres.member_project_role_repository import (
    MemberProjectRoleRepository,
)
from jira_telegram_bot.entities.member_project_role import (
    MemberProjectRole,
    MemberRoleSummary,
)


class ManageMemberRolesUseCase:
    """Use case for managing member roles across projects."""

    def __init__(self, member_role_repo: MemberProjectRoleRepository) -> None:
        """Initialize use case.
        
        Args:
            member_role_repo: Repository for member project roles.
        """
        self.member_role_repo = member_role_repo

    def set_overall_role(
        self, member_id: str, role: str, rank: Optional[str] = None
    ) -> MemberProjectRole:
        """Set or update a member's overall role.
        
        Args:
            member_id: Jira account ID of the member.
            role: Role name (e.g., Developer, Lead, QA).
            rank: Optional rank (e.g., Junior, Mid, Senior, Principal).
            
        Returns:
            Created or updated MemberProjectRole.
        """
        return self.member_role_repo.set_overall_role(
            member_id=member_id, role=role, rank=rank
        )

    def set_project_role(
        self,
        member_id: str,
        project_key: str,
        role: str,
        rank: Optional[str] = None,
    ) -> MemberProjectRole:
        """Set or update a member's role in a specific project.
        
        Args:
            member_id: Jira account ID of the member.
            project_key: Jira project key.
            role: Role name in this project.
            rank: Optional rank in this project.
            
        Returns:
            Created or updated MemberProjectRole.
        """
        return self.member_role_repo.set_project_role(
            member_id=member_id, project_key=project_key, role=role, rank=rank
        )

    def get_member_roles(self, member_id: str) -> MemberRoleSummary:
        """Get complete role summary for a member.
        
        Args:
            member_id: Jira account ID of the member.
            
        Returns:
            MemberRoleSummary with overall role and all project roles.
        """
        return self.member_role_repo.get_member_role_summary(member_id)

    def get_effective_role(
        self, member_id: str, project_key: Optional[str] = None
    ) -> Optional[MemberProjectRole]:
        """Get effective role for a member in a context.
        
        This returns the project-specific role if available, otherwise
        falls back to the overall role.
        
        Args:
            member_id: Jira account ID of the member.
            project_key: Optional project key for context.
            
        Returns:
            Most specific applicable role, or None if no role defined.
        """
        summary = self.member_role_repo.get_member_role_summary(member_id)
        return summary.get_effective_role(project_key)

    def delete_project_role(self, member_id: str, project_key: str) -> bool:
        """Delete a member's role in a specific project.
        
        Args:
            member_id: Jira account ID of the member.
            project_key: Jira project key.
            
        Returns:
            True if deleted, False if not found.
        """
        return self.member_role_repo.delete_project_role(member_id, project_key)

    def delete_all_roles(self, member_id: str) -> int:
        """Delete all roles for a member.
        
        Args:
            member_id: Jira account ID of the member.
            
        Returns:
            Number of roles deleted.
        """
        return self.member_role_repo.delete_all_roles(member_id)

    def get_project_members(self, project_key: str) -> list[MemberProjectRole]:
        """Get all members who have a role in a specific project.
        
        Args:
            project_key: Jira project key.
            
        Returns:
            List of MemberProjectRole for this project.
        """
        return self.member_role_repo.get_members_by_project(project_key)

    def get_members_by_role(self, role: str) -> list[MemberProjectRole]:
        """Get all members with a specific role.
        
        Args:
            role: Role name to search for.
            
        Returns:
            List of MemberProjectRole matching the role.
        """
        return self.member_role_repo.get_members_by_role(role)
