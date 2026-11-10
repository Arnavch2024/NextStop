-- Migration 008: Profiles guard trigger rewrite
-- Clients (role authenticated or anon) may set profiles.role only while it is NULL or 'student'.
-- Clients may NEVER change is_demo, college_id or company_id, including from NULL.
-- Those columns are set only by the server with the service role.

-- Clean up any older/competing functions and triggers
drop trigger if exists protect_profile_columns_trg on public.profiles;
drop trigger if exists tr_guard_profile_columns on public.profiles;
drop trigger if exists protect_profile_columns on public.profiles;
drop function if exists public.protect_profile_columns();
drop function if exists public.guard_profile_privileged_columns();

create or replace function public.guard_profile_privileged_columns()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  -- Service role bypasses all client guards
  if auth.role() = 'service_role' then
    return new;
  end if;

  if tg_op = 'INSERT' then
    -- Clients may NEVER set is_demo, college_id or company_id
    if (new.is_demo is not null and new.is_demo is distinct from false) then
      raise exception 'Setting profile is_demo is not permitted.';
    end if;

    if (new.college_id is not null) then
      raise exception 'Setting profile college_id is not permitted.';
    end if;

    if (new.company_id is not null) then
      raise exception 'Setting profile company_id is not permitted.';
    end if;

    return new;
  end if;

  -- TG_OP = 'UPDATE'
  -- Clients may set profiles.role only while it is NULL or 'student'
  if (old.role is not null and old.role <> 'student' and new.role is distinct from old.role) then
    raise exception 'Changing profile role is not permitted.';
  end if;

  -- Clients may NEVER change is_demo, college_id or company_id, including from NULL
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

create trigger tr_guard_profile_columns
before insert or update on public.profiles
for each row
execute function public.guard_profile_privileged_columns();
