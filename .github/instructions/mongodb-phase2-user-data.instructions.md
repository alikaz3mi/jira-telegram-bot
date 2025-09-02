---

mode: agent
description: Phase 2 - User & Session Data Migration - Move user-related data and session management to MongoDB
tools: [terminalLastCommand, codeBase, usages, testFailure, findTestFiles]
-----------------------------------------

# 🚀 Phase 2: User & Session Data Migration

Migrate user-related data and session management from local JSON files to MongoDB. This includes user configurations, Telegram post mappings, and session persistence, building upon the foundation established in Phase 1.

## 🎯 Goals

1. **User Configuration Migration**: Move `data/storage/user_config.json` to MongoDB
2. **Session Management**: Migrate Telegram post mappings (`data_store.json`) to MongoDB
3. **User Preferences**: Enhanced user preference management and versioning
4. **Session Persistence**: Robust session management across deployments
5. **User Activity Tracking**: Foundation for user analytics and audit trails

## 📊 Data to Migrate

### From JSON Files to MongoDB Collections:

1. **`user_configurations`** - User profiles, preferences, Jira mappings
2. **`telegram_sessions`** - Telegram post-to-Jira issue mappings
3. **`user_authentication`** - User permissions and access control
4. **`user_activity_logs`** - User action history (new capability)
5. **`session_metadata`** - Session state and context data

## 🏗️ Architecture Components

### 1. Enhanced User Entities
**Location**: `jira_telegram_bot/entities/users/`

* `user_profile.py` - Comprehensive user profile entity
* `user_preferences.py` - User preference and configuration entity
* `telegram_session.py` - Telegram session and mapping entity
* `user_activity.py` - User activity tracking entity

### 2. User Repository Interfaces
**Location**: `jira_telegram_bot/use_cases/interfaces/users/`

* `user_profile_repository_interface.py`
* `user_preferences_repository_interface.py`
* `telegram_session_repository_interface.py`
* `user_activity_repository_interface.py`

### 3. MongoDB User Repositories
**Location**: `jira_telegram_bot/adapters/repositories/mongodb/users/`

* `mongodb_user_profile_repository.py`
* `mongodb_user_preferences_repository.py`
* `mongodb_telegram_session_repository.py`
* `mongodb_user_activity_repository.py`

### 4. Migration Services
**Location**: `jira_telegram_bot/use_cases/migrations/`

* `user_data_migration_service.py` - Orchestrates user data migration
* `session_data_migration_service.py` - Handles session data migration
* `data_validation_service.py` - Validates migrated data integrity

## 📝 Implementation Details

### User Configuration Structure (Enhanced)
```python
UserProfile:
    user_id: str  # unique identifier
    telegram_username: str
    telegram_user_chat_id: int
    jira_username: str
    gitlab_username: Optional[str]
    google_sheet_name: str
    user_components: Dict[str, str]  # project -> component mapping
    created_at: datetime
    updated_at: datetime
    is_active: bool
    last_seen: Optional[datetime]
    version: int  # for optimistic locking

UserPreferences:
    user_id: str  # foreign key to UserProfile
    field_configurations: Dict[str, FieldConfig]
    notification_settings: NotificationConfig
    ui_preferences: UIConfig
    integrations: IntegrationConfig
    created_at: datetime
    updated_at: datetime
    version: int
```

### Telegram Session Structure
```python
TelegramSession:
    session_id: str  # unique identifier
    channel_post_id: int
    issue_key: str
    channel_chat_id: int
    group_chat_id: Optional[int]
    user_id: str  # reference to UserProfile
    message_type: str  # text, photo, video, document, etc.
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
```

### Migration Strategy Details

#### Dual-Write Pattern Implementation
1. **Phase 2a**: Read from JSON, write to both JSON and MongoDB
2. **Phase 2b**: Read from MongoDB with JSON fallback, write to both
3. **Phase 2c**: Read/write only MongoDB, maintain JSON backup
4. **Phase 2d**: Remove JSON dependencies completely

#### Data Validation Strategy
1. **Schema Validation**: Pydantic models ensure data integrity
2. **Cross-Reference Validation**: Ensure user relationships are maintained
3. **Performance Validation**: Compare query performance before/after
4. **Functional Validation**: End-to-end testing of user workflows

## 🔄 Migration Workflow

### 1. Enhanced Entity Design
1. Extend existing user entities with MongoDB-specific fields
2. Add versioning and audit trail capabilities
3. Implement data validation and serialization
4. Design indexes for query optimization

### 2. Repository Implementation
1. Implement MongoDB repositories for user data
2. Add caching layer for frequently accessed data
3. Implement atomic operations for data consistency
4. Add batch operations for bulk updates

### 3. Migration Service Development
1. Create migration orchestration service
2. Implement data transformation and validation
3. Add rollback and recovery mechanisms
4. Create data integrity verification

### 4. Backwards Compatibility Layer
1. Update existing UserConfig adapter to use MongoDB
2. Maintain API compatibility for existing code
3. Implement graceful fallback mechanisms
4. Add migration status tracking

### 5. Session Management Enhancement
1. Migrate TelegramPostDataStore to MongoDB
2. Add session expiration and cleanup
3. Implement session clustering for scaling
4. Add session analytics and monitoring

### 6. Testing and Validation
1. Comprehensive data migration testing
2. Performance benchmarking
3. Concurrent access testing
4. Data consistency validation

## 📋 Interactive Variables

* `${input:batch_size}` - Migration batch size (default: 50 users)
* `${input:enable_versioning}` - Enable user data versioning (default: true)
* `${input:session_ttl_days}` - Session TTL in days (default: 30)
* `${input:enable_caching}` - Enable user data caching (default: true)
* `${input:cache_ttl_seconds}` - Cache TTL in seconds (default: 300)
* `${input:enable_activity_tracking}` - Enable user activity tracking (default: true)
* `${input:migration_validation}` - Enable strict migration validation (default: true)
* `${input:backup_retention_days}` - JSON backup retention in days (default: 90)

## 🔧 Technical Implementation

### Enhanced User Repository Pattern
```python
class MongoDBUserProfileRepository(UserProfileRepositoryInterface):
    def __init__(self, connection: MongoDBConnection):
        super().__init__(connection, "user_profiles")
        self.cache = TTLCache(maxsize=1000, ttl=300)

    async def get_by_telegram_username(self, username: str) -> Optional[UserProfile]:
        # Cached lookup with fallback to database

    async def get_by_jira_username(self, jira_username: str) -> Optional[UserProfile]:
        # Support for multi-Jira environment lookups

    async def update_last_seen(self, user_id: str) -> None:
        # Efficient timestamp update without full document

    async def get_users_by_component(self, project: str, component: str) -> List[UserProfile]:
        # Query for team organization
```

### Session Management Service
```python
class TelegramSessionService:
    async def create_session(self, session_data: TelegramSessionCreate) -> TelegramSession:
        # Create session with automatic expiration

    async def get_session_by_post_id(self, post_id: int) -> Optional[TelegramSession]:
        # Quick session lookup with caching

    async def extend_session(self, session_id: str, ttl_days: int = 30) -> bool:
        # Extend session lifetime

    async def cleanup_expired_sessions(self) -> int:
        # Automated cleanup of expired sessions
```

### Migration Orchestration
```python
class UserDataMigrationService:
    async def migrate_user_configurations(self) -> MigrationResult:
        # Migrate user_config.json to MongoDB

    async def migrate_telegram_sessions(self) -> MigrationResult:
        # Migrate data_store.json to MongoDB

    async def validate_migration(self) -> ValidationResult:
        # Comprehensive data validation

    async def rollback_migration(self, checkpoint: str) -> bool:
        # Rollback to previous state
```

## 🧪 Testing Strategy

### Unit Tests
- User repository CRUD operations
- Data transformation and validation
- Session management lifecycle
- Cache invalidation strategies

### Integration Tests
- Migration from JSON to MongoDB
- Concurrent user operations
- Cross-repository data consistency
- Fallback mechanism testing

### Performance Tests
- User lookup performance comparison
- Session creation/retrieval benchmarks
- Bulk migration performance
- Memory usage under load

### User Acceptance Tests
- Existing user workflows unchanged
- New user registration process
- Session persistence across restarts
- Data consistency verification

## 📁 File Structure
```
jira_telegram_bot/
├── entities/users/
│   ├── __init__.py
│   ├── user_profile.py
│   ├── user_preferences.py
│   ├── telegram_session.py
│   └── user_activity.py
├── use_cases/interfaces/users/
│   ├── __init__.py
│   ├── user_profile_repository_interface.py
│   ├── user_preferences_repository_interface.py
│   ├── telegram_session_repository_interface.py
│   └── user_activity_repository_interface.py
├── adapters/repositories/mongodb/users/
│   ├── __init__.py
│   ├── mongodb_user_profile_repository.py
│   ├── mongodb_user_preferences_repository.py
│   ├── mongodb_telegram_session_repository.py
│   └── mongodb_user_activity_repository.py
├── use_cases/migrations/
│   ├── __init__.py
│   ├── user_data_migration_service.py
│   ├── session_data_migration_service.py
│   └── data_validation_service.py
└── frameworks/cli/
    ├── user_migration_cli.py
    └── session_migration_cli.py
```

## 🔐 Security & Privacy

### Data Protection
- Encrypt sensitive user data at rest
- Implement field-level encryption for PII
- Add data retention policies
- Support GDPR data deletion requests

### Access Control
- User-based access control for user data
- Admin vs. regular user permissions
- Audit trail for user data modifications
- Session security and token management

### Privacy Compliance
- User data anonymization capabilities
- Consent management for data tracking
- Data export functionality
- Privacy policy compliance checks

## 📈 Success Criteria

1. **Migration Completeness**: 100% of user data migrated successfully
2. **Data Integrity**: Zero data loss or corruption during migration
3. **Performance**: User operations ≤50ms response time (95th percentile)
4. **Backwards Compatibility**: Existing user workflows unaffected
5. **Session Reliability**: 99.9% session persistence across deployments
6. **Cache Efficiency**: >90% cache hit rate for user lookups
7. **Migration Speed**: Complete migration in <2 hours for current data volume

## 🚀 Deliverables

1. **Enhanced User Entities**: Comprehensive user and session models
2. **Migration Services**: Automated migration with validation and rollback
3. **Repository Implementations**: High-performance MongoDB repositories
4. **Updated Adapters**: Backwards-compatible user configuration adapters
5. **Testing Suite**: Comprehensive testing coverage (≥90%)
6. **Migration Tools**: CLI tools for migration management and monitoring
7. **Documentation**: User migration guide, troubleshooting, and API documentation

## 🔄 Dependencies on Phase 1

This phase builds directly on Phase 1 deliverables:
- **MongoDB Connection**: Uses connection infrastructure from Phase 1
- **Base Repository**: Extends base repository patterns
- **Settings Management**: Leverages configuration management patterns
- **Error Handling**: Uses established error handling patterns

## 📚 Additional Dependencies

Add to `requirements.txt`:
```
cachetools~=5.3.0  # For user data caching
python-dateutil~=2.8.0  # For enhanced date handling
```

## ⚠️ Risk Mitigation

### Data Migration Risks
- **User Data Loss**: Multiple backup strategies and validation checks
- **Migration Interruption**: Checkpoint-based migration with resume capability
- **Performance Degradation**: Gradual migration with monitoring

### Operational Risks
- **User Impact**: Dual-write pattern ensures no service interruption
- **Rollback Scenarios**: Complete rollback capability with data validation
- **Concurrent Modifications**: Optimistic locking and conflict resolution

### Technical Risks
- **Memory Usage**: Batch processing and streaming for large datasets
- **Database Load**: Rate limiting and connection pooling
- **Cache Coherence**: Cache invalidation strategies and consistency checks

---

**Remember**: This phase establishes user-centric data patterns that will support advanced features like user analytics, team collaboration tools, and personalized experiences in future phases.
