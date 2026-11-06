-- Migration 002_student_slice.sql
-- Matching recruiting platform MVP specification Day 2 Student slice

-- Enum Types
do $$ begin
  create type education_level as enum ('tenth','twelfth','bachelors','masters','other');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type score_scale as enum ('percentage','gpa10','cgpa10','cgpa4');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type document_kind as enum ('resume','id_proof','certificate','other');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type verification_status as enum ('pending','pre_verified','rejected');
exception
  when duplicate_object then null;
end $$;

-- 1. education
create table if not exists public.education (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references public.students(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  level education_level not null,
  institution text,
  degree text,
  branch text,
  board_or_university text,
  score_value numeric,
  score_scale score_scale,
  start_year int,
  end_year int,
  source text not null,                                   -- 'resume' | 'user_said'
  confidence numeric not null default 1.0 check (confidence between 0 and 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists education_student_idx on public.education (student_id, level);
create unique index if not exists education_student_level_uidx on public.education (student_id, level);

drop trigger if exists tr_education_updated_at on public.education;
create trigger tr_education_updated_at
  before update on public.education
  for each row execute function public.set_updated_at();

-- 2. internships
create table if not exists public.internships (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references public.students(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  company text,
  company_id uuid references public.companies(id) on delete set null,
  role text,
  start_date date,
  end_date date,
  duration_months numeric,
  source text not null,                                   -- 'resume' | 'user_said'
  confidence numeric not null default 1.0 check (confidence between 0 and 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists internships_student_idx on public.internships (student_id);
create unique index if not exists internships_student_company_role_uidx
  on public.internships (student_id, lower(coalesce(company,'')), lower(coalesce(role,'')));

drop trigger if exists tr_internships_updated_at on public.internships;
create trigger tr_internships_updated_at
  before update on public.internships
  for each row execute function public.set_updated_at();

-- 3. jobs
create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references public.students(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  company text,
  company_id uuid references public.companies(id) on delete set null,
  role text,
  start_date date,
  end_date date,                                           -- null = current
  duration_months numeric,
  source text not null,                                   -- 'resume' | 'user_said'
  confidence numeric not null default 1.0 check (confidence between 0 and 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists jobs_student_idx on public.jobs (student_id);
create unique index if not exists jobs_student_company_role_uidx
  on public.jobs (student_id, lower(coalesce(company,'')), lower(coalesce(role,'')));

drop trigger if exists tr_jobs_updated_at on public.jobs;
create trigger tr_jobs_updated_at
  before update on public.jobs
  for each row execute function public.set_updated_at();

-- 4. skills
create table if not exists public.skills (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references public.students(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  proficiency text,
  source text not null,                                   -- 'resume' | 'user_said'
  confidence numeric not null default 1.0 check (confidence between 0 and 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists skills_student_name_uidx on public.skills (student_id, lower(name));

drop trigger if exists tr_skills_updated_at on public.skills;
create trigger tr_skills_updated_at
  before update on public.skills
  for each row execute function public.set_updated_at();

-- 5. documents
create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references public.students(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  kind document_kind not null default 'resume',
  storage_path text not null,                             -- path in private Storage bucket
  file_name text,
  mime_type text,
  size_bytes bigint,
  verification_status verification_status not null default 'pending',
  uploaded_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists documents_student_idx on public.documents (student_id);

drop trigger if exists tr_documents_updated_at on public.documents;
create trigger tr_documents_updated_at
  before update on public.documents
  for each row execute function public.set_updated_at();

-- 6. score_events
create table if not exists public.score_events (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references public.students(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  score int not null,
  breakdown jsonb not null,                                -- [{reason, points, source}]
  next_best_actions jsonb not null default '[]'::jsonb,
  documents_pre_verified boolean not null default false,
  reference_check_authorized boolean not null default false,
  trigger text,                                           -- 'resume_parsed' | 'chat_upsert' | 'manual'
  created_at timestamptz not null default now()
);
create index if not exists score_events_student_idx on public.score_events (student_id, created_at desc);

-- Row Level Security (RLS)
alter table public.education    enable row level security;
alter table public.internships  enable row level security;
alter table public.jobs         enable row level security;
alter table public.skills       enable row level security;
alter table public.documents    enable row level security;
alter table public.score_events enable row level security;

-- Policies (auth.uid() = profile_id, SELECT only - writes via service role)
drop policy if exists "education self" on public.education;
create policy "education self" on public.education for select using (auth.uid() = profile_id);

drop policy if exists "internships self" on public.internships;
create policy "internships self" on public.internships for select using (auth.uid() = profile_id);

drop policy if exists "jobs self" on public.jobs;
create policy "jobs self" on public.jobs for select using (auth.uid() = profile_id);

drop policy if exists "skills self" on public.skills;
create policy "skills self" on public.skills for select using (auth.uid() = profile_id);

drop policy if exists "documents self" on public.documents;
create policy "documents self" on public.documents for select using (auth.uid() = profile_id);

drop policy if exists "score_events self" on public.score_events;
create policy "score_events self" on public.score_events for select using (auth.uid() = profile_id);

-- Storage bucket for resumes (private, no public read access)
do $$ begin
  if exists (
    select from pg_tables
    where schemaname = 'storage' and tablename = 'buckets'
  ) then
    insert into storage.buckets (id, name, public)
    values ('resumes', 'resumes', false)
    on conflict (id) do nothing;
  end if;
end $$;

