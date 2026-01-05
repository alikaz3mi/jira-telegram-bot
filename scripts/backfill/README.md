# Backfill Scripts

Scripts for backfilling historical data and populating missing fields.

## Scripts

### `backfill_actual_dates.py`
Backfill actual start and end dates for issues.

```bash
python scripts/backfill/backfill_actual_dates.py
```

### `backfill_calculation_logs.py`
Backfill calculation logs for historical data.

```bash
python scripts/backfill/backfill_calculation_logs.py
```

### `backfill_reviewed_at.py`
Backfill review timestamps for issues.

```bash
python scripts/backfill/backfill_reviewed_at.py
```

### `backfill_task_tracking_fields.py`
Backfill task tracking fields.

```bash
python scripts/backfill/backfill_task_tracking_fields.py
```

### `backfill_team_evaluations.py`
Backfill team evaluation data.

```bash
python scripts/backfill/backfill_team_evaluations.py
```

### `populate_delay_reasons.py`
Populate delay reasons for issues.

```bash
python scripts/backfill/populate_delay_reasons.py
```

## Usage

Backfill scripts are typically run once to populate historical data or fix missing fields.

⚠️ **Warning**: Always backup your database before running backfill scripts!
