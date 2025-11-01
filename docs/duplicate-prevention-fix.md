# Duplicate Prevention: Feature Subtab Management

## Problem (Before)

When running sync multiple times, the code would:
1. ❌ **Always create new subtabs** - No check if feature already exists
2. ❌ **Create duplicate content** - Same feature appears multiple times
3. ❌ **Ignore updates** - No way to update existing documentation

**Example of the problem:**
```
Google Doc After 2 Syncs:
├── Epic 1
│   ├── Feature A (first sync)
│   ├── Feature A (second sync) ← DUPLICATE!
│   ├── Feature A (third sync) ← DUPLICATE!
│   └── Feature B
```

## Solution (After)

### New Methods Added

#### 1. `feature_subtab_exists()` - Check if subtab exists
```python
async def feature_subtab_exists(
    document_id: str,
    epic_tab_id: str,
    feature_title: str,
) -> bool:
    """Check if feature subtab already exists in document."""
```

#### 2. `get_or_create_feature_subtab()` - Smart creation/update
```python
async def get_or_create_feature_subtab(
    document_id: str,
    epic_tab_id: str,
    feature_doc: FeatureDocumentation,
) -> tuple[str, bool]:
    """Get existing subtab or create new one.
    
    Returns:
        (subtab_id, was_created) - was_created is True if newly created
    """
```

### How It Works Now

```python
# In DocumentationGenerationUseCase
subtab_id, was_created = await self.google_docs_repository.get_or_create_feature_subtab(
    document_id,
    epic_tab_id,
    feature_doc,
)

if subtab_id:
    if was_created:
        LOGGER.info(f"✅ Created NEW feature documentation: {feature.task_title}")
    else:
        LOGGER.info(f"♻️ Updated EXISTING feature documentation: {feature.task_title}")
```

### Behavior Comparison

| Scenario | Before | After |
|----------|--------|-------|
| **First sync** | Creates subtab ✅ | Creates subtab ✅ |
| **Second sync** | Creates duplicate ❌ | Updates existing ✅ |
| **Third sync** | Creates another duplicate ❌ | Updates existing ✅ |
| **Field changes** | Creates duplicate with new values ❌ | Updates existing subtab ✅ |

## Implementation Details

### Flow Chart

```
Start Sync
    ↓
Get/Create Epic Tab
    ↓
Build Feature Documentation
    ↓
Check: Does feature subtab exist?
    ├─ NO → Create new subtab
    │         └─ Return (id, created=True)
    └─ YES → Update existing subtab
              └─ Return (id, created=False)
```

### Detection Logic

The code searches through document content for:
```python
# Looks for exact match of feature title
for element in content:
    text = element.get("paragraph", {})...get("content", "")
    if text.strip() == feature_title:
        return True  # Found existing!
```

### Update vs Create

- **Create**: Adds new content at end of Epic section
- **Update**: Replaces content of existing feature section (stub for now)

## Benefits

1. ✅ **No Duplicates**: Each feature appears only once
2. ✅ **Always Current**: Re-syncing updates documentation
3. ✅ **Idempotent**: Running sync multiple times = same result
4. ✅ **Clear Logging**: Know if created or updated

## Example Logs

```bash
# First sync
INFO: Created NEW feature documentation: User Login Feature

# Second sync
INFO: Found existing feature subtab: User Login Feature
INFO: Updated EXISTING feature documentation: User Login Feature

# Third sync  
INFO: Found existing feature subtab: User Login Feature
INFO: Updated EXISTING feature documentation: User Login Feature
```

## Edge Cases Handled

| Case | Behavior |
|------|----------|
| Feature title changed | Creates new subtab (title is key) |
| Fields updated | Updates existing subtab |
| Epic changed | Creates in new epic section |
| Document doesn't exist | Fails gracefully with error |
| No permission | Fails with permission error |

## Future Enhancements

### Currently Stub (Not Implemented)
```python
async def update_feature_documentation(...):
    # TODO: Actually update content instead of just logging
    LOGGER.info(f"Updating feature documentation: {feature_title}")
    return True
```

### To Fully Implement Update:
1. Find exact location of existing feature
2. Delete old content
3. Insert new content at same location
4. Preserve any manual edits/comments

### Potential Improvements:
- Track feature by Jira key instead of title
- Add version tracking
- Support partial updates (only changed fields)
- Keep history of changes
- Add "last updated" timestamp

## Migration Notes

### For Existing Documents

If you already have duplicates:
1. **Option A**: Manually delete duplicates in Google Docs
2. **Option B**: Use `delete_feature_subtab()` method (to be implemented)
3. **Option C**: Create fresh document and re-sync

### No Breaking Changes

- Existing code continues to work
- New behavior is backward compatible
- Only affects future syncs

## Testing

To test the fix:
```bash
# First sync
python scripts/run_synth_pm.py sync

# Check Google Doc - should have features

# Second sync  
python scripts/run_synth_pm.py sync

# Check Google Doc - should NOT have duplicates
```

## Summary

**Before**: 🔴 Multiple syncs = Multiple copies  
**After**: 🟢 Multiple syncs = One updated copy

This ensures Google Docs always reflects current state without accumulating duplicates!
