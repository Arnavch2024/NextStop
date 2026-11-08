-- Migration 003_search_slice.sql
-- Day 3: Shared Contact Data Lake & Supporting Tables
--
-- ROLLBACK NOTE:
-- This migration is fully non-destructive and reversible:
-- 1. To revert contact renaming:
--      alter table public.contacts rename column name to full_name;
-- 2. New columns, tables, and constraints can be dropped safely:
--      alter table public.contacts drop column if exists college_id, drop column if exists role_type,
--        drop column if exists linkedin_url, drop column if exists source, drop column if exists source_url,
--        drop column if exists confidence, drop column if exists first_seen_at, drop column if exists last_verified_at,
--        drop column if exists created_by_profile_id, drop column if exists suppressed_at;
--      alter table public.companies drop column if exists category;
--      alter table public.colleges drop constraint if exists colleges_mumbai_chk;
--      drop table if exists public.contact_sources cascade;
--      drop table if exists public.search_cache cascade;
--      drop table if exists public.user_saved_contacts cascade;
--      drop table if exists public.outreach_drafts cascade;
--      drop type if exists contact_role_type;
-- 3. The deprecated phone and owner_id columns were never dropped, so no data restore is required.
-- 4. To restore the legacy unique index:
--      create unique index contacts_company_email_uidx on public.contacts (company_id, lower(coalesce(email,'')));

-- 1. Enum Types
do $$ begin
  create type contact_role_type as enum ('campus_recruiter', 'placement_officer', 'hr', 'other');
exception
  when duplicate_object then null;
end $$;

-- 2. Migrate existing contacts table to Shared Lake (non-destructive + guarded)
do $$ begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'contacts' and column_name = 'full_name'
  ) then
    alter table public.contacts rename column full_name to name;
  end if;
end $$;

alter table public.contacts add column if not exists college_id uuid references public.colleges(id) on delete set null;
alter table public.contacts add column if not exists role_type contact_role_type not null default 'other';
alter table public.contacts add column if not exists linkedin_url text;
alter table public.contacts add column if not exists source text not null default 'user_said';
alter table public.contacts add column if not exists source_url text;
alter table public.contacts add column if not exists confidence numeric not null default 1.0 check (confidence between 0 and 1);
alter table public.contacts add column if not exists first_seen_at timestamptz not null default now();
alter table public.contacts add column if not exists last_verified_at timestamptz;
alter table public.contacts add column if not exists created_by_profile_id uuid references public.profiles(id) on delete set null;
alter table public.contacts add column if not exists suppressed_at timestamptz;
alter table public.contacts add column if not exists location text;
alter table public.contacts add column if not exists source_published_date text;
alter table public.contacts add column if not exists stale boolean;

-- Backfill audit column from legacy owner_id (owner_id & phone are retained deprecated)
update public.contacts
   set created_by_profile_id = owner_id
 where created_by_profile_id is null and owner_id is not null;

-- Swap legacy unique index for multi-key dedupe / FTS / active indexes
drop index if exists contacts_company_email_uidx;
create index if not exists contacts_company_idx on public.contacts (company_id);
create index if not exists contacts_college_idx on public.contacts (college_id);
create unique index if not exists contacts_linkedin_uidx on public.contacts (lower(linkedin_url)) where linkedin_url is not null;
create unique index if not exists contacts_email_uidx on public.contacts (lower(email)) where email is not null;
create index if not exists contacts_fts_idx on public.contacts
  using gin (to_tsvector('english', coalesce(name,'') || ' ' || coalesce(title,'')));
create index if not exists contacts_active_idx on public.contacts (company_id) where suppressed_at is null;

-- 3. Companies & Colleges updates
alter table public.companies add column if not exists category text;

do $$ begin
  if not exists (
    select 1 from pg_constraint where conname = 'colleges_mumbai_chk'
  ) then
    alter table public.colleges add constraint colleges_mumbai_chk check (lower(city) = 'mumbai');
  end if;
end $$;

-- 4. contact_sources (provenance)
create table if not exists public.contact_sources (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid not null references public.contacts(id) on delete cascade,
  source text not null,                 -- 'seed' | 'resume' | 'user_said' | 'web'
  source_url text,
  fetched_at timestamptz,
  confidence numeric not null default 1.0,
  unverified boolean not null default false,   -- true for user_said contributions or unverified web sources
  fetch_status text,                     -- 'ok' | 'blocked' | 'not_fetched'
  published_date text,                   -- article / result publication date if provided
  note text,                             -- e.g. 'synthetic'
  created_at timestamptz not null default now()
);
alter table public.contact_sources add column if not exists fetch_status text;
alter table public.contact_sources add column if not exists published_date text;

create index if not exists contact_sources_contact_idx on public.contact_sources (contact_id);

-- 5. search_cache (server-only, 7-day TTL)
create table if not exists public.search_cache (
  id uuid primary key default gen_random_uuid(),
  query_hash text not null,             -- sha256 of normalized query + purpose
  query text not null,
  provider text not null,
  purpose text,
  result jsonb not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);
create unique index if not exists search_cache_hash_uidx on public.search_cache (query_hash);
create index if not exists search_cache_expires_idx on public.search_cache (expires_at);

-- 6. user_saved_contacts (private saved list per user)
create table if not exists public.user_saved_contacts (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  contact_id uuid not null references public.contacts(id) on delete cascade,
  saved_at timestamptz not null default now(),
  note text,
  phone text,                           -- user-provided ONLY; never written to shared lake
  user_overrides jsonb,                 -- conflicting user-stated fields, e.g. {"title":"Senior SDE"}
  unverified boolean not null default false,   -- true when row holds unverified user input
  created_at timestamptz not null default now()
);
create unique index if not exists user_saved_contacts_profile_contact_uidx on public.user_saved_contacts (profile_id, contact_id);
create index if not exists user_saved_contacts_profile_idx on public.user_saved_contacts (profile_id);

-- 7. outreach_drafts (private drafts per user; never sent)
create table if not exists public.outreach_drafts (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  contact_id uuid references public.contacts(id) on delete set null,
  channel text not null,                -- 'email' | 'linkedin'
  subject text,
  body text not null,
  created_at timestamptz not null default now()
);
create index if not exists outreach_drafts_profile_idx on public.outreach_drafts (profile_id, created_at desc);

-- 8. Row Level Security (RLS) Updates

-- Shared lake: readable by every authenticated user; writes via service role only
drop policy if exists "contacts owner" on public.contacts;
drop policy if exists "companies owner" on public.companies;
drop policy if exists "colleges owner" on public.colleges;
drop policy if exists "contacts lake read" on public.contacts;
drop policy if exists "companies lake read" on public.companies;
drop policy if exists "colleges lake read" on public.colleges;
drop policy if exists "contact_sources lake read" on public.contact_sources;

create policy "contacts lake read" on public.contacts for select to authenticated using (true);
create policy "companies lake read" on public.companies for select to authenticated using (true);
create policy "colleges lake read" on public.colleges for select to authenticated using (true);
create policy "contact_sources lake read" on public.contact_sources for select to authenticated using (true);

-- Private per user
alter table public.user_saved_contacts enable row level security;
alter table public.outreach_drafts enable row level security;

drop policy if exists "saved self" on public.user_saved_contacts;
create policy "saved self" on public.user_saved_contacts for all
  using (auth.uid() = profile_id) with check (auth.uid() = profile_id);

drop policy if exists "drafts self" on public.outreach_drafts;
create policy "drafts self" on public.outreach_drafts for all
  using (auth.uid() = profile_id) with check (auth.uid() = profile_id);

-- Server-only: clients cannot read or write the cache directly
alter table public.search_cache enable row level security;
-- (no SELECT/ALL policy means denied to anon & authenticated; service role bypasses RLS)
