# Docker PostgreSQL Setup for Jira Telegram Bot

This directory contains Docker Compose configuration for running PostgreSQL database locally.

## 📁 Directory Structure

```
docker/
├── docker-compose.yml          # Main Docker Compose configuration
├── .env.example               # Environment variables template
├── postgres/
│   ├── postgresql.conf        # PostgreSQL server configuration
│   ├── pg_hba.conf           # Client authentication configuration
│   ├── init/                 # Initialization scripts (run on first start)
│   │   ├── 01_create_extensions.sql
│   │   └── 02_create_schemas.sql
│   └── pgadmin/
│       └── servers.json      # pgAdmin pre-configured servers
```

## 🚀 Quick Start

### 1. Create Environment File

```bash
cd docker
cp .env.example .env
```

Edit `.env` and update the values (especially passwords):
```bash
POSTGRES_PASSWORD=your_secure_password
PGADMIN_PASSWORD=your_admin_password
```

### 2. Start PostgreSQL

```bash
# Start in foreground
docker-compose up

# Start in background (detached)
docker-compose up -d

# View logs
docker-compose logs -f postgres
```

### 3. Verify Database is Running

```bash
# Check container status
docker-compose ps

# Check database health
docker-compose exec postgres pg_isready -U jira_bot -d jira_telegram_bot
```

### 4. Run Migrations

From the project root directory:
```bash
python scripts/run_migrations.py
```

## 🔧 Configuration Details

### PostgreSQL Settings

| Setting | Value | Description |
|---------|-------|-------------|
| **Port** | 5432 | PostgreSQL connection port |
| **Database** | jira_telegram_bot | Database name |
| **User** | jira_bot | Database user |
| **Memory** | 256MB shared buffers | Optimized for moderate workloads |
| **Max Connections** | 100 | Maximum concurrent connections |

### Memory Configuration

The default configuration assumes **4GB RAM available**:
- `shared_buffers`: 256MB (25% of system memory)
- `effective_cache_size`: 1GB (50% of system memory)
- `work_mem`: 16MB
- `maintenance_work_mem`: 64MB

**Adjust for your system:**
- **8GB RAM**: Double the values
- **2GB RAM**: Halve the values

Edit `docker/postgres/postgresql.conf` to customize.

### Schemas

The database includes three schemas:
- **public**: Main tables (`jira_tasks_enhanced`, `git_commit`, `sync_status`)
- **reporting**: Grafana views for dashboards
- **analytics**: Aggregated data tables

### Extensions

Automatically installed extensions:
- `uuid-ossp`: UUID generation
- `pgcrypto`: Cryptographic functions
- `pg_trgm`: Full-text search improvements
- `pg_stat_statements`: Query statistics

## 🖥️ pgAdmin Web Interface

Access pgAdmin at: http://localhost:5050

**Default Credentials:**
- Email: `admin@jirabot.local`
- Password: Set in `.env` (`PGADMIN_PASSWORD`)

The PostgreSQL server is pre-configured and will appear automatically.

## 📊 Connecting from Application

### Using Environment Variables

Update your `.env` in the project root:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=jira_telegram_bot
POSTGRES_USER=jira_bot
POSTGRES_PASSWORD=your_password
```

### Using Connection String

```bash
DATABASE_URL=postgresql://jira_bot:your_password@localhost:5432/jira_telegram_bot
```

### From Python Code

The application automatically reads from settings:
```python
from jira_telegram_bot.settings.postgres_settings import PostgresSettings

settings = PostgresSettings()
# Connects using environment variables
```

## 🛠️ Common Operations

### View Logs
```bash
docker-compose logs -f postgres
```

### Access PostgreSQL Shell
```bash
docker-compose exec postgres psql -U jira_bot -d jira_telegram_bot
```

### Stop Services
```bash
docker-compose down
```

### Stop and Remove Volumes (⚠️ Deletes all data)
```bash
docker-compose down -v
```

### Restart Services
```bash
docker-compose restart
```

### Update Configuration

After editing `postgresql.conf` or `pg_hba.conf`:
```bash
docker-compose restart postgres
```

## 💾 Data Persistence

Data is stored in Docker volumes:
- **postgres_data**: Database files (persists across restarts)
- **pgadmin_data**: pgAdmin settings

Volumes are preserved even when containers are stopped.

### Backup Database

```bash
# Create backup
docker-compose exec postgres pg_dump -U jira_bot jira_telegram_bot > backup_$(date +%Y%m%d).sql

# Restore from backup
docker-compose exec -T postgres psql -U jira_bot jira_telegram_bot < backup_20241203.sql
```

## 🔒 Security Best Practices

### Development
- ✅ Current setup is fine for local development
- ✅ Change default passwords in `.env`

### Production
1. **Remove open access** from `pg_hba.conf`:
   ```diff
   - host    all    all    0.0.0.0/0    scram-sha-256
   + host    all    all    10.0.0.0/8   scram-sha-256
   ```

2. **Use strong passwords**:
   ```bash
   openssl rand -base64 32
   ```

3. **Enable SSL/TLS**:
   - Add SSL certificates to `docker/postgres/certs/`
   - Update `postgresql.conf`: `ssl = on`

4. **Restrict pgAdmin access**:
   - Use reverse proxy with authentication
   - Or disable pgAdmin service entirely

5. **Use Docker secrets** instead of environment variables

## 🐛 Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs postgres

# Common issue: port already in use
sudo lsof -i :5432
```

### Permission denied errors
```bash
# Fix volume permissions
docker-compose down -v
docker-compose up
```

### Connection refused
```bash
# Verify container is running
docker-compose ps

# Check health status
docker-compose exec postgres pg_isready

# Test connection
docker-compose exec postgres psql -U jira_bot -d jira_telegram_bot -c "SELECT 1"
```

### Out of memory
```bash
# Reduce memory settings in postgresql.conf
shared_buffers = 128MB
effective_cache_size = 512MB
```

## 📈 Performance Tuning

### For High-Load Production

Edit `docker/postgres/postgresql.conf`:
```ini
# Increase connections
max_connections = 200

# Increase memory
shared_buffers = 512MB
effective_cache_size = 2GB
work_mem = 32MB

# Enable parallel queries
max_worker_processes = 8
max_parallel_workers = 8
max_parallel_workers_per_gather = 4
```

### Monitor Performance

```sql
-- Check query statistics
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Check database size
SELECT pg_size_pretty(pg_database_size('jira_telegram_bot'));
```

## 🔗 Additional Resources

- [PostgreSQL Official Docs](https://www.postgresql.org/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [pgAdmin Documentation](https://www.pgadmin.org/docs/)
- [PostgreSQL Tuning Guide](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server)

## 📝 Notes

- **First run**: Initialization scripts in `init/` run automatically
- **Configuration changes**: Require container restart
- **Data persistence**: Volumes persist until explicitly removed
- **Network**: Services communicate via `jira-bot-network` bridge

---

**Need help?** Check the project's main README or open an issue.
