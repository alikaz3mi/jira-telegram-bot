# Test Scripts

Test and validation scripts for development.

## Scripts

### `test_delay_reason_extraction.py`
Test delay reason extraction logic.

```bash
python scripts/testing/test_delay_reason_extraction.py
```

### `test_delay_reason_simple.py`
Simple delay reason tests.

```bash
python scripts/testing/test_delay_reason_simple.py
```

### `test_department_dependencies.py`
Test department dependency resolution.

```bash
python scripts/testing/test_department_dependencies.py
```

### `test_epic_sync.py`
Test PROJ1 epic synchronization.

```bash
python scripts/testing/test_epic_sync.py
```

### `test_sprint_closed_webhook.py`
Test sprint closed webhook handler.

```bash
python scripts/testing/test_sprint_closed_webhook.py
```

### `test_synth_pm_filtering.py`
Test SynthPM filtering logic.

```bash
python scripts/testing/test_synth_pm_filtering.py
```

## Usage

These scripts test specific functionality outside the main test suite.

For full test suite, use:
```bash
make unit-tests
make integration-tests
```
