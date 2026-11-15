-- ENG-P05 schema reconciliation: pin Agent identity revisions for grants and execution snapshots.
-- The connected database already has this column and trigger, but the repository migration
-- history did not contain their canonical forward-only definition.
alter table public.ai_agents
  add column if not exists version integer not null default 1
    check (version > 0);

create or replace function public.bump_ai_agent_version()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.version := old.version + 1;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists ai_agents_bump_version on public.ai_agents;
create trigger ai_agents_bump_version
before update on public.ai_agents
for each row execute function public.bump_ai_agent_version();

revoke all on function public.bump_ai_agent_version() from public, anon, authenticated;

comment on column public.ai_agents.version is
  'Monotonic Agent identity revision pinned by Consumer grants, generation jobs and execution snapshots.';
