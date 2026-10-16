-- ENG-P34: pin official bot roster entries to immutable canonical Skill versions.
-- Source-only. Validate schema/RLS/retention and all dependent contracts in approved
-- isolated ENG-P37 staging before applying anywhere; never apply to Production directly.

alter table public.official_agent_bots
  add column if not exists skill_version_id uuid
    references public.agent_skill_versions(id) on delete restrict,
  add column if not exists skill_version_number integer
    check (skill_version_number is null or skill_version_number > 0),
  add column if not exists skill_version_digest text
    check (skill_version_digest is null or skill_version_digest ~ '^[a-f0-9]{64}$');

alter table public.official_agent_bots
  add constraint official_agent_bots_active_skill_version_required
  check (
    status <> 'active'
    or (
      skill_version_id is not null
      and skill_version_number is not null
      and skill_version_digest is not null
      and skill_version_digest ~ '^[a-f0-9]{64}$'
    )
  );

-- Snapshot rows may be removed only through the existing privacy/retention lifecycle,
-- but their content cannot be rewritten after creation, including by service_role.
create or replace function public.prevent_agent_skill_version_update()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  raise exception 'agent_skill_versions are immutable; create a new version instead'
    using errcode = '55000';
end;
$$;

revoke all on function public.prevent_agent_skill_version_update() from public, anon, authenticated;
drop trigger if exists agent_skill_versions_immutable_update on public.agent_skill_versions;
create trigger agent_skill_versions_immutable_update
  before update on public.agent_skill_versions
  for each row execute function public.prevent_agent_skill_version_update();

comment on column public.official_agent_bots.skill_version_id is
  'Pinned immutable canonical Agent Skill version; catalog membership alone never grants execution.';
comment on column public.official_agent_bots.skill_version_digest is
  'SHA-256 of canonical JSON snapshot captured at runtime-link review; checked again before activation.';
comment on function public.prevent_agent_skill_version_update() is
  'Prevents mutation of an immutable Skill version snapshot; create a new version instead.';
