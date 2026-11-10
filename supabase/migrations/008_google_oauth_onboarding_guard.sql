-- Migration 008: Google OAuth onboarding guard adjustment
-- Allows authenticated users to set role, college_id, company_id if they were previously NULL (first-time onboarding),
-- while continuing to prevent changing already-assigned privileged values.

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

  -- Authenticated users cannot change role once assigned (allows initial setting during onboarding)
  if (old.role is not null and new.role is distinct from old.role) then
    raise exception 'Changing profile role is not permitted.';
  end if;

  -- Authenticated users cannot change is_demo
  if (new.is_demo is distinct from old.is_demo) then
    raise exception 'Changing profile is_demo status is not permitted.';
  end if;

  -- Authenticated users cannot change college_id once assigned
  if (old.college_id is not null and new.college_id is distinct from old.college_id) then
    raise exception 'Changing profile college_id is not permitted.';
  end if;

  -- Authenticated users cannot change company_id once assigned
  if (old.company_id is not null and new.company_id is distinct from old.company_id) then
    raise exception 'Changing profile company_id is not permitted.';
  end if;

  return new;
end;
$$;
