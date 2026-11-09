-- Migration 005: Day 4 Roles, Student Records, Campus Hiring & Batch Sharing
-- Non-destructive and idempotent.
--
-- Rollback note:
-- Reversible. Drop tables and columns if needed:
-- drop table if exists public.batch_sharing cascade;
-- drop table if exists public.campus_hiring cascade;
-- drop table if exists public.student_records cascade;
-- alter table public.outreach_drafts drop column if exists kind;
-- alter table public.user_saved_contacts drop column if exists status;
-- alter table public.profiles drop column if exists is_demo;
-- alter table public.profiles drop column if exists company_id;
-- alter table public.profiles drop column if exists college_id;
-- drop type if exists outreach_draft_kind;
-- drop type if exists campus_hiring_type;
-- drop type if exists student_status;
-- The 'kind' default ('outreach') preserves Day 3 drafts. No data-holding column is dropped.

-- enums (re-runnable)
do $$ begin
  create type student_status as enum ('in_college','internship','full_time','not_placed');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type campus_hiring_type as enum ('internship','full_time');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type outreach_draft_kind as enum ('outreach','invitation','interview','offer');
exception when duplicate_object then null;
end $$;

-- profiles links + demo flag
alter table public.profiles add column if not exists college_id uuid references public.colleges(id) on delete set null;
alter table public.profiles add column if not exists company_id  uuid references public.companies(id) on delete set null;
alter table public.profiles add column if not exists is_demo boolean not null default false;

-- outreach drafts: add a kind (default preserves Day 3 behaviour)
alter table public.outreach_drafts add column if not exists kind outreach_draft_kind not null default 'outreach';

-- user_saved_contacts: status column (Task 7.1 / Decision #8)
alter table public.user_saved_contacts add column if not exists status text not null default 'not_contacted';

-- student_records
create table if not exists public.student_records (
  id uuid primary key default gen_random_uuid(),
  college_id uuid not null references public.colleges(id) on delete cascade,
  full_name text not null,
  email text,                                 -- college email; claim key; hidden from company/recruiter
  batch_year int not null check (batch_year in (2027,2028)),
  branch text,
  degree text,
  score_value numeric,                        -- cgpa or percentage
  score_scale score_scale,                    -- reuse Day 2 enum ('percentage','gpa10','cgpa10','cgpa4')
  current_status student_status not null default 'in_college',
  resume_ref text,                            -- reference to a documents row / storage path
  claimed_by_profile_id uuid references public.profiles(id) on delete set null,
  discoverable boolean not null default false,  -- Future Work: individual toggle; not used in Day 4 visibility rule
  opted_out boolean not null default false,
  is_demo_data boolean not null default false,  -- synthetic demo records; visible only to is_demo profiles
  created_by_profile_id uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists student_records_college_batch_idx on public.student_records (college_id, batch_year);
create unique index if not exists student_records_college_email_uidx on public.student_records (college_id, lower(coalesce(email,''))) where email is not null;
create index if not exists student_records_claimed_profile_idx on public.student_records (claimed_by_profile_id);
create index if not exists student_records_demo_idx on public.student_records (is_demo_data);

-- campus_hiring
create table if not exists public.campus_hiring (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete set null,
  college_id uuid not null references public.colleges(id) on delete cascade,
  cycle_year int not null,
  type campus_hiring_type not null,
  students_interviewed int not null default 0,
  offers_made int not null default 0,
  profile_id uuid not null references public.profiles(id) on delete cascade,  -- the company user who recorded it
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists campus_hiring_company_college_cycle_type_uidx
  on public.campus_hiring (company_id, college_id, cycle_year, type);
create index if not exists campus_hiring_company_idx on public.campus_hiring (company_id);
create index if not exists campus_hiring_college_idx on public.campus_hiring (college_id, cycle_year);

-- batch_sharing (per college + batch)
create table if not exists public.batch_sharing (
  id uuid primary key default gen_random_uuid(),
  college_id uuid not null references public.colleges(id) on delete cascade,
  batch_year int not null check (batch_year in (2027,2028)),
  shared_with_recruiters boolean not null default false,
  set_by_profile_id uuid references public.profiles(id) on delete set null,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create unique index if not exists batch_sharing_college_batch_uidx on public.batch_sharing (college_id, batch_year);

-- Enable RLS on every new table
alter table public.student_records enable row level security;
alter table public.campus_hiring   enable row level security;
alter table public.batch_sharing   enable row level security;

-- Officer sees student_records of their own college (profiles.college_id)
drop policy if exists "student_records officer" on public.student_records;
create policy "student_records officer" on public.student_records for select using (
  exists (select 1 from public.profiles p where p.id = auth.uid() and p.college_id = student_records.college_id)
);

-- Student sees their own claimed record
drop policy if exists "student_records self" on public.student_records;
create policy "student_records self" on public.student_records for select using (auth.uid() = claimed_by_profile_id);

-- Company sees only their own campus_hiring rows (the rows they recorded)
drop policy if exists "campus_hiring self" on public.campus_hiring;
create policy "campus_hiring self" on public.campus_hiring for select using (auth.uid() = profile_id);

-- Officer manages batch_sharing for their own college
drop policy if exists "batch_sharing officer" on public.batch_sharing;
create policy "batch_sharing officer" on public.batch_sharing for select using (
  exists (select 1 from public.profiles p where p.id = auth.uid() and p.college_id = batch_sharing.college_id)
);

