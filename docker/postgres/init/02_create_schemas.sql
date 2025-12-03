-- Create database schemas for Jira Telegram Bot
-- This organizes tables into logical groupings

-- Main application schema (default - public)
-- Tables: jira_tasks_enhanced, git_commit, sync_status, schema_migrations

-- Create reporting schema for views
CREATE SCHEMA IF NOT EXISTS reporting;

-- Create analytics schema for aggregated data
CREATE SCHEMA IF NOT EXISTS analytics;

-- Grant permissions
GRANT USAGE ON SCHEMA reporting TO PUBLIC;
GRANT USAGE ON SCHEMA analytics TO PUBLIC;

-- Set default search path
ALTER DATABASE jira_telegram_bot SET search_path TO public, reporting, analytics;

-- Log schema creation
DO $$
BEGIN
    RAISE NOTICE 'Database schemas created successfully';
    RAISE NOTICE '  - public (main tables)';
    RAISE NOTICE '  - reporting (Grafana views)';
    RAISE NOTICE '  - analytics (aggregated data)';
END $$;
