# Documentation Creation Fix - Implementation Plan

## مشکلات شناسایی شده:

### 1. ❌ استفاده اشتباه از Email
**مشکل فعلی**: کد سعی می‌کنه email برای هر department member پیدا کنه  
**راه‌حل**: باید از `projects_info.json` department lead رو بگیریم

```json
// From projects_info.json
{
  "PARSCHAT": {
    "components": [
      { "name": "Front-end", "lead": "z_lotfian" },
      { "name": "Backend", "lead": "m_samei" },
      { "name": "AI", "lead": "m_mousavi" },
      { "name": "DevOPS", "lead": "a_kazemi" },
      { "name": "UI/UX", "lead": "a_kazemi" }
    ]
  }
}
```

### 2. ❌ ساخت مجدد Task‌ها
**مشکل فعلی**: `_create_documentation_subtasks` دوباره subtask می‌سازه  
**واقعیت**: Task‌ها قبلاً در مراحل قبل ساخته شدن  
**راه‌حل**: نباید task بسازیم، فقط باید documentation در Google Docs بسازیم

### 3. ❌ استفاده نادرست از feature.release
**مشکل فعلی**: مستقیم از `feature.release` استفاده می‌شه  
**راه‌حل**: باید از لیست Release Notes استفاده کنیم

---

## Implementation Plan

### Step 1: حذف Subtask Creation Logic

**File**: `jira_telegram_bot/use_cases/synth_pm_usecase.py`

```python
# DELETE این متد:
async def _create_documentation_subtasks(
    self,
    feature: SynthPMFeatureEntity,
) -> List[str]:
    # این متد باید کاملاً حذف بشه
```

**و این صدا زدن رو هم حذف کن**:
```python
# در متد _process_feature:
# DELETE:
if feature.developer_board_issue_key:
    created_doc_subtasks = await self._create_documentation_subtasks(
        feature,
    )
```

### Step 2: ساخت متد جدید برای Google Docs Documentation

**File**: `jira_telegram_bot/use_cases/synth_pm_usecase.py`

```python
async def _create_and_save_feature_documentation(
    self,
    feature: SynthPMFeatureEntity,
    project_config: ProjectConfig,
) -> bool:
    """Create feature documentation in Google Docs and save link to release notes.
    
    Args:
        feature: Feature entity
        project_config: Project configuration
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # 1. Get release note from Release Notes sheet
        release_note = await self._get_release_note_for_feature(feature)
        
        if not release_note:
            LOGGER.warning(
                f"No release note found for feature {feature.task_title} "
                f"(release: {feature.release or feature.version})"
            )
            return False
        
        # 2. Get subtasks that were already created
        subtasks = await self._get_feature_subtasks(feature)
        
        # 3. Create documentation in Google Docs
        doc_id = project_config.google_docs.document_id
        epic_name = feature.epic or "Unnamed Epic"
        
        success, doc_link = await self.documentation_generation_usecase.create_feature_documentation(
            document_id=doc_id,
            epic_name=epic_name,
            feature=feature,
            release_note=release_note,
            subtasks=subtasks,
        )
        
        if not success:
            LOGGER.error(f"Failed to create documentation for: {feature.task_title}")
            return False
        
        # 4. Save documentation link to release notes
        if doc_link:
            await self.repository.update_release_note(
                row_number=release_note.row_number,
                updates={"documentation_link": doc_link},
            )
            LOGGER.info(
                f"✅ Saved documentation link for {release_note.release_version}: {doc_link}"
            )
        
        return True
        
    except Exception as e:
        LOGGER.error(f"Error creating feature documentation: {e}")
        return False
```

### Step 3: Update create_feature_documentation Return Type

**File**: `jira_telegram_bot/use_cases/documentation_generation_usecase.py`

```python
# Change from:
async def create_feature_documentation(...) -> bool:
    # ...
    if subtab_id:
        return True
    return False

# To:
async def create_feature_documentation(...) -> tuple[bool, Optional[str]]:
    """Create complete feature documentation in Google Docs.
    
    Returns:
        Tuple of (success, documentation_link)
    """
    try:
        epic_tab_id = await self.google_docs_repository.get_or_create_epic_tab(
            document_id,
            epic_name,
        )
        
        feature_doc = await self._build_feature_documentation(
            feature,
            release_note,
            subtasks,
        )
        
        subtab_id, was_created = await self.google_docs_repository.get_or_create_feature_subtab(
            document_id,
            epic_tab_id,
            feature_doc,
        )
        
        if subtab_id:
            # Generate documentation link
            doc_link = f"https://docs.google.com/document/d/{document_id}/edit#heading={epic_tab_id}"
            
            if was_created:
                LOGGER.info(f"✨ Created new feature documentation: {feature.task_title}")
            else:
                LOGGER.info(f"♻️ Updated existing feature documentation: {feature.task_title}")
            
            await self._apply_status_color_coding(
                document_id,
                epic_tab_id,
                feature,
            )
            
            return True, doc_link
        
        return False, None
        
    except Exception as e:
        LOGGER.error(f"Failed to create feature documentation: {e}")
        return False, None
```

### Step 4: Update _process_feature

**File**: `jira_telegram_bot/use_cases/synth_pm_usecase.py`

```python
# در متد _process_feature، REPLACE:

# OLD:
if feature.developer_board_issue_key:
    created_doc_subtasks = await self._create_documentation_subtasks(
        feature,
    )
    
    if created_doc_subtasks:
        sync_results["created_documentation_subtasks"] = (
            sync_results.get("created_documentation_subtasks", 0) 
            + len(created_doc_subtasks)
        )

# NEW:
if feature.developer_board_issue_key and (feature.release or feature.version):
    # Create Google Docs documentation
    project_config = await self._get_project_config()
    
    doc_created = await self._create_and_save_feature_documentation(
        feature,
        project_config,
    )
    
    if doc_created:
        sync_results["created_feature_documentation"] = (
            sync_results.get("created_feature_documentation", 0) + 1
        )
```

### Step 5: Add Helper Method for Project Config

**File**: `jira_telegram_bot/use_cases/synth_pm_usecase.py`

```python
async def _get_project_config(self) -> ProjectConfig:
    """Get project configuration.
    
    Returns:
        ProjectConfig entity
    """
    from jira_telegram_bot.settings.project_config_settings import ProjectConfigSettings
    
    config_settings = ProjectConfigSettings()
    
    # Try to find by board key
    project_config = config_settings.get_project_by_board_key(
        self.settings.pm_project_key
    )
    
    if not project_config:
        # Fallback: try to find by spreadsheet_id
        project_config = config_settings.get_project_by_spreadsheet_id(
            self.settings.google_sheets_id
        )
    
    if not project_config:
        raise ValueError(
            f"No project configuration found for board key: {self.settings.pm_project_key}"
        )
    
    return project_config
```

---

## توضیحات مهم:

### چرا Task نمی‌سازیم؟
از آنجایی که در مراحل قبل این Task‌ها ساخته شده‌اند:
- **PM Board**: `feature.jira_issue_key` 
- **Developer Board**: `feature.developer_board_issue_key`
- **Subtasks**: زیر developer_board_issue_key ساخته شدن

پس الان فقط باید:
1. Documentation در Google Docs بسازیم
2. لینکش رو در Release Notes sheet ذخیره کنیم

### Department Lead چطوری پیدا می‌شه؟
الان از `get_component_lead()` در repository استفاده می‌شه که از `projects_info.json` می‌خونه:
```python
lead_username = self.repository.get_component_lead(
    project_key="PARSCHAT",
    component_name="Backend"
)
# Returns: "m_samei"
```

### Release Notes چطوری پیدا می‌شه؟
```python
release_note = await self.repository.get_release_note_by_version(
    feature.release  # مثلاً "V 1.0.0"
)
```

---

## Testing Checklist

- [ ] حذف `_create_documentation_subtasks`
- [ ] پیاده‌سازی `_create_and_save_feature_documentation`
- [ ] Update کردن `create_feature_documentation` return type
- [ ] Update کردن `_process_feature`
- [ ] اضافه کردن `_get_project_config`
- [ ] تست کردن: آیا documentation در Google Docs ساخته می‌شه؟
- [ ] تست کردن: آیا link در Release Notes ذخیره می‌شه؟
- [ ] تست کردن: آیا duplicate نمی‌سازه؟

---

## Files to Modify

1. ✏️ `jira_telegram_bot/use_cases/synth_pm_usecase.py`
   - Delete `_create_documentation_subtasks`
   - Add `_create_and_save_feature_documentation`
   - Add `_get_project_config`
   - Update `_process_feature`

2. ✏️ `jira_telegram_bot/use_cases/documentation_generation_usecase.py`
   - Update `create_feature_documentation` return type

3. ✏️ `jira_telegram_bot/adapters/repositories/synth_pm_repository.py`
   - Delete `_create_documentation_subtask` (if not used elsewhere)
   - Keep `get_component_lead` (already exists)
   - Keep `create_release_in_pm_board` (already exists)

---

## Summary

**قبل از تغییرات**:
```
Feature → Create Subtasks (❌ اشتباه) → Done
```

**بعد از تغییرات**:
```
Feature → Get Release Note → Get Subtasks (Already Created) → 
         Create Google Docs → Save Link to Release Notes ✅
```
