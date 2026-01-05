# Notification Services

Scripts for running notification and service daemons.

## Scripts

### `run_deadline_notifier.py`
Sends deadline notifications to Telegram users and groups.

```bash
python scripts/notifications/run_deadline_notifier.py
```

### `run_synth_pm_service.py`
Multi-project SynthPM synchronization service.

```bash
python scripts/notifications/run_synth_pm_service.py
```

### `run_synth_pm.py`
SynthPM service runner.

```bash
python scripts/notifications/run_synth_pm.py service
```

## Docker Services

These scripts typically run as Docker services. See `docker-compose.yml`:

```yaml
synth-pm-multi-project-service:
  command: python3 scripts/notifications/run_synth_pm_service.py
  
deadline-notifier-service:
  command: python3 scripts/notifications/run_deadline_notifier.py
```

## Documentation

See [docs/features/notifications/](../../docs/features/notifications/) for detailed documentation.
