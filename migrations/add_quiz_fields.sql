-- Migration: Add quiz fields to users table
-- Run this SQL against your PostgreSQL database before deploying the updated bot.

ALTER TABLE users ADD COLUMN IF NOT EXISTS quiz_answers JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS quiz_score INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS quiz_user_type VARCHAR(1);
ALTER TABLE users ADD COLUMN IF NOT EXISTS quiz_name_entered VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS quiz_completed_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS quiz_followup_step INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS quiz_followup_last_at TIMESTAMPTZ;
