# Quick Start Guide - PostgreSQL with Docker

## Start Database

```bash
# Navigate to docker directory
cd docker

# Create environment file (first time only)
cp .env.example .env

# Edit passwords in .env
nano .env  # or use your preferred editor

# Start PostgreSQL and pgAdmin
docker-compose up -d

# Check status
docker-compose ps
```

## Run Migrations

```bash
# From project root
python scripts/run_migrations.py
```

## Access Database

### Via Command Line
```bash
docker-compose exec postgres psql -U jira_bot -d jira_telegram_bot
```

### Via pgAdmin
Open browser: http://localhost:5050
- Email: admin@jirabot.local (or your value from .env)
- Password: admin (or your value from .env)

## Application Configuration

Your `.env` file in project root should have:
```
db_user="jira_bot"
db_password="your_password_here"
db_host="localhost"
db_port=5432
db_name="jira_telegram_bot"
```

## Stop Database

```bash
cd docker
docker-compose down

# To also remove data (⚠️ destroys all data)
docker-compose down -v
```

## Full Documentation

See [docker/README.md](./README.md) for complete documentation including:
- Configuration options
- Performance tuning
- Backup/restore procedures
- Troubleshooting
- Security best practices
