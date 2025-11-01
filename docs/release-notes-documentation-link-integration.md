# Release Notes Documentation Link Integration

## خلاصه تغییرات

این تغییرات برای اضافه کردن قابلیت ذخیره لینک Google Docs documentation در Google Sheets Release Notes انجام شده.

---

## ✅ تغییرات انجام شده (Completed)

### 1. **Entity Layer** 

#### `ReleaseNoteEntity` - فیلد جدید
```python
# File: jira_telegram_bot/entities/release_notes.py

documentation_link: Optional[str] = Field(default=None, description="لینک Documentation")
```

### 2. **Configuration Layer**

#### `GoogleSheetsReleasesConfig` - فیلدهای جدید
```python
# File: jira_telegram_bot/entities/synth_pm/project_config.py

class GoogleSheetsReleasesConfig(BaseModel):
    """Configuration for Google Sheets releases/release notes sheet."""
    
    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")  # ✨ NEW
    sheet_name: str = Field(description="Release notes sheet name")
    gid: int = Field(description="Sheet GID for URL generation")  # ✨ NEW
    data_range: str = Field(description="Release notes data range")
```

#### `projects_config.json` - به‌روزرسانی
```json
{
  "projects": {
    "PARSCHAT": {
      "google_sheets": {
        "releases": {
          "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",  // ✨ NEW
          "sheet_name": "Release Notes",
          "gid": 1054397609,  // ✨ NEW
          "data_range": "A2:AO"
        }
      }
    }
  }
}
```

**نکته**: `gid` از لینک Google Sheets استخراج شده:
```
https://docs.google.com/spreadsheets/d/1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4/edit?gid=1054397609
                                                                                                     ^^^^^^^^^^
```

### 3. **Repository Layer - Parsing Methods**

#### `_create_release_notes_column_mapping`
```python
# File: jira_telegram_bot/adapters/repositories/synth_pm_repository.py

column_name_mappings = {
    # ... existing mappings ...
    "documentation_link": ["لینک Documentation", "Documentation Link", "Link Documentation"],  # ✨ NEW
    "telegram_message_id": ["Telegram Message ID", "Message ID"],
    "last_updated": ["Last Updated", "Updated"],
}
```

#### `_parse_row_to_release_note`
```python
# File: jira_telegram_bot/adapters/repositories/synth_pm_repository.py

return ReleaseNoteEntity(
    # ... existing fields ...
    documentation_link=get_mapped_value("documentation_link") if get_mapped_value("documentation_link") else None,  # ✨ NEW
    telegram_message_id=get_mapped_value("telegram_message_id") if get_mapped_value("telegram_message_id") else None,
    last_updated=parse_date(get_mapped_value("last_updated")),
)
```

---

## ⏳ کارهای باقیمانده (Remaining Tasks)

### Task 1: Update `create_feature_documentation` Return Value

**File**: `jira_telegram_bot/use_cases/documentation_generation_usecase.py`

**Current**:
```python
async def create_feature_documentation(...) -> bool:
    # ...
    if subtab_id:
        return True
    return False
```

**باید تبدیل بشه به**:
```python
async def create_feature_documentation(...) -> tuple[bool, Optional[str]]:
    """Create complete feature documentation in Google Docs.
    
    Returns:
        Tuple of (success, documentation_link)
        - success: True if successful, False otherwise
        - documentation_link: URL to Google Docs documentation (None if failed)
    """
    # ...
    if subtab_id:
        # Generate documentation link
        doc_link = f"https://docs.google.com/document/d/{document_id}/edit#heading={epic_tab_id}"
        return True, doc_link
    
    return False, None
```

### Task 2: Update Callers of `create_feature_documentation`

**هر جایی که این متد رو صدا می‌زنه باید update بشه**:

```python
# Before
success = await doc_gen_usecase.create_feature_documentation(...)

# After  
success, doc_link = await doc_gen_usecase.create_feature_documentation(...)
```

### Task 3: Add Documentation Link Storage Logic

**File**: `jira_telegram_bot/use_cases/synth_pm_usecase.py`

**جایی که `create_feature_documentation` صدا زده میشه** (معمولاً در یک orchestration method):

```python
async def _create_feature_documentation_and_save_link(
    self,
    feature: SynthPMFeatureEntity,
    document_id: str,
) -> bool:
    """Create feature documentation and save link to release notes.
    
    Args:
        feature: Feature entity
        document_id: Google Docs document ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get release note for this feature
        release_note = await self.repository.get_release_note_by_version(
            feature.release or feature.version
        )
        
        if not release_note:
            LOGGER.warning(f"No release note found for feature: {feature.task_title}")
            return False
        
        # Get subtasks
        subtasks = await self._get_feature_subtasks(feature)
        
        # Create documentation
        success, doc_link = await self.documentation_generation_usecase.create_feature_documentation(
            document_id=document_id,
            epic_name=feature.epic or "Unnamed Epic",
            feature=feature,
            release_note=release_note,
            subtasks=subtasks,
        )
        
        if not success:
            LOGGER.error(f"Failed to create documentation for: {feature.task_title}")
            return False
        
        # Save documentation link to release notes
        if doc_link:
            await self.repository.update_release_note(
                row_number=release_note.row_number,
                updates={"documentation_link": doc_link},
            )
            LOGGER.info(f"Saved documentation link for release {release_note.release_version}: {doc_link}")
        
        return True
        
    except Exception as e:
        LOGGER.error(f"Error creating feature documentation: {e}")
        return False
```

### Task 4: Handle Feature Title Changes in Google Docs

**Scenario**: اگر اسم یک feature در Google Sheet تغییر کرد، باید در Google Docs هم update بشه.

**راه‌حل پیشنهادی**: 

در Google Docs Repository یک متد برای update کردن feature title:

```python
# File: jira_telegram_bot/use_cases/interfaces/google_docs_repository_interface.py

@abstractmethod
async def update_feature_title(
    self,
    document_id: str,
    epic_tab_id: str,
    old_title: str,
    new_title: str,
) -> bool:
    """Update feature subtab title in Google Docs.
    
    Args:
        document_id: Google Docs document ID
        epic_tab_id: Epic tab ID
        old_title: Current feature title
        new_title: New feature title
        
    Returns:
        True if successful, False otherwise
    """
    pass
```

**Implementation در Repository**:
```python
# File: jira_telegram_bot/adapters/repositories/google_docs_repository.py

async def update_feature_title(
    self,
    document_id: str,
    epic_tab_id: str,
    old_title: str,
    new_title: str,
) -> bool:
    """Update feature subtab title in Google Docs."""
    try:
        # 1. Find feature subtab by old title
        content = await self._get_document_content(document_id)
        
        # 2. Find the heading with old_title
        for i, element in enumerate(content):
            if self._is_heading(element):
                text = self._extract_text(element)
                if text.strip() == old_title:
                    # 3. Update the heading text to new_title
                    await self._update_heading_text(
                        document_id,
                        i,  # element index
                        new_title,
                    )
                    LOGGER.info(f"Updated feature title from '{old_title}' to '{new_title}'")
                    return True
        
        LOGGER.warning(f"Feature subtab with title '{old_title}' not found")
        return False
        
    except Exception as e:
        LOGGER.error(f"Error updating feature title: {e}")
        return False
```

**Usage در Use Case**:
```python
# In synth_pm_usecase.py

async def _update_feature_if_title_changed(
    self,
    feature: SynthPMFeatureEntity,
    old_feature_data: Dict[str, Any],
    document_id: str,
) -> bool:
    """Update feature documentation if title changed.
    
    Args:
        feature: Current feature entity
        old_feature_data: Previous feature data from change tracker
        document_id: Google Docs document ID
        
    Returns:
        True if successful, False otherwise
    """
    old_title = old_feature_data.get("task_title")
    new_title = feature.task_title
    
    if old_title and old_title != new_title:
        LOGGER.info(f"Feature title changed: '{old_title}' -> '{new_title}'")
        
        # Get epic tab ID
        epic_tab_id = await self.documentation_generation_usecase.google_docs_repository.get_or_create_epic_tab(
            document_id,
            feature.epic or "Unnamed Epic",
        )
        
        # Update title in Google Docs
        success = await self.documentation_generation_usecase.google_docs_repository.update_feature_title(
            document_id,
            epic_tab_id,
            old_title,
            new_title,
        )
        
        return success
    
    return True  # No change needed
```

---

## 📊 Database Schema (Google Sheets)

### Release Notes Sheet

**ستون جدید که باید اضافه بشه**:

| Column Name | Persian Name | Type | Description |
|------------|--------------|------|-------------|
| Documentation Link | لینک Documentation | URL | Link to Google Docs feature documentation |

**مثال value**:
```
https://docs.google.com/document/d/1aSko7ryN2-kePi5d8w0dqlXdOZ4heQ3hmBP116NlCYY/edit#heading=h.abc123
```

---

## 🔄 Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Feature Sync Flow                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Process Feature      │
                  │  from Google Sheets   │
                  └───────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Create/Update Jira   │
                  │  Tasks                │
                  └───────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Create Documentation │
                  │  in Google Docs       │
                  └───────────────────────┘
                              │
                              ├──► Returns: (success, doc_link)
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Get Release Note     │
                  │  by Version           │
                  └───────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Update Release Note  │
                  │  with Documentation   │
                  │  Link                 │
                  └───────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Release Notes Sheet  │
                  │  Updated ✅           │
                  └───────────────────────┘
```

---

## 🧪 Testing Checklist

### Unit Tests to Add:

- [ ] Test `documentation_link` field in `ReleaseNoteEntity`
- [ ] Test `GoogleSheetsReleasesConfig` with new fields
- [ ] Test `_parse_row_to_release_note` with documentation_link
- [ ] Test `create_feature_documentation` returns tuple
- [ ] Test updating release note with documentation link
- [ ] Test feature title update in Google Docs

### Integration Tests:

- [ ] Test full flow: create documentation → save link
- [ ] Test updating feature title
- [ ] Test multiple features in same release

---

## 💡 Notes & Considerations

### 1. **Link Format**

دو فرمت لینک ممکن است:

**Option A - با Heading ID** (پیشنهادی):
```
https://docs.google.com/document/d/{document_id}/edit#heading={epic_tab_id}
```
✅ مستقیم به بخش مربوطه می‌رود

**Option B - بدون Heading ID**:
```
https://docs.google.com/document/d/{document_id}/edit
```
❌ باید manually scroll کنی

### 2. **Error Handling**

- اگر release note پیدا نشد → Log warning و ادامه sync
- اگر save link failed → Log error اما feature را invalid نکن
- اگر Google Docs API timeout → Retry with exponential backoff

### 3. **Performance**

- Documentation link generation باید synchronous باشه (string concat)
- فقط API call برای `update_release_note` هست
- Consider batching if updating multiple releases

### 4. **Backward Compatibility**

- همه فیلدهای جدید `Optional` هستند
- Existing release notes بدون documentation_link کار می‌کنند
- Configuration با default values سازگار است

---

## 📝 Summary

### تغییرات کامل شده:
1. ✅ Entity layer updated با `documentation_link`
2. ✅ Configuration updated با `spreadsheet_id` و `gid`
3. ✅ Repository parsing methods updated
4. ✅ `projects_config.json` updated

### تغییرات باقیمانده:
1. ⏳ `create_feature_documentation` return type تغییر بده
2. ⏳ Callers را update کن
3. ⏳ Logic ذخیره link در release notes اضافه کن
4. ⏳ Feature title update در Google Docs

### اولویت پیاده‌سازی:
1. **HIGH**: Tasks 1-3 (Documentation link storage)
2. **MEDIUM**: Task 4 (Feature title updates)
3. **LOW**: Additional features (link tracking, analytics)
