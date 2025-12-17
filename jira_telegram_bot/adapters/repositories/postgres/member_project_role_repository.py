"""Repository for managing member project roles."""

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from jira_telegram_bot.entities.member_project_role import (
    MemberProjectRole,
    MemberRoleSummary,
)


class MemberProjectRoleRepository:
    """Repository for member project role operations."""

    def __init__(self, session: Session) -> None:
        """Initialize repository.
        
        Args:
            session: SQLAlchemy database session.
        """
        self.session = session

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
        # Check if overall role exists
        existing = self._get_overall_role(member_id)
        
        if existing:
            # Update existing
            query = text(
                """
                UPDATE member_project_roles 
                SET role = :role, rank = :rank, updated_at = :updated_at
                WHERE member_id = :member_id AND is_overall = TRUE
                RETURNING id, member_id, project_key, role, rank, is_overall, created_at, updated_at
                """
            )
            result = self.session.execute(
                query,
                {
                    "member_id": member_id,
                    "role": role,
                    "rank": rank,
                    "updated_at": datetime.utcnow(),
                },
            )
        else:
            # Create new
            query = text(
                """
                INSERT INTO member_project_roles 
                (member_id, project_key, role, rank, is_overall, created_at, updated_at)
                VALUES (:member_id, NULL, :role, :rank, TRUE, :created_at, :updated_at)
                RETURNING id, member_id, project_key, role, rank, is_overall, created_at, updated_at
                """
            )
            now = datetime.utcnow()
            result = self.session.execute(
                query,
                {
                    "member_id": member_id,
                    "role": role,
                    "rank": rank,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        
        self.session.commit()
        row = result.fetchone()
        return MemberProjectRole(
            id=row[0],
            member_id=row[1],
            project_key=row[2],
            role=row[3],
            rank=row[4],
            is_overall=row[5],
            created_at=row[6],
            updated_at=row[7],
        )

    def set_project_role(
        self, member_id: str, project_key: str, role: str, rank: Optional[str] = None
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
        # Check if project role exists
        existing = self._get_project_role(member_id, project_key)
        
        if existing:
            # Update existing
            query = text(
                """
                UPDATE member_project_roles 
                SET role = :role, rank = :rank, updated_at = :updated_at
                WHERE member_id = :member_id AND project_key = :project_key
                RETURNING id, member_id, project_key, role, rank, is_overall, created_at, updated_at
                """
            )
            result = self.session.execute(
                query,
                {
                    "member_id": member_id,
                    "project_key": project_key,
                    "role": role,
                    "rank": rank,
                    "updated_at": datetime.utcnow(),
                },
            )
        else:
            # Create new
            query = text(
                """
                INSERT INTO member_project_roles 
                (member_id, project_key, role, rank, is_overall, created_at, updated_at)
                VALUES (:member_id, :project_key, :role, :rank, FALSE, :created_at, :updated_at)
                RETURNING id, member_id, project_key, role, rank, is_overall, created_at, updated_at
                """
            )
            now = datetime.utcnow()
            result = self.session.execute(
                query,
                {
                    "member_id": member_id,
                    "project_key": project_key,
                    "role": role,
                    "rank": rank,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        
        self.session.commit()
        row = result.fetchone()
        return MemberProjectRole(
            id=row[0],
            member_id=row[1],
            project_key=row[2],
            role=row[3],
            rank=row[4],
            is_overall=row[5],
            created_at=row[6],
            updated_at=row[7],
        )

    def get_member_role_summary(self, member_id: str) -> MemberRoleSummary:
        """Get complete role summary for a member.
        
        Args:
            member_id: Jira account ID of the member.
            
        Returns:
            MemberRoleSummary with overall role and all project roles.
        """
        query = text(
            """
            SELECT id, member_id, project_key, role, rank, is_overall, created_at, updated_at
            FROM member_project_roles
            WHERE member_id = :member_id
            ORDER BY is_overall DESC, project_key ASC
            """
        )
        result = self.session.execute(query, {"member_id": member_id})
        
        overall_role = None
        project_roles = []
        
        for row in result:
            role = MemberProjectRole(
                id=row[0],
                member_id=row[1],
                project_key=row[2],
                role=row[3],
                rank=row[4],
                is_overall=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            
            if role.is_overall:
                overall_role = role
            else:
                project_roles.append(role)
        
        return MemberRoleSummary(
            member_id=member_id, overall_role=overall_role, project_roles=project_roles
        )

    def get_project_role(
        self, member_id: str, project_key: str
    ) -> Optional[MemberProjectRole]:
        """Get member's role for a specific project.
        
        Args:
            member_id: Jira account ID of the member.
            project_key: Jira project key.
            
        Returns:
            MemberProjectRole if found, None otherwise.
        """
        return self._get_project_role(member_id, project_key)

    def get_overall_role(self, member_id: str) -> Optional[MemberProjectRole]:
        """Get member's overall role.
        
        Args:
            member_id: Jira account ID of the member.
            
        Returns:
            MemberProjectRole if found, None otherwise.
        """
        return self._get_overall_role(member_id)

    def delete_project_role(self, member_id: str, project_key: str) -> bool:
        """Delete a member's role in a specific project.
        
        Args:
            member_id: Jira account ID of the member.
            project_key: Jira project key.
            
        Returns:
            True if deleted, False if not found.
        """
        query = text(
            """
            DELETE FROM member_project_roles
            WHERE member_id = :member_id AND project_key = :project_key
            """
        )
        result = self.session.execute(
            query, {"member_id": member_id, "project_key": project_key}
        )
        self.session.commit()
        return result.rowcount > 0

    def delete_all_roles(self, member_id: str) -> int:
        """Delete all roles for a member (both overall and project-specific).
        
        Args:
            member_id: Jira account ID of the member.
            
        Returns:
            Number of roles deleted.
        """
        query = text(
            """
            DELETE FROM member_project_roles
            WHERE member_id = :member_id
            """
        )
        result = self.session.execute(query, {"member_id": member_id})
        self.session.commit()
        return result.rowcount

    def get_members_by_project(self, project_key: str) -> list[MemberProjectRole]:
        """Get all members who have a role in a specific project.
        
        Args:
            project_key: Jira project key.
            
        Returns:
            List of MemberProjectRole for this project.
        """
        query = text(
            """
            SELECT id, member_id, project_key, role, rank, is_overall, created_at, updated_at
            FROM member_project_roles
            WHERE project_key = :project_key
            ORDER BY rank ASC, role ASC
            """
        )
        result = self.session.execute(query, {"project_key": project_key})
        
        roles = []
        for row in result:
            roles.append(
                MemberProjectRole(
                    id=row[0],
                    member_id=row[1],
                    project_key=row[2],
                    role=row[3],
                    rank=row[4],
                    is_overall=row[5],
                    created_at=row[6],
                    updated_at=row[7],
                )
            )
        return roles

    def get_members_by_role(self, role: str) -> list[MemberProjectRole]:
        """Get all members with a specific role (across all projects).
        
        Args:
            role: Role name to search for.
            
        Returns:
            List of MemberProjectRole matching the role.
        """
        query = text(
            """
            SELECT id, member_id, project_key, role, rank, is_overall, created_at, updated_at
            FROM member_project_roles
            WHERE role = :role
            ORDER BY project_key ASC, rank ASC
            """
        )
        result = self.session.execute(query, {"role": role})
        
        roles = []
        for row in result:
            roles.append(
                MemberProjectRole(
                    id=row[0],
                    member_id=row[1],
                    project_key=row[2],
                    role=row[3],
                    rank=row[4],
                    is_overall=row[5],
                    created_at=row[6],
                    updated_at=row[7],
                )
            )
        return roles

    def _get_overall_role(self, member_id: str) -> Optional[MemberProjectRole]:
        """Internal method to get overall role."""
        query = text(
            """
            SELECT id, member_id, project_key, role, rank, is_overall, created_at, updated_at
            FROM member_project_roles
            WHERE member_id = :member_id AND is_overall = TRUE
            """
        )
        result = self.session.execute(query, {"member_id": member_id})
        row = result.fetchone()
        
        if row:
            return MemberProjectRole(
                id=row[0],
                member_id=row[1],
                project_key=row[2],
                role=row[3],
                rank=row[4],
                is_overall=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
        return None

    def _get_project_role(
        self, member_id: str, project_key: str
    ) -> Optional[MemberProjectRole]:
        """Internal method to get project role."""
        query = text(
            """
            SELECT id, member_id, project_key, role, rank, is_overall, created_at, updated_at
            FROM member_project_roles
            WHERE member_id = :member_id AND project_key = :project_key
            """
        )
        result = self.session.execute(
            query, {"member_id": member_id, "project_key": project_key}
        )
        row = result.fetchone()
        
        if row:
            return MemberProjectRole(
                id=row[0],
                member_id=row[1],
                project_key=row[2],
                role=row[3],
                rank=row[4],
                is_overall=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
        return None
