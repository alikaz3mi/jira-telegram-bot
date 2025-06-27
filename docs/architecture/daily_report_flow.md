# Daily Report Feature Architecture

## Overview

The Daily Report feature implements an automated system for collecting daily progress reports from team members via Telegram. The system follows Clean Architecture principles with clear separation of concerns across entities, use cases, adapters, and frameworks.

## Feature Components

### 1. Entities

#### `ProgressReport` (`entities/progress_reports/progress_report.py`)
- Core business entity representing a daily progress report
- Immutable Pydantic model containing:
  - `issue_key`: JIRA issue identifier
  - `progress`: Description of work accomplished
  - `blockers`: Obstacles or challenges encountered
  - `time_spent`: Estimated time spent on the task
  - `assignee`: Team member who reported progress
  - `reported_at`: Timestamp of report creation
  - `report_id`: Unique identifier

### 2. Use Cases

#### `GenerateProgressReportUseCase` (`use_cases/ai_agents/generate_progress_report_usecase.py`)
- Core application logic for processing progress reports
- Orchestrates AI-powered report generation and data storage
- Validates input, enriches reports with metadata
- Handles both individual and batch report processing

### 3. Adapters

#### AI Models
- **`GenerateProgressReportService`** (`adapters/ai_models/ai_agents/generate_progress_report_service.py`)
  - AI service for converting raw text/speech to structured reports
  - Uses prompt template and LLM provider for intelligent parsing
  - Maps unstructured input to specific JIRA tasks

#### Speech-to-Text
- **`SpeechRecogniser`** (`adapters/stt/speech_recogniser.py`)
  - Adapter for existing SpeechProcessor
  - Handles voice message transcription
  - Supports multiple audio formats (OGG, MP3, WAV, M4A)

#### Repository
- **`FileProgressReportRepository`** (`adapters/repositories/file_storage/file_progress_report_repository.py`)
  - File-based storage implementation
  - Stores reports in JSON format
  - Provides query capabilities by assignee, sprint, date range

### 4. Frameworks

#### Scheduler
- **`DailyReportJob`** (`frameworks/scheduler/daily_report_job.py`)
  - Cron job for automated report prompting
  - Runs daily between 14:00-16:00 (configurable)
  - Sends personalized prompts to team members
  - Integrates with existing CronJob framework

#### Telegram Handler
- **`DailyReportHandler`** (`frameworks/telegram/daily_report_handler.py`)
  - Telegram conversation handler for interactive report collection
  - Supports both voice and text input
  - Task selection interface for targeted reporting
  - Real-time progress feedback

## Workflow

### 1. Automated Prompting (Daily 14:00-16:00)
```
DailyReportJob
├── Fetches team members from report channel
├── Gets assigned tasks for each member
├── Sends personalized DM with task list
└── Provides interactive buttons for report types
```

### 2. Report Collection
```
User Input (Voice/Text)
├── DailyReportHandler receives message
├── SpeechRecogniser transcribes (if voice)
├── Optional task selection interface
└── Forwards to processing pipeline
```

### 3. AI Processing
```
GenerateProgressReportUseCase
├── Validates input data
├── GenerateProgressReportService
│   ├── Loads prompt template
│   ├── Calls LLM with context
│   └── Parses structured JSON response
├── Enriches with metadata
└── Stores via repository
```

### 4. Report Storage & Distribution
```
FileProgressReportRepository
├── Saves individual reports
├── Enables querying by various filters
└── Supports data export/aggregation

TelegramService
├── Confirms report submission to user
└── Posts summary to report channel
```

## Configuration

### Environment Variables
- `SPRINT_LABEL`: Current sprint label or JQL query
- `REPORT_CHANNEL_ID`: Telegram channel for aggregated reports
- `DATA_DIR`: Directory for report storage (default: ./data)

### Prompt Template
- Location: `adapters/ai_models/ai_agents/prompts/generate_progress_report.yaml`
- Configurable system and user prompts
- Structured output schema for consistent parsing

### Scheduler Configuration
- Cron expression: `0 14-16 * * 1-5` (weekdays only)
- Timezone: UTC (configurable)
- Prompt window: 14:00-16:00 (configurable)

## Integration Points

### Dependencies
- **JIRA Integration**: Uses existing `GetSprintIssuesUseCase` for task retrieval
- **Telegram Framework**: Leverages existing message handling infrastructure
- **AI Models**: Integrates with existing LLM provider interface
- **Speech Processing**: Uses existing `SpeechProcessor` for transcription

### Data Flow
1. **Input**: Voice messages or text from Telegram users
2. **Processing**: AI-powered conversion to structured reports
3. **Storage**: JSON file storage with query capabilities
4. **Output**: User confirmation + channel notifications

## Error Handling

### Graceful Degradation
- Voice transcription failures fall back to text input
- AI processing errors prompt for retry
- Network issues don't block user interaction
- Channel posting failures don't affect user flow

### Logging
- Comprehensive error logging at each layer
- Performance metrics for AI processing
- User interaction tracking for UX improvement

## Future Enhancements

### Planned Features
- Report analytics dashboard
- Integration with JIRA time tracking
- Team productivity metrics
- Custom report templates
- Slack integration
- Database storage option

### Scalability Considerations
- Repository interface allows easy database migration
- Service layer supports multiple AI providers
- Handler framework enables multi-platform support
- Configurable scheduling for different time zones
