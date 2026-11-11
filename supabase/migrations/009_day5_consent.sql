-- Migration 009: Day 5 Consent Flows & Pre-Verification Metadata
-- Non-destructive and idempotent.
--
-- Rollback note:
-- drop table if exists public.reference_authorizations cascade;
-- alter table public.documents drop column if exists verification_note;
-- alter table public.documents drop column if exists verified_at;
-- alter table public.documents drop column if exists verified_flag;
-- alter table public.documents drop column if exists masked_id_tail;
-- alter table public.documents drop column if exists document_type;
--
-- HARD RULES (enforced in application code, not just here):
--   • The mock verification NEVER reads document file contents.
--   • Nothing from a document is sent to any LLM, OCR or log.
--   • Scoring flags are set only from DB state.
--   • Consent is granted only via authenticated confirm endpoints;
--     chat tools may PROPOSE consent but NEVER grant it.
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

create unique index if not exists ref_auth_student_active_uidx
  on public.reference_authorizations (student_id)
  where revoked_at is null;

create index if not exists ref_auth_profile_idx
  on public.reference_authorizations (profile_id);

-- Enable RLS
alter table public.reference_authorizations enable row level security;

drop policy if exists "ref_auth self" on public.reference_authorizations;
create policy "ref_auth self" on public.reference_authorizations
  for select using (auth.uid() = profile_id);

drop policy if exists "ref_auth student modify" on public.reference_authorizations;
create policy "ref_auth student modify" on public.reference_authorizations
  for all using (auth.uid() = profile_id);

-- 2. Document verification metadata additions
-- Stored: document_type, masked last digits, verified flag, verified_at, private storage path.
-- NOT stored: full Aadhaar/PAN numbers, address text, pgcrypto-encrypted blobs,
--             verified_fields JSONB, any text extracted from the document.
alter table public.documents add column if not exists document_type   text;
alter table public.documents add column if not exists masked_id_tail  text;
alter table public.documents add column if not exists verified_flag   boolean not null default false;
alter table public.documents add column if not exists verified_at     timestamptz;
alter table public.documents add column if not exists verification_note text;

-- 3. Labelled UPDATE backfill: demo/seed documents only (profiles.is_demo = true)
-- Production rows are untouched.
update public.documents d
set verified_flag = true
where d.verification_status = 'pre_verified'
  and d.verified_flag = false
  and exists (
    select 1
    from public.students s
    join public.profiles p on p.id = s.profile_id
    where s.id = d.student_id
      and p.is_demo = true
  );
