-- ENG-P06 immutable published versions, owner rollover and runtime snapshot pinning.
-- Forward-only: preserve existing agent_skills rows and historical snapshots.

create or replace function public.guard_agent_skill_lifecycle()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_content_changed boolean;
begin
  if tg_op = 'INSERT' then
    if new.status is distinct from 'draft' or new.version is distinct from 1 then
      raise exception using errcode = '42501', message = 'agent_skill_must_start_as_draft_v1';
    end if;
    return new;
  end if;

  if new.id is distinct from old.id
     or new.agent_id is distinct from old.agent_id
     or new.created_by is distinct from old.created_by
     or new.created_at is distinct from old.created_at then
    raise exception using errcode = '42501', message = 'agent_skill_identity_immutable';
  end if;

  v_content_changed :=
    (to_jsonb(new) - 'status' - 'version' - 'updated_at')
    is distinct from
    (to_jsonb(old) - 'status' - 'version' - 'updated_at');

  if old.status = 'draft' then
    if new.status = 'draft' then
      return new;
    end if;
    if new.status in ('published', 'archived')
       and current_user = 'service_role'
       and not v_content_changed then
      return new;
    end if;
  elsif old.status = 'published' then
    if new.status = 'draft'
       and current_user = 'authenticated'
       and not v_content_changed then
      return new;
    end if;
    if new.status = 'archived'
       and current_user = 'service_role'
       and not v_content_changed then
      return new;
    end if;
  elsif old.status = 'archived' then
    if new.status = 'draft'
       and current_user = 'authenticated'
       and not v_content_changed then
      return new;
    end if;
  end if;

  raise exception using errcode = '42501', message = 'agent_skill_lifecycle_transition_forbidden';
end;
$$;

drop trigger if exists agent_skills_lifecycle_guard on public.agent_skills;
create trigger agent_skills_lifecycle_guard
before insert or update on public.agent_skills
for each row execute function public.guard_agent_skill_lifecycle();

-- Snapshot capture runs with the table owner so authenticated users cannot
-- forge, edit or delete immutable version records directly.
create or replace function public.capture_agent_skill_version()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.agent_skill_versions(skill_id, agent_id, version, created_by, snapshot)
  values (new.id, new.agent_id, new.version, new.created_by, to_jsonb(new));
  return new;
end;
$$;

revoke all on function public.guard_agent_skill_lifecycle() from public, anon, authenticated;
revoke all on function public.capture_agent_skill_version() from public, anon, authenticated;

-- Owner may edit drafts and read history, but cannot delete a published skill
-- or mutate its immutable version snapshots.
drop policy if exists agent_skills_owner_delete on public.agent_skills;
revoke delete, truncate, references, trigger on table public.agent_skills from public, anon, authenticated;
revoke insert, update, delete, truncate, references, trigger on table public.agent_skill_versions from public, anon, authenticated;
revoke insert (skill_id, agent_id, version, created_by, snapshot),
       update (skill_id, agent_id, version, created_by, snapshot)
on table public.agent_skill_versions from public, anon, authenticated;
grant select on table public.agent_skill_versions to authenticated;

-- Public Passport reads the latest published immutable snapshot, not the live
-- draft row. A draft rollover therefore never removes the previous publication.
create or replace view public.agent_skill_publications
with (security_barrier = true)
as
select distinct on (v.skill_id)
  v.skill_id as id,
  v.agent_id,
  v.snapshot ->> 'slug' as slug,
  v.snapshot ->> 'name' as name,
  v.snapshot ->> 'description' as description,
  v.snapshot ->> 'category' as category,
  (v.snapshot ->> 'version')::integer as version,
  v.snapshot ->> 'status' as status,
  v.snapshot -> 'publication_terms' as publication_terms,
  nullif(v.snapshot ->> 'created_at', '')::timestamptz as created_at,
  nullif(v.snapshot ->> 'updated_at', '')::timestamptz as updated_at
from public.agent_skill_versions v
join public.agent_skills s on s.id = v.skill_id and s.agent_id = v.agent_id
join public.ai_agents a on a.id = v.agent_id
where v.snapshot ->> 'status' = 'published'
  and s.status <> 'archived'
  and a.visibility = 'public'
  and a.status = 'active'
order by v.skill_id, (v.snapshot ->> 'version')::integer desc, v.created_at desc;

revoke all on public.agent_skill_publications from public, anon, authenticated;
grant select on public.agent_skill_publications to anon, authenticated;
comment on view public.agent_skill_publications is
  'Safe public projection of latest published immutable Agent Skill snapshots; excludes instructions, schemas, tools, permissions, budgets and owner data.';
