-- Migration 009: Day 5 Consent Flows & Pre-Verification Metadata
-- Non-destructive and idempotent.
--
-- Rollback note:
-- drop trigger if exists guard_document_verification on public.documents;
-- drop function if exists public.guard_document_verification();
-- drop table if exists public.reference_authorizations cascade;
-- drop table if exists public.consent_records cascade;
-- alter table public.documents drop column if exists verification_note;
-- alter table public.documents drop column if exists verified_at;
-- alter table public.documents drop column if exists verified_flag;
-- alter table public.documents drop column if exists masked_id_tail;
-- alter table public.documents drop column if exists document_type;
--
-- HARD RULES (enforced in application code and database triggers):
--   • The mock verification NEVER reads document file contents.
--   • Nothing from a document is sent to any LLM, OCR or log.
--   • Scoring flags are set only from DB state.
--   • Consent is granted only via authenticated confirm endpoints (service_role);
--     clients have NO write policy on reference_authorizations and cannot set
--     documents.verified_flag, verified_at, or masked_id_tail.
--     Chat tools may PROPOSE consent but NEVER grant it.
--     Text inside a resume or document can NEVER grant consent.

-- 1. Reference-check authorizations table
create table if not exists public.reference_authorizations (
  id              uuid primary key default gen_random_uuid(),
  student_id      uuid not null references public.students(id) on delete cascade,
  profile_id      uuid not null references public.profiles(id) on delete cascade,
  internship_id   uuid references public.internships(id) on delete set null,
  authorized_party text,
  authorized_role text,
  authorized_at   timestamptz not null default now(),
  revoked_at      timestamptz,
  created_at      timestamptz not null default now()
);

-- Drop older single-student active unique index if present
drop index if exists public.ref_auth_student_active_uidx;

-- Active authorization unique index per (student, internship, role, party)
create unique index if not exists ref_auth_active_party_uidx
  on public.reference_authorizations (student_id, internship_id, authorized_role, authorized_party)
  where revoked_at is null;

create index if not exists ref_auth_profile_idx
  on public.reference_authorizations (profile_id);

-- Enable RLS: Clients have READ-ONLY access to their own authorizations.
-- There is NO client write policy (all writes must go through server service-role).
alter table public.reference_authorizations enable row level security;

drop policy if exists "ref_auth student modify" on public.reference_authorizations;
drop policy if exists "ref_auth self" on public.reference_authorizations;
create policy "ref_auth self" on public.reference_authorizations
  for select using (auth.uid() = profile_id);

-- 2. Document verification metadata additions
alter table public.documents add column if not exists document_type   text;
alter table public.documents add column if not exists masked_id_tail  text;
alter table public.documents add column if not exists verified_flag   boolean not null default false;
alter table public.documents add column if not exists verified_at     timestamptz;
alter table public.documents add column if not exists verification_note text;

-- 3. Document verification guard trigger
-- Clients (role authenticated or anon) cannot set verified_flag, verified_at, or masked_id_tail.
-- Those columns are set only by the server with the service role.
create or replace function public.guard_document_verification()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  -- Only browser clients (authenticated or anon) are restricted; service_role is not
  if coalesce(auth.role(), '') not in ('authenticated', 'anon') then
    return new;
  end if;

  if tg_op = 'INSERT' then
    if (new.verified_flag is not null and new.verified_flag is distinct from false) then
      raise exception 'Setting document verified_flag is not permitted for clients.';
    end if;
    if (new.verified_at is not null) then
      raise exception 'Setting document verified_at is not permitted for clients.';
    end if;
    if (new.masked_id_tail is not null) then
      raise exception 'Setting document masked_id_tail is not permitted for clients.';
    end if;
    return new;
  end if;

  -- TG_OP = 'UPDATE'
  if (new.verified_flag is distinct from old.verified_flag) then
    raise exception 'Modifying document verified_flag is not permitted for clients.';
  end if;
  if (new.verified_at is distinct from old.verified_at) then
    raise exception 'Modifying document verified_at is not permitted for clients.';
  end if;
  if (new.masked_id_tail is distinct from old.masked_id_tail) then
    raise exception 'Modifying document masked_id_tail is not permitted for clients.';
  end if;

  return new;
end;
$$;

drop trigger if exists guard_document_verification on public.documents;
create trigger guard_document_verification
  before insert or update on public.documents
  for each row execute function public.guard_document_verification();

-- 4. Compatibility: consent_records table with read-only client RLS
create table if not exists public.consent_records (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  consent_type text not null,
  granted boolean not null default true,
  granted_at timestamptz not null default now(),
  revoked_at timestamptz,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.consent_records enable row level security;

drop policy if exists "consent_records self" on public.consent_records;
create policy "consent_records self" on public.consent_records
  for select using (auth.uid() = profile_id);

-- 5. Labelled UPDATE backfill: demo/seed documents only (profiles.is_demo = true)
update public.documents d
set verified_flag = true,
    verification_note = 'Demo verification (mocked)'
where d.verification_status = 'pre_verified'
  and d.verified_flag = false
  and exists (
    select 1
    from public.students s
    join public.profiles p on p.id = s.profile_id
    where s.id = d.student_id
      and p.is_demo = true
  );
