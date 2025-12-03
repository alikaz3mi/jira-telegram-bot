-- Create PostgreSQL extensions for Jira Telegram Bot
-- This script runs automatically when the database is first initialized

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable JSON functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enable full-text search enhancements
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enable additional statistics
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Log extension creation
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL extensions created successfully';
    RAISE NOTICE 'Database ready for Jira Telegram Bot';
END $$;
