# SynthPM Multi-Project Test Status

## Test Suite Overview

### ✅ Passing Tests (11/24 = 46%)

#### Unit Tests - Validation Logic (11/11 - 100%)
All validation tests in `tests/unit_tests/adapters/test_synth_pm_validation.py` pass:

- `test_validate_empty_title` - Validates empty title detection
- `test_validate_status_below_minimum` - Tests status threshold
- `test_validate_status_at_minimum` - Tests status at threshold
- `test_validate_no_assignees` - Validates assignee requirement
- `test_validate_no_sprint` - Validates sprint requirement
- `test_validate_no_departments` - Validates department requirement
- `test_validate_no_dates` - Validates date requirement
- `test_validate_all_requirements_met` - Tests valid feature
- `test_validate_with_sprint_list` - Tests sprint_list alternative
- `test_validate_different_departments` - Tests department variations
- `test_validate_invalid_status` - Tests invalid status handling

**Run command:** `python -m pytest tests/unit_tests/adapters/test_synth_pm_validation.py -v`

### ⚠️ Failing Tests (13/24 = 54%)

#### Multi-Project Sync Unit Tests (4/7 failing)
Location: `tests/unit_tests/adapters/test_synth_pm_multi_project_sync.py`

**Passing (3):**
- `test_get_status`
- `test_trigger_sync_all_projects`
- `test_trigger_sync_specific_project`

**Failing (4):**
- `test_initialize_all_projects` - Patch path issue
- `test_initialize_specific_projects` - Patch path issue
- `test_start_creates_tasks_for_each_project` - Patch path issue
- `test_stop_cancels_all_tasks` - Async mock issue

**Fix Required:** Update mock patches to match actual dependency injection patterns

#### Integration Tests (6/6 failing)
Location: `tests/integration/test_synth_pm_feature_validation.py`

**All Failing Due To:**
1. Missing `sheet_row_number` field (required)
2. Using boolean `True/False` instead of string `"✓"/None` for department fields

**Failing Tests:**
- `test_process_feature_skips_empty_row`
- `test_process_feature_skips_low_status`
- `test_process_feature_skips_missing_assignees`
- `test_process_feature_creates_task_when_valid`
- `test_process_feature_handles_multiple_validation_failures`
- `test_sync_includes_skipped_in_results`

**Fix Required:** 
- Add `sheet_row_number` parameter to all `SynthPMFeatureEntity()` creations
- Change `ai=True` to `ai="✓"`, `backend=True` to `backend="✓"`, etc.
- Change `ai=False` to `ai=None`, etc.

## Quick Fixes Needed

### For Integration Tests

Replace all instances like this:
```python
# ❌ Wrong
feature = SynthPMFeatureEntity(
    row_number=1,
    task_title="Test",
    ai=True,
    backend=False,
)

# ✅ Correct
feature = SynthPMFeatureEntity(
    row_number=1,
    sheet_row_number=2,  # Add this
    task_title="Test",
    ai="✓",  # String, not boolean
    backend=None,  # None instead of False
)
```

Or use the factory function approach from unit tests:
```python
def create_test_feature(**overrides):
    defaults = {
        "row_number": 1,
        "sheet_row_number": 2,
        "task_title": "Test Feature",
        "status": "۵. آماده پیاده سازی فنی",
        "involved_people": "User1",
        "sprint": "Sprint-1",
        "ai": "✓",
        "implementation_start_date": "2024-01-01",
    }
    defaults.update(overrides)
    return SynthPMFeatureEntity(**defaults)
```

### For Multi-Project Sync Tests

The service uses dependency injection via Lagom container. Mock patches need to target the container's resolve methods instead of direct imports.

## Running Tests

```bash
# All validation tests (passing)
python -m pytest tests/unit_tests/adapters/test_synth_pm_validation.py -v

# Multi-project sync tests (partial)
python -m pytest tests/unit_tests/adapters/test_synth_pm_multi_project_sync.py -v

# Integration tests (needs fixes)
python -m pytest tests/integration/test_synth_pm_feature_validation.py -v

# All SynthPM tests
python -m pytest tests/ -k synth_pm -v
```

## Test Coverage

- **Validation Logic:** ✅ Complete (100%)
- **Multi-Project Service:** ⚠️ Partial (43%)
- **Integration Flows:** ❌ Needs fixes (0%)

**Overall:** 11/24 tests passing (46%)
