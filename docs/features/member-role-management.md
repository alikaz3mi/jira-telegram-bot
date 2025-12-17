# Member Role Management System

## Overview

The Member Role Management system tracks member roles and ranks across projects. Since members can be involved in multiple projects with different roles in each, this system provides flexible role assignment at both the project level and overall organizational level.

## Architecture

### Database Schema

#### `member_project_roles` Table

```sql
CREATE TABLE member_project_roles (
    id SERIAL PRIMARY KEY,
    member_id VARCHAR(255) NOT NULL,           -- Jira account ID
    project_key VARCHAR(50),                    -- NULL for overall role
    role VARCHAR(100) NOT NULL,                 -- e.g., Developer, Lead, QA
    rank VARCHAR(50),                           -- e.g., Junior, Mid, Senior, Principal
    is_overall BOOLEAN DEFAULT FALSE,           -- TRUE for overall role
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Indexes

1. `idx_member_project_roles_member_id` - Fast lookups by member
2. `idx_member_project_roles_project_key` - Project-based queries
3. `idx_member_project_roles_unique` - Unique constraint: one role per member per project
4. `idx_member_project_roles_overall_unique` - Unique constraint: one overall role per member

### Entities

#### `MemberProjectRole`

Represents a single role assignment:

```python
class MemberProjectRole(BaseModel):
    id: Optional[int]
    member_id: str              # Jira account ID
    project_key: Optional[str]  # None for overall role
    role: str                   # Role name
    rank: Optional[str]         # Rank (Junior, Mid, Senior, Principal)
    is_overall: bool = False    # Whether this is overall role
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
```

Methods:
- `is_project_specific()` - Check if role is for a specific project
- `display_name()` - Generate human-readable role description

#### `MemberRoleSummary`

Aggregates all roles for a member:

```python
class MemberRoleSummary(BaseModel):
    member_id: str
    overall_role: Optional[MemberProjectRole]
    project_roles: list[MemberProjectRole]
```

Methods:
- `has_overall_role()` - Check if overall role exists
- `get_role_for_project(project_key)` - Get role for specific project
- `get_effective_role(project_key)` - Get most specific applicable role (project-specific or overall)

## Implementation

### Repository

**File**: `jira_telegram_bot/adapters/repositories/postgres/member_project_role_repository.py`

#### Key Methods

##### Set Overall Role
```python
def set_overall_role(
    member_id: str, 
    role: str, 
    rank: Optional[str] = None
) -> MemberProjectRole
```

Sets or updates a member's overall role (applies across all projects).

##### Set Project Role
```python
def set_project_role(
    member_id: str, 
    project_key: str, 
    role: str, 
    rank: Optional[str] = None
) -> MemberProjectRole
```

Sets or updates a member's role in a specific project.

##### Get Member Role Summary
```python
def get_member_role_summary(member_id: str) -> MemberRoleSummary
```

Returns complete role information including overall and all project-specific roles.

##### Get Project Members
```python
def get_members_by_project(project_key: str) -> list[MemberProjectRole]
```

Returns all members with roles in a specific project.

##### Get Members by Role
```python
def get_members_by_role(role: str) -> list[MemberProjectRole]
```

Returns all members with a specific role (across all projects).

### Use Case

**File**: `jira_telegram_bot/use_cases/team_evaluation/manage_member_roles.py`

The `ManageMemberRolesUseCase` provides high-level operations for managing member roles:

- `set_overall_role()` - Set member's overall role
- `set_project_role()` - Set member's role in a project
- `get_member_roles()` - Get complete role summary
- `get_effective_role()` - Get most specific applicable role
- `delete_project_role()` - Remove project-specific role
- `delete_all_roles()` - Remove all roles for a member
- `get_project_members()` - Get all members in a project
- `get_members_by_role()` - Get all members with a role

## Integration with Manager Evaluation

The role information is integrated into the manager evaluation system:

**File**: `jira_telegram_bot/use_cases/team_evaluation/get_developer_performance_for_evaluation.py`

When managers evaluate developers, the `DeveloperPerformanceData` now includes:

```python
class DeveloperPerformanceData(BaseModel):
    # ... other fields ...
    member_role: Optional[MemberProjectRole] = None
```

The system automatically:
1. Looks up developer's account ID from their name
2. Finds the project key from the sprint
3. Returns project-specific role if available, otherwise overall role

This provides managers with context about the developer's role and rank when making evaluations.

## Usage Examples

### Example 1: Set Overall Role

```python
from jira_telegram_bot.use_cases.team_evaluation.manage_member_roles import (
    ManageMemberRolesUseCase
)

# Set a member's overall role
use_case.set_overall_role(
    member_id="account_12345",
    role="Developer",
    rank="Senior"
)
```

### Example 2: Set Project-Specific Role

```python
# Member is Senior Developer overall, but Lead in a specific project
use_case.set_project_role(
    member_id="account_12345",
    project_key="PROJ1",
    role="Lead Developer",
    rank="Senior"
)
```

### Example 3: Get Effective Role

```python
# Get effective role for a context
role = use_case.get_effective_role(
    member_id="account_12345",
    project_key="PROJ1"  # Returns project-specific role if exists
)

# If no project key, returns overall role
overall_role = use_case.get_effective_role(
    member_id="account_12345"
)
```

### Example 4: Get All Project Members

```python
# Get all members working on a project
members = use_case.get_project_members("PROJ1")

for member in members:
    print(f"{member.display_name()}")
    # Output: "Senior Lead Developer in PROJ1"
```

### Example 5: Get Members by Role

```python
# Find all QA members across all projects
qa_members = use_case.get_members_by_role("QA")
```

## Migration

**Migration**: `migration_009_add_member_project_roles.py`

The migration creates:
- `member_project_roles` table
- 5 indexes for performance and constraints
- Unique constraints ensuring data integrity

To run the migration:

```bash
python scripts/run_migrations.py
```

## Testing

### Repository Tests

**File**: `tests/use_cases/test_member_project_role_repository.py`

- 18 unit tests covering all repository methods
- Tests for entity methods
- Tests for MemberRoleSummary functionality
- 100% code coverage

### Use Case Tests

**File**: `tests/use_cases/test_manage_member_roles.py`

- 9 unit tests covering all use case methods
- Tests for effective role resolution
- Tests for role deletion
- Mock-based testing for isolation

Run tests:

```bash
python -m pytest tests/use_cases/test_member_project_role_repository.py -v
python tests/use_cases/test_manage_member_roles.py
```

## API Endpoints (Future)

Once FastAPI endpoints are created, the system will support:

- `POST /api/members/{member_id}/overall-role` - Set overall role
- `POST /api/members/{member_id}/project-roles` - Set project role
- `GET /api/members/{member_id}/roles` - Get all roles
- `GET /api/projects/{project_key}/members` - Get project members
- `DELETE /api/members/{member_id}/project-roles/{project_key}` - Remove project role

## Benefits

1. **Flexibility**: Members can have different roles in different projects
2. **Context-Aware**: Manager evaluations automatically include role information
3. **Clean Data Model**: Separate table prevents denormalization
4. **Audit Trail**: Created/updated timestamps for tracking changes
5. **Performance**: Proper indexes for fast queries
6. **Type Safety**: Strong typing with Pydantic models

## Future Enhancements

1. **Role Hierarchy**: Define role hierarchy (e.g., Lead > Senior > Mid > Junior)
2. **Role Permissions**: Map roles to permissions
3. **Role History**: Track role changes over time
4. **Automatic Assignment**: Auto-assign roles based on Jira project membership
5. **Role Templates**: Predefined role templates for common setups

## Related Documentation

- [Manager Evaluation Implementation](manager-evaluation-implementation.md)
- [Team Evaluation System](../TODO.txt)
- [Database Schema](../mongodb-database-ecosystem.md)
