-- Migration 001_init.sql
-- Matching recruiting platform MVP specification

-- Extensions
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- Enum Types
do $$ begin
  create type profile_role as enum ('student', 'placement_officer', 'company', 'recruiter');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type agent_run_status as enum ('running', 'completed', 'failed');
exception
  when duplicate_object then null;
end $$;

-- Helper function for updated_at
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- 1. profiles
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role profile_role,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists tr_profiles_updated_at on public.profiles;
create trigger tr_profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- 2. colleges
create table if not exists public.colleges (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  city text not null default 'Mumbai',
  owner_id uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists colleges_name_city_uidx on public.colleges (lower(name), lower(city));

drop trigger if exists tr_colleges_updated_at on public.colleges;
create trigger tr_colleges_updated_at
  before update on public.colleges
  for each row execute function public.set_updated_at();

-- 3. companies
create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  industry text,
  owner_id uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists companies_name_uidx on public.companies (lower(name));

drop trigger if exists tr_companies_updated_at on public.companies;
create trigger tr_companies_updated_at
  before update on public.companies
  for each row execute function public.set_updated_at();

-- 4. contacts
create table if not exists public.contacts (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete cascade,
  full_name text not null,
  title text,
  email text,
  phone text,
  owner_id uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists contacts_company_email_uidx on public.contacts (company_id, lower(coalesce(email,'')));

drop trigger if exists tr_contacts_updated_at on public.contacts;
create trigger tr_contacts_updated_at
  before update on public.contacts
  for each row execute function public.set_updated_at();

-- 5. students
create table if not exists public.students (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  college_id uuid references public.colleges(id) on delete set null,
  full_name text not null,
  batch_year int not null check (batch_year in (2027, 2028)),
  degree text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists students_profile_uidx on public.students (profile_id);

drop trigger if exists tr_students_updated_at on public.students;
create trigger tr_students_updated_at
  before update on public.students
  for each row execute function public.set_updated_at();

-- 6. raw_events
create table if not exists public.raw_events (
  id uuid primary key default gen_random_uuid(),
  payload jsonb not null,
  source text not null,           -- 'user_message' | 'agent_message' | 'tool_call' | 'tool_result'
  source_url text,
  actor_id uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists raw_events_actor_created_idx on public.raw_events (actor_id, created_at desc);

-- 7. agent_runs
create table if not exists public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  status agent_run_status not null default 'running',
  steps jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists agent_runs_profile_idx on public.agent_runs (profile_id, created_at desc);

drop trigger if exists tr_agent_runs_updated_at on public.agent_runs;
create trigger tr_agent_runs_updated_at
  before update on public.agent_runs
  for each row execute function public.set_updated_at();

-- Row Level Security (RLS)
alter table public.profiles   enable row level security;
alter table public.colleges   enable row level security;
alter table public.companies  enable row level security;
alter table public.contacts   enable row level security;
alter table public.students   enable row level security;
alter table public.raw_events enable row level security;
alter table public.agent_runs enable row level security;

-- Policies for profiles
drop policy if exists "profiles self select" on public.profiles;
create policy "profiles self select" on public.profiles for select using (auth.uid() = id);

drop policy if exists "profiles self insert" on public.profiles;
create policy "profiles self insert" on public.profiles for insert with check (auth.uid() = id);

drop policy if exists "profiles self update" on public.profiles;
create policy "profiles self update" on public.profiles for update using (auth.uid() = id);

-- Policies for colleges, companies, contacts, students
drop policy if exists "colleges owner" on public.colleges;
create policy "colleges owner" on public.colleges for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

drop policy if exists "companies owner" on public.companies;
create policy "companies owner" on public.companies for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

drop policy if exists "contacts owner" on public.contacts;
create policy "contacts owner" on public.contacts for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

drop policy if exists "students self" on public.students;
create policy "students self" on public.students for all using (auth.uid() = profile_id) with check (auth.uid() = profile_id);

-- Policies for raw_events & agent_runs
drop policy if exists "raw_events actor" on public.raw_events;
create policy "raw_events actor" on public.raw_events for select using (auth.uid() = actor_id);

drop policy if exists "agent_runs self" on public.agent_runs;
create policy "agent_runs self" on public.agent_runs for select using (auth.uid() = profile_id);

-- Auto-provision profile on auth.users insert
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.email))
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql security definer;

do $$ begin
  if exists (
    select from pg_tables
    where schemaname = 'auth' and tablename = 'users'
  ) then
    drop trigger if exists on_auth_user_created on auth.users;
    create trigger on_auth_user_created
      after insert on auth.users
      for each row execute function public.handle_new_user();
  end if;
end $$;

-- Enable Realtime for raw_events table
do $$ begin
  if exists (
    select 1 from pg_publication where pubname = 'supabase_realtime'
  ) then
    alter publication supabase_realtime add table public.raw_events;
  end if;
exception
  when duplicate_object then null;
end $$;
