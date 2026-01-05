# Migration Scripts

Database migration runner scripts.

## Scripts

### `run_migration_008.py`
Run specific migration #008.

```bash
python scripts/migration/run_migration_008.py
```

### `run_migration_011.py`
Run specific migration #011.

```bash
python scripts/migration/run_migration_011.py
```

## Usage

Migration scripts apply database schema changes. They should be run once per migration.

⚠️ **Warning**: Always backup your database before running migrations!

## Documentation

Migrations are defined in:
- `jira_telegram_bot/adapters/repositories/postgres/database/migrations/`
