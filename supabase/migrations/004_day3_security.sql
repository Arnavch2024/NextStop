-- Make sure RLS is on everywhere it must be
alter table public.contacts enable row level security;
alter table public.companies enable row level security;
alter table public.colleges enable row level security;
alter table public.contact_sources enable row level security;

-- Lake reads must not expose suppressed contacts
drop policy if exists "contacts lake read" on public.contacts;
create policy "contacts lake read" on public.contacts
  for select to authenticated using (suppressed_at is null);

drop policy if exists "contact_sources lake read" on public.contact_sources;
create policy "contact_sources lake read" on public.contact_sources
  for select to authenticated using (
    exists (select 1 from public.contacts c
            where c.id = contact_sources.contact_id and c.suppressed_at is null)
  );

-- Legacy phone numbers must not be readable through the shared lake
update public.contacts set phone = null where phone is not null;

-- Live updates for the saved list
do $$ begin
  begin
    alter publication supabase_realtime add table public.user_saved_contacts;
  exception
    when duplicate_object then null;
    when undefined_object then null;
  end;
end $$;
