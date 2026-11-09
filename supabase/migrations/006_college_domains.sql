-- Migration: 006_college_domains.sql
-- Description: Adds college_domains table for resolving colleges from verified email domains.
-- Non-destructive, idempotent, with Row Level Security enabled.
-- Rollback: DROP TABLE IF EXISTS college_domains CASCADE;

CREATE TABLE IF NOT EXISTS college_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    college_id UUID NOT NULL REFERENCES colleges(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('student', 'staff')),
    source_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (domain),
    CONSTRAINT college_domains_domain_lower CHECK (domain = lower(domain))
);

-- Index for domain lookups
CREATE INDEX IF NOT EXISTS idx_college_domains_domain ON college_domains(domain);
CREATE INDEX IF NOT EXISTS idx_college_domains_college ON college_domains(college_id);

-- Enable Row Level Security
ALTER TABLE college_domains ENABLE ROW LEVEL SECURITY;

-- Read policy: accessible by authenticated users
DROP POLICY IF EXISTS "college_domains_read_auth" ON college_domains;
CREATE POLICY "college_domains_read_auth" ON college_domains
    FOR SELECT TO authenticated USING (true);

-- Writes are restricted to service_role (service role key bypasses RLS)
