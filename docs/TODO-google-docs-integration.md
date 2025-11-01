# خلاصه تغییرات و کارهای باقیمانده - Google Docs Integration

## ✅ فایل‌های ایجاد شده:

### Entities:
1. **`jira_telegram_bot/entities/synth_pm/google_docs_entities.py`**
   - تمام Entity های مربوط به ساختار Google Docs
   - شامل: FeatureDocumentation, EpicTab, DocumentSection ها و...

2. **`jira_telegram_bot/entities/synth_pm/story_sync_config.py`**
   - Entity برای configuration مربوط به story synchronization
   - شامل: StorySyncMapping, StorySyncConfig

### Interfaces:
3. **`jira_telegram_bot/use_cases/interfaces/google_docs_repository_interface.py`**
   - Interface کامل برای عملیات Google Docs
   - شامل متدهای: create_epic_tab, create_feature_subtab, update_feature_documentation و...

### Adapters:
4. **`jira_telegram_bot/adapters/repositories/google_docs_repository.py`**
   - پیاده‌سازی اولیه Google Docs Repository
   - ⚠️ توجه: برخی متدها stub هستند و نیاز به تکمیل دارند

### Use Cases:
5. **`jira_telegram_bot/use_cases/documentation_generation_usecase.py`**
   - Use case کامل برای تولید محتوای Google Docs
   - شامل helper متدهای متعدد برای ساخت بخش‌های مختلف documentation

### Configuration:
6. **`config/story_sync_config.json`** (به‌روز شده)
   - اضافه شدن فیلدهای: google_docs_id, google_docs_url, epic_tab_mappings, release_notes_sheet_name

---

## 🔧 کارهای باقیمانده (به ترتیب اولویت):

### 1. **Helper برای ایجاد Documentation Subtask** (Priority: HIGH)
یک helper method در `SynthPMRepository` برای ایجاد subtask مستندسازی با 2 ساعت تخمین:

```python
async def _create_documentation_subtask(
    self,
    parent_issue_key: str,
    department: str,
    assignee_email: str,
    feature: SynthPMFeatureEntity,
) -> Optional[str]:
    """Create documentation subtask for a department.
    
    Args:
        parent_issue_key: Parent feature issue key
        department: Department name
        assignee_email: Assignee email from user_config
        feature: Feature entity
        
    Returns:
        Created subtask issue key
    """
    # Implementation needed
    pass
```

**مکان**: `jira_telegram_bot/adapters/repositories/synth_pm_repository.py`

**توضیح**: این متد باید:
- یک subtask با عنوان "مستندسازی {department}" ایجاد کند
- Time estimate را 2 ساعت (7200 ثانیه) set کند
- به assignee مربوطه assign شود
- به parent issue لینک شود

---

### 2. **اضافه کردن Release Creation به PM Board** (Priority: HIGH)
متد جدید در `SynthPMRepository` برای ایجاد release در Jira PM board:

```python
async def create_release_in_pm_board(
    self,
    release_note: ReleaseNoteEntity,
) -> Optional[str]:
    """Create release version in PM board.
    
    Args:
        release_note: Release note entity from Google Sheets
        
    Returns:
        Release version ID if successful
    """
    # Implementation needed
    pass
```

**توضیح**: این متد باید:
- از release_note.release_version برای نام release استفاده کند
- Release را در project PM board ایجاد کند
- Start date و release date را از release_note بگیرد
- Description را از release_note.description بگیرد

---

### 3. **Integration با SynthPMUseCase** (Priority: HIGH)
به‌روزرسانی `SynthPMUseCase` برای استفاده از documentation generation:

```python
async def _process_feature(
    self,
    feature: SynthPMFeatureEntity,
    sync_results: Dict[str, Any],
):
    """Process a single feature."""
    try:
        # ... existing code ...
        
        # NEW: Create documentation in Google Docs
        if feature.developer_board_issue_key:
            await self._create_feature_documentation(
                feature,
                config.google_docs_id,
            )
        
        # NEW: Create documentation subtasks for each department
        await self._create_documentation_subtasks(feature)
        
        # ... rest of code ...
```

**Helpers مورد نیاز**:

```python
async def _create_feature_documentation(
    self,
    feature: SynthPMFeatureEntity,
    document_id: str,
) -> bool:
    """Create feature documentation in Google Docs."""
    # Get release note for this feature
    release_note = await self._get_release_note_for_feature(feature)
    
    # Get subtasks
    subtasks = await self._get_feature_subtasks(feature)
    
    # Use DocumentationGenerationUseCase
    return await self.documentation_generation_use_case.create_feature_documentation(
        document_id=document_id,
        epic_name=feature.epic or "Unnamed Epic",
        feature=feature,
        release_note=release_note,
        subtasks=subtasks,
    )

async def _create_documentation_subtasks(
    self,
    feature: SynthPMFeatureEntity,
) -> List[str]:
    """Create documentation subtasks for each involved department."""
    departments = self._extract_departments_from_feature(feature)
    created_subtasks = []
    
    for dept in departments:
        assignee_email = self._get_department_assignee_email(feature, dept)
        
        subtask_key = await self.repository._create_documentation_subtask(
            parent_issue_key=feature.developer_board_issue_key,
            department=dept,
            assignee_email=assignee_email,
            feature=feature,
        )
        
        if subtask_key:
            created_subtasks.append(subtask_key)
    
    return created_subtasks
```

---

### 4. **Load Configuration در Runtime** (Priority: MEDIUM)
ایجاد Settings class جدید برای story sync config:

**فایل جدید**: `jira_telegram_bot/settings/story_sync_settings.py`

```python
"""Settings for story synchronization."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from jira_telegram_bot.entities.synth_pm.story_sync_config import StorySyncConfig


class StorySyncSettings(BaseSettings):
    """Settings for story synchronization."""
    
    config_file_path: str = Field(
        default="config/story_sync_config.json",
        description="Path to story sync config JSON file",
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="story_sync_",
        extra="ignore",
    )
    
    def load_config(self) -> StorySyncConfig:
        """Load story sync configuration from JSON file.
        
        Returns:
            StorySyncConfig entity
        """
        config_path = Path(self.config_file_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        return StorySyncConfig(**config_data)
```

---

### 5. **Update Dependency Injection** (Priority: HIGH)
اضافه کردن binding های جدید به `config_dependency_injection.py`:

```python
# Google Docs Repository
container[GoogleDocsRepositoryInterface] = Singleton(
    lambda: GoogleDocsRepository(
        settings=container[GoogleSheetsConnectionSettings],
    ),
)

# Story Sync Settings
container[StorySyncSettings] = Singleton(StorySyncSettings)

# Documentation Generation Use Case
container[DocumentationGenerationUseCase] = Singleton(
    lambda: DocumentationGenerationUseCase(
        google_docs_repository=container[GoogleDocsRepositoryInterface],
        user_config=container[UserConfigInterface],
    ),
)

# Update SynthPMUseCase to include DocumentationGenerationUseCase
# (modify existing binding)
```

---

### 6. **Complete Google Docs Repository Implementation** (Priority: MEDIUM)
متدهای زیر در `GoogleDocsRepository` نیاز به پیاده‌سازی کامل دارند:

- `update_feature_documentation()` - برای update کردن documentation موجود
- `apply_document_formatting()` - برای اعمال font و formatting
- `insert_table()` - برای درج جداول (feature info table)
- `add_hyperlink()` - برای لینک‌های Jira
- `tag_user_by_email()` - برای تگ کردن کاربران با email
- `delete_feature_subtab()` - برای حذف documentation حذف شده

**راهنمای پیاده‌سازی**:
- استفاده از Google Docs API v1
- استفاده از `batchUpdate` برای performance بهتر
- Handle کردن RTL text برای فارسی
- استفاده از `run_in_executor` برای async operations

---

### 7. **Helper برای Extract کردن Emails از UserConfig** (Priority: HIGH)
در `DocumentationGenerationUseCase`، متدهای زیر باید واقعی پیاده شوند:

```python
def _get_reporter_email(self, release_note: ReleaseNoteEntity) -> str:
    """Get reporter email from user config."""
    # از user_config استفاده کن تا email واقعی reporter را پیدا کنی
    # باید با field reporter در release_note match شود
    pass

def _get_assignee_email_for_department(
    self,
    feature: SynthPMFeatureEntity,
    department: str,
) -> str:
    """Get assignee email for specific department from user config."""
    # از user_config استفاده کن
    # باید با people columns در feature match شود
    pass
```

---

### 8. **Link Google Doc به Jira Issues** (Priority: MEDIUM)
اضافه کردن قابلیت لینک کردن Google Doc link به Jira issues:

```python
async def _add_google_doc_link_to_issue(
    self,
    issue_key: str,
    doc_url: str,
) -> bool:
    """Add Google Doc link to Jira issue.
    
    این link باید در description یا یک custom field قرار بگیرد.
    """
    pass
```

---

### 9. **Sync Process Flow Update** (Priority: HIGH)
روند sync باید به این شکل تغییر کند:

#### فلوچارت جدید:
```
1. خواندن features از Google Sheets
2. خواندن release notes از Google Sheets
3. برای هر release:
   a. ایجاد release در PM board (اگر وجود ندارد)
   b. ایجاد Epic tab در Google Docs (اگر وجود ندارد)
4. برای هر feature:
   a. ایجاد/به‌روزرسانی task در PM board
   b. ایجاد/به‌روزرسانی task در Developer board
   c. ایجاد subtasks برای هر department
   d. ایجاد documentation subtask برای هر department (2 ساعت)
   e. ایجاد feature documentation در Google Docs
   f. لینک کردن Google Doc به Jira issues
5. Post کردن به Telegram (اگر نیاز باشد)
```

---

### 10. **Unit Tests** (Priority: MEDIUM)
ایجاد test files:

- `tests/use_cases/test_documentation_generation_usecase.py`
- `tests/adapters/repositories/test_google_docs_repository.py`
- `tests/entities/synth_pm/test_google_docs_entities.py`
- `tests/entities/synth_pm/test_story_sync_config.py`

**Coverage Target**: ≥ 90%

---

### 11. **Documentation** (Priority: LOW)
ایجاد documentation در `docs/features/`:

**فایل**: `docs/features/google-docs-documentation-generation.md`

```markdown
# Google Docs Documentation Generation

## Overview
توضیح کامل سیستم تولید خودکار مستندات در Google Docs

## Architecture
- Entity Layer
- Use Case Layer  
- Adapter Layer
- Integration Points

## Flow Diagrams
(Mermaid diagrams)

## Configuration
نحوه configure کردن story_sync_config.json

## Usage Examples
نمونه‌های استفاده

## Troubleshooting
راهنمای troubleshoot
```

---

## 🎯 Next Steps (اولویت‌بندی شده):

### Phase 1 - Core Functionality (این هفته):
1. ✅ Helper for Documentation Subtask Creation
2. ✅ Release Creation in PM Board  
3. ✅ Integration با SynthPMUseCase
4. ✅ Update Dependency Injection
5. ✅ Load Configuration در Runtime

### Phase 2 - Enhancement (هفته بعد):
6. ⚠️ Complete Google Docs Repository Implementation
7. ⚠️ Helper برای Extract Emails
8. ⚠️ Link Google Doc به Jira

### Phase 3 - Testing & Documentation (2 هفته بعد):
9. ⚠️ Unit Tests (≥90% coverage)
10. ⚠️ Integration Tests
11. ⚠️ Documentation

---

## 📝 Notes:

### Google Docs API Limitations:
- Google Docs API v1 محدودیت‌های خاصی برای RTL text دارد
- Tabs واقعی در Google Docs وجود ندارند - باید از Named Ranges یا Bookmarks استفاده کنیم
- برای رنگ‌آمیزی باید از ParagraphStyle background color استفاده شود

### User Config Integration:
- باید email mapping از `user_config` استخراج شود
- هر user در user_config باید email داشته باشد
- matching بر اساس department و people columns انجام می‌شود

### Performance Considerations:
- Google Docs API rate limits دارد (60 requests per minute)
- باید از batch operations استفاده کنیم
- caching برای frequently accessed documents

---

## 🐛 Known Issues:

1. **Google Docs Tabs**: Google Docs API support واقعی برای tabs ندارد
   - **راه حل**: استفاده از Headings و Named Ranges برای simulate کردن tabs

2. **RTL Text**: مشکلات formatting با متن فارسی
   - **راه حل**: استفاده از explicit RTL markers و proper paragraph styles

3. **User Email Mapping**: فعلاً emails mock هستند
   - **راه حل**: باید integration با UserConfig کامل شود

---

## 📚 Resources:

- [Google Docs API Reference](https://developers.google.com/docs/api/reference/rest)
- [Google Docs API Quickstart](https://developers.google.com/docs/api/quickstart/python)
- [Batch Update Guide](https://developers.google.com/docs/api/how-tos/batch-updates)

---

**Last Updated**: 2025-11-01
**Status**: Foundation Complete, Implementation In Progress
