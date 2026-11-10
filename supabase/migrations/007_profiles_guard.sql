-- Migration 007: Profiles guard trigger
-- Prevents authenticated users from altering privileged columns: role, is_demo, college_id, company_id.
-- Privileged updates can only be executed by service_role.

create or replace function public.guard_profile_privileged_columns()
returns trigger
language plpgsql
security definer
as $$
begin
  -- If invoked by service_role, allow all updates
  if auth.role() = 'service_role' then
    return new;
  end if;

  -- Authenticated users cannot change role, is_demo, college_id, or company_id
  if (new.role is distinct from old.role) then
    raise exception 'Changing profile role is not permitted.';
  end if;

  if (new.is_demo is distinct from old.is_demo) then
    raise exception 'Changing profile is_demo status is not permitted.';
  end if;

  if (new.college_id is distinct from old.college_id) then
    raise exception 'Changing profile college_id is not permitted.';
  end if;

  if (new.company_id is distinct from old.company_id) then
    raise exception 'Changing profile company_id is not permitted.';
  end if;

  return new;
end;
$$;

drop trigger if exists tr_guard_profile_columns on public.profiles;

create trigger tr_guard_profile_columns
before update on public.profiles
for each row
execute function public.guard_profile_privileged_columns();
