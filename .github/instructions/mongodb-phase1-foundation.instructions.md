---

mode: agent
description: Phase 1 - MongoDB Foundation & Settings Migration - Establish MongoDB infrastructure and migrate basic configuration data
tools: [terminalLastCommand, codeBase, usages, testFailure, findTestFiles]
-----------------------------------------

# 🚀 Phase 1: MongoDB Foundation & Settings Migration

Establish MongoDB infrastructure and migrate configuration data from `.env` files to MongoDB collections. This includes multi-Jira support, Google Sheets/Docs configuration, and application settings management.

This phase creates the foundation for all subsequent MongoDB migrations by establishing connection patterns, base entities, and repository interfaces following Clean Architecture principles.

## 🎯 Goals

1. **MongoDB Infrastructure**: Connection management, settings classes, base repositories
2. **Multi-Jira Support**: Store multiple Jira connections (Cloud & Server) in MongoDB
3. **Google Services Config**: Migrate Google Sheets/Docs settings from `.env` to MongoDB
4. **Application Settings**: Centralize environment-specific configurations
5. **User Authentication**: Move allowed users list from `.env` to MongoDB
6. **Foundation Patterns**: Establish Clean Architecture patterns for subsequent phases

## 📊 Data to Migrate

### From `.env` to MongoDB Collections:

1. **`jira_connections`** - Multiple Jira instances (Cloud & Server)
2. **`google_services_config`** - Multiple Google API connections (Sheets, Docs, Drive)
3. **`telegram_integrations`** - Multi-channel/group configurations
4. **`project_integrations`** - Project-centric integration mappings
5. **`notification_routing`** - Project-to-channel notification rules
6. **`application_settings`** - App-level configurations
7. **`user_authentication`** - Allowed users and permissions

### New Logical Relationship Collections:

8. **`project_ecosystem_mappings`** - Central project integration hub
9. **`team_workspace_assignments`** - Team-to-workspace mappings
10. **`integration_dependencies`** - Service dependency relationships

## 🏗️ Architecture Components

### 1. MongoDB Connection Infrastructure
**Location**: `jira_telegram_bot/adapters/repositories/mongodb/`

* `mongodb_connection.py` - Connection management and client factory
* `base_mongodb_repository.py` - Base repository with common CRUD operations
* `mongodb_settings.py` - MongoDB-specific settings class

### 2. Settings Migration
**Location**: `jira_telegram_bot/settings/mongodb/`

* `mongodb_application_settings.py` - Centralized app settings
* `mongodb_jira_settings.py` - Multi-Jira connection settings
* `mongodb_google_services_settings.py` - Multiple Google services configuration
* `mongodb_telegram_settings.py` - Multi-channel/group Telegram settings
* `mongodb_project_integration_settings.py` - Project-centric integration settings

### 3. Domain Entities  
**Location**: `jira_telegram_bot/entities/mongodb/`

* `jira_connection_config.py` - Jira connection entity
* `google_services_config.py` - Multiple Google services entity
* `telegram_integration_config.py` - Multi-channel Telegram entity
* `project_ecosystem_mapping.py` - Project integration hub entity
* `notification_routing_config.py` - Project-to-channel routing entity
* `application_config.py` - Application configuration entity
* `user_authentication_config.py` - User auth entity

### 4. Repository Interfaces
**Location**: `jira_telegram_bot/use_cases/interfaces/mongodb/`

* `jira_connection_repository_interface.py`
* `google_services_repository_interface.py` 
* `telegram_integration_repository_interface.py`
* `project_ecosystem_repository_interface.py`
* `notification_routing_repository_interface.py`
* `application_settings_repository_interface.py`
* `user_authentication_repository_interface.py`

### 5. Repository Implementations
**Location**: `jira_telegram_bot/adapters/repositories/mongodb/`

* `mongodb_jira_connection_repository.py`
* `mongodb_google_services_repository.py`
* `mongodb_telegram_integration_repository.py`
* `mongodb_project_ecosystem_repository.py`
* `mongodb_notification_routing_repository.py`
* `mongodb_application_settings_repository.py`
* `mongodb_user_authentication_repository.py`

## 📝 Implementation Details

### Environment Strategy
- **Development**: `jira_bot_dev` database
- **Staging**: `jira_bot_staging` database  
- **Production**: `jira_bot_prod` database
- **Connection pooling**: Shared across environments

### Migration Strategy
- **Dual-write pattern**: Write to both `.env` and MongoDB during transition
- **Graceful fallback**: If MongoDB unavailable, fall back to `.env`
- **Migration scripts**: One-time data import from `.env` to MongoDB
- **Validation**: Compare `.env` vs MongoDB data integrity

### Multi-Jira Configuration Structure
```python
JiraConnectionConfig:
    connection_id: str  # unique identifier
    connection_type: "cloud" | "server"
    domain: str
    username: str  
    password: Optional[str]  # for server
    token: Optional[str]     # for cloud
    email: Optional[str]     # for cloud
    is_primary: bool         # default connection
    is_active: bool
    projects: List[str]      # associated projects
    created_at: datetime
    updated_at: datetime
```

### Google Services Configuration Structure
```python
GoogleServicesConfig:
    service_id: str  # unique identifier
    service_type: "sheets" | "docs" | "drive"
    service_account_file: str
    credentials_json: dict  # encrypted storage
    project_associations: List[str]  # projects using this service
    scope_permissions: List[str]  # API scopes
    quota_limits: QuotaConfig
    is_active: bool
    created_at: datetime
    updated_at: datetime

# Multiple service configurations per type
GoogleSheetsServiceConfig:
    service_id: str
    sheet_connections: List[SheetConnection]
    default_sheet_id: Optional[str]
    project_sheet_mappings: Dict[str, str]  # project_key -> sheet_id
    team_sheet_mappings: Dict[str, str]     # team -> sheet_id
```

### Telegram Integration Structure
```python
TelegramIntegrationConfig:
    integration_id: str  # unique identifier
    bot_token: str
    bot_username: str
    integration_type: "project" | "team" | "global"
    channels: List[TelegramChannelConfig]
    groups: List[TelegramGroupConfig]
    project_associations: List[str]
    notification_rules: List[NotificationRule]
    is_active: bool
    created_at: datetime
    updated_at: datetime

TelegramChannelConfig:
    channel_id: int
    channel_name: str
    channel_type: "public" | "private"
    project_associations: List[str]
    allowed_operations: List[str]  # post, edit, delete
    notification_types: List[str]  # deadlines, progress, status
    
TelegramGroupConfig:
    group_id: int
    group_name: str
    team_associations: List[str]
    allowed_users: List[str]
    permissions: GroupPermissions
```

### Project Ecosystem Mapping Structure
```python
ProjectEcosystemMapping:
    project_key: str  # primary key
    project_name: str
    jira_connection_id: str  # reference to JiraConnectionConfig
    google_services: ProjectGoogleServices
    telegram_integration: ProjectTelegramIntegration
    team_assignments: List[TeamAssignment]
    notification_routing: NotificationRoutingConfig
    dashboard_config: DashboardConfig
    created_at: datetime
    updated_at: datetime
    is_active: bool

ProjectGoogleServices:
    sheets_service_id: Optional[str]
    docs_service_id: Optional[str]
    drive_service_id: Optional[str]
    primary_sheet_id: Optional[str]
    backup_sheet_id: Optional[str]
    project_folder_id: Optional[str]

ProjectTelegramIntegration:
    primary_channel_id: Optional[int]
    notification_channel_id: Optional[int]
    team_group_id: Optional[int]
    stakeholder_group_id: Optional[int]
    bot_integration_id: str

NotificationRoutingConfig:
    deadline_notifications: ChannelRoutingRule
    progress_notifications: ChannelRoutingRule
    status_change_notifications: ChannelRoutingRule
    error_notifications: ChannelRoutingRule
    escalation_rules: List[EscalationRule]
```

## 🔄 Migration Workflow

### 1. Infrastructure Setup
1. Create MongoDB connection management
2. Establish base repository patterns
3. Set up environment-specific databases
4. Configure connection pooling and error handling

### 2. Entity & Interface Creation
1. Define domain entities for each configuration type
2. Create repository interfaces following Clean Architecture
3. Establish data validation and serialization patterns

### 3. Repository Implementation
1. Implement MongoDB repositories with CRUD operations
2. Add indexing for performance
3. Implement caching strategies
4. Add error handling and logging

### 4. Settings Classes Migration
1. Create new settings classes that read from MongoDB
2. Implement fallback to `.env` for backwards compatibility
3. Add configuration validation
4. Support environment-specific overrides

### 5. Migration Scripts
1. Create one-time migration scripts to import `.env` data
2. Implement data validation and integrity checks
3. Add rollback capabilities
4. Create backup mechanisms

### 6. Integration & Testing
1. Update dependency injection configuration
2. Modify existing code to use new settings classes
3. Implement comprehensive testing
4. Add monitoring and alerting

## 📋 Interactive Variables

### Database Configuration
* `${input:mongodb_uri}` - MongoDB connection string
* `${input:database_prefix}` - Database name prefix (default: `jira_bot`)
* `${input:environment}` - Environment name (dev/staging/prod)
* `${input:enable_fallback}` - Enable `.env` fallback (default: true)
* `${input:migration_batch_size}` - Batch size for data migration (default: 100)
* `${input:connection_pool_size}` - MongoDB connection pool size (default: 10)
* `${input:enable_encryption}` - Encrypt sensitive data (default: true)
* `${input:backup_original}` - Backup original `.env` data (default: true)

### Integration Configuration
* `${input:enable_multi_jira}` - Enable multiple Jira connections (default: true)
* `${input:enable_multi_telegram}` - Enable multiple Telegram integrations (default: true)
* `${input:enable_multi_google}` - Enable multiple Google service accounts (default: true)
* `${input:enable_project_ecosystems}` - Enable project-centric integration mapping (default: true)
* `${input:notification_routing}` - Enable smart notification routing (default: true)
* `${input:cross_service_linking}` - Enable cross-service entity linking (default: true)

## 🔧 Technical Implementation

### MongoDB Connection Pattern
```python
class MongoDBConnection:
    def __init__(self, settings: MongoDBSettings):
        self.client = MongoClient(settings.uri, **settings.connection_options)
        self.database = self.client[settings.database_name]
    
    async def get_collection(self, collection_name: str):
        return self.database[collection_name]
```

### Base Repository Pattern
```python
class BaseMongoDBRepository:
    def __init__(self, connection: MongoDBConnection, collection_name: str):
        self.collection = connection.get_collection(collection_name)
    
    async def create(self, entity: BaseModel) -> str:
        # Implementation with validation and error handling
    
    async def get_by_id(self, id: str) -> Optional[BaseModel]:
        # Implementation with caching
    
    async def update(self, id: str, updates: dict) -> bool:
        # Implementation with optimistic locking
```

### Multi-Service Configuration Access
```python
class ProjectEcosystemService:
    async def get_project_jira_connection(self, project_key: str) -> JiraConnectionConfig:
        # Returns the Jira connection for specific project
    
    async def get_project_telegram_channels(self, project_key: str) -> List[TelegramChannelConfig]:
        # Returns all Telegram channels for specific project
    
    async def get_project_google_sheets(self, project_key: str) -> GoogleSheetsServiceConfig:
        # Returns Google Sheets configuration for specific project
        
    async def get_notification_routing_for_project(self, project_key: str) -> NotificationRoutingConfig:
        # Returns notification routing rules for specific project
        
    async def get_all_integrations_for_project(self, project_key: str) -> ProjectEcosystemMapping:
        # Returns complete integration ecosystem for project

class MultiServiceManager:
    async def route_notification(
        self, 
        project_key: str, 
        notification_type: str, 
        message: str
    ) -> List[NotificationResult]:
        # Route notification to appropriate channels based on project config
        
    async def create_cross_service_link(
        self,
        jira_issue_key: str,
        telegram_message_id: int,
        google_sheet_row: int
    ) -> CrossServiceLink:
        # Create links between services for the same project entity
        
    async def sync_project_data_across_services(self, project_key: str) -> SyncResult:
        # Synchronize project data across all integrated services
```

## 🧪 Testing Strategy

### Unit Tests
- Repository implementations (CRUD operations)
- Settings classes (validation, fallback logic)
- Entity serialization/deserialization
- Connection management

### Integration Tests  
- MongoDB connection and database operations
- Migration scripts with real data
- Fallback mechanisms
- Environment-specific configurations

### Performance Tests
- Connection pooling efficiency
- Query performance with indexes
- Bulk operations for migration
- Memory usage patterns

## 📁 File Structure
```
jira_telegram_bot/
├── entities/mongodb/
│   ├── __init__.py
│   ├── jira_connection_config.py
│   ├── google_services_config.py
│   ├── telegram_integration_config.py
│   ├── project_ecosystem_mapping.py
│   ├── notification_routing_config.py
│   ├── application_config.py
│   └── user_authentication_config.py
├── use_cases/interfaces/mongodb/
│   ├── __init__.py
│   ├── jira_connection_repository_interface.py
│   ├── google_services_repository_interface.py
│   ├── telegram_integration_repository_interface.py
│   ├── project_ecosystem_repository_interface.py
│   ├── notification_routing_repository_interface.py
│   ├── application_settings_repository_interface.py
│   └── user_authentication_repository_interface.py
├── adapters/repositories/mongodb/
│   ├── __init__.py
│   ├── mongodb_connection.py
│   ├── base_mongodb_repository.py
│   ├── mongodb_jira_connection_repository.py
│   ├── mongodb_google_services_repository.py
│   ├── mongodb_telegram_integration_repository.py
│   ├── mongodb_project_ecosystem_repository.py
│   ├── mongodb_notification_routing_repository.py
│   ├── mongodb_application_settings_repository.py
│   └── mongodb_user_authentication_repository.py
├── settings/mongodb/
│   ├── __init__.py
│   ├── mongodb_settings.py
│   ├── mongodb_application_settings.py
│   ├── mongodb_jira_settings.py
│   ├── mongodb_google_services_settings.py
│   ├── mongodb_telegram_settings.py
│   └── mongodb_project_integration_settings.py
├── use_cases/integrations/
│   ├── __init__.py
│   ├── project_ecosystem_service.py
│   ├── multi_service_manager.py
│   ├── notification_routing_service.py
│   └── cross_service_linking_service.py
└── frameworks/cli/
    ├── mongodb_migration_cli.py
    ├── mongodb_setup_cli.py
    ├── integration_management_cli.py
    └── project_ecosystem_cli.py
```

## 🔐 Security Considerations

### Data Encryption
- Encrypt sensitive data (passwords, tokens) at rest
- Use MongoDB field-level encryption for credentials
- Implement key rotation strategies

### Access Control  
- MongoDB role-based access control
- Application-level permission checking
- Audit logging for configuration changes

### Backup & Recovery
- Automated daily backups
- Point-in-time recovery capabilities
- Cross-region backup replication

## 📈 Success Criteria

1. **MongoDB Infrastructure**: Connection management working across environments
2. **Multi-Service Integration**: Multiple Jira, Google, and Telegram integrations working simultaneously
3. **Project Ecosystem Mapping**: Complete project-to-services mapping with automated routing
4. **Cross-Service Linking**: Entities linked across Jira, Telegram, and Google services
5. **Configuration Migration**: All `.env` settings moved to MongoDB with fallback
6. **Notification Routing**: Smart routing based on project and notification type
7. **Backwards Compatibility**: Existing functionality unchanged during transition
8. **Performance**: Response times within 100ms for configuration queries
9. **Reliability**: 99.9% uptime for MongoDB connections with proper failover
10. **Security**: All sensitive data encrypted, access properly controlled

## 🚀 Deliverables

1. **Infrastructure Code**: MongoDB connection, base repositories, settings classes
2. **Migration Scripts**: Automated `.env` to MongoDB migration with validation
3. **Updated DI Configuration**: Lagom container bindings for new repositories
4. **Comprehensive Tests**: Unit, integration, and performance tests (≥90% coverage)
5. **Documentation**: Architecture decisions, configuration guides, troubleshooting
6. **CLI Tools**: Migration, setup, and management command-line tools

## 📚 Dependencies

### New Dependencies
- `motor`: Async MongoDB driver for Python
- `cryptography`: For data encryption at rest
- `pydantic[email]`: Enhanced validation for email fields

### Update Requirements
Add to `requirements.txt`:
```
motor~=3.3.0
cryptography~=41.0.0
pydantic[email]~=2.4.0
```

## 🔄 Next Phase Integration

This phase establishes the foundation patterns that subsequent phases will follow:
- **Phase 2**: User & session data will use the same repository patterns
- **Phase 3**: Business data will leverage the same connection infrastructure  
- **Phase 4**: Advanced features will build upon the caching and indexing strategies

## ⚠️ Risk Mitigation

### Technical Risks
- **MongoDB connectivity issues**: Implement robust retry logic and circuit breakers
- **Data migration errors**: Extensive validation and rollback procedures
- **Performance degradation**: Comprehensive benchmarking and optimization

### Business Risks  
- **Service interruption**: Dual-write pattern ensures continuity
- **Data loss**: Multiple backup strategies and validation checks
- **Security vulnerabilities**: Comprehensive security review and testing

---

**Remember**: This phase creates the foundation for all subsequent MongoDB integrations. Focus on establishing robust, scalable patterns that future phases can build upon.
