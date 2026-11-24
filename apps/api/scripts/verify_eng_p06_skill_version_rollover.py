"""ENG-P06 disposable PostgreSQL 17 verification for skill rollover and runtime snapshots."""
from __future__ import annotations
from pathlib import Path
import subprocess, sys, time, uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps/api/supabase/migrations/20261122154257_eng_p06_skill_version_rollover_runtime_pinning.sql"
NAME = "allpha-p06-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
AGENT = "22222222-2222-4222-8222-222222222222"
SKILL = "33333333-3333-4333-8333-333333333333"

def run(args, sql=None, check=True):
    result = subprocess.run(args, input=sql, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout + "\\n" + result.stderr)
    return result

def psql(statement, check=True):
    return run(["docker","exec","-i",NAME,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres"], statement, check)

def main():
    run(["docker","run","-d","--rm","--name",NAME,"-e","POSTGRES_PASSWORD=ci-only","postgres:17-alpine"])
    try:
        time.sleep(1)
        ready = False
        ready_streak = 0
        for _ in range(90):
            probe = run(["docker","exec",NAME,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False)
            if probe.returncode == 0:
                ready_streak += 1
                if ready_streak >= 3:
                    ready = True
                    break
            else:
                ready_streak = 0
            time.sleep(1)
        if not ready: raise RuntimeError("PostgreSQL 17 did not reach stable SQL readiness")
        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create extension if not exists pgcrypto;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
grant usage on schema auth to public;
grant execute on function auth.uid() to public;
create table public.ai_agents(id uuid primary key,visibility text not null,status text not null);
create table public.agent_ownerships(agent_id uuid,owner_user_id uuid,ownership_role text,status text);
grant select on public.agent_ownerships to authenticated, service_role;
create table public.agent_skills(
 id uuid primary key default gen_random_uuid(),agent_id uuid not null,created_by uuid not null,
 slug text not null,name text not null,description text not null default '',category text not null default 'general',
 inputs_schema jsonb not null default '{"type":"object"}',outputs_schema jsonb not null default '{"type":"object"}',
 instructions text not null default '',constraints jsonb not null default '{}',tool_dependencies jsonb not null default '[]',
 required_permission_scopes jsonb not null default '[]',model_requirements jsonb not null default '{}',
 budget_limits jsonb not null default '{}',tests jsonb not null default '[]',evaluation_rubric jsonb not null default '{}',
 provenance jsonb not null default '{}',version integer not null default 1,changelog text not null default '',
 publication_terms jsonb not null default '{}',status text not null default 'draft',
 created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create table public.agent_skill_versions(
 id uuid primary key default gen_random_uuid(),skill_id uuid not null,agent_id uuid not null,
 version integer not null,created_by uuid not null,snapshot jsonb not null,created_at timestamptz not null default now(),
 unique(skill_id,version));
alter table public.agent_skills enable row level security;
alter table public.agent_skill_versions enable row level security;
create policy agent_skills_owner_insert on public.agent_skills for insert to authenticated
 with check(created_by=auth.uid() and exists(select 1 from public.agent_ownerships o where o.agent_id=agent_skills.agent_id and o.owner_user_id=auth.uid() and o.ownership_role='owner' and o.status='active'));
create policy agent_skills_owner_update on public.agent_skills for update to authenticated
 using(exists(select 1 from public.agent_ownerships o where o.agent_id=agent_skills.agent_id and o.owner_user_id=auth.uid() and o.ownership_role='owner' and o.status='active'))
 with check(created_by=auth.uid() and exists(select 1 from public.agent_ownerships o where o.agent_id=agent_skills.agent_id and o.owner_user_id=auth.uid() and o.ownership_role='owner' and o.status='active'));
create policy agent_skills_owner_select on public.agent_skills for select to authenticated
 using(exists(select 1 from public.agent_ownerships o where o.agent_id=agent_skills.agent_id and o.owner_user_id=auth.uid() and o.ownership_role='owner' and o.status='active'));
create policy agent_skills_owner_delete on public.agent_skills for delete to authenticated
 using(exists(select 1 from public.agent_ownerships o where o.agent_id=agent_skills.agent_id and o.owner_user_id=auth.uid() and o.ownership_role='owner' and o.status='active'));
create policy agent_skill_versions_owner_select on public.agent_skill_versions for select to authenticated
 using(exists(select 1 from public.agent_ownerships o where o.agent_id=agent_skill_versions.agent_id and o.owner_user_id=auth.uid() and o.ownership_role='owner' and o.status='active'));
create policy agent_skill_versions_owner_insert on public.agent_skill_versions for insert to authenticated
 with check(created_by=auth.uid());
create function public.prepare_agent_skill_update() returns trigger language plpgsql set search_path='' as $$
begin new.version:=old.version+1; new.updated_at:=now(); return new; end $$;
create function public.capture_agent_skill_version() returns trigger language plpgsql set search_path='' as $$
begin insert into public.agent_skill_versions(skill_id,agent_id,version,created_by,snapshot) values(new.id,new.agent_id,new.version,new.created_by,to_jsonb(new)); return new; end $$;
create trigger agent_skills_prepare_update before update on public.agent_skills for each row execute function public.prepare_agent_skill_update();
create trigger agent_skills_capture_version after insert or update on public.agent_skills for each row execute function public.capture_agent_skill_version();
grant select,insert,update,delete on public.agent_skills to authenticated;
grant select,insert,update,delete on public.agent_skill_versions to authenticated;
grant select on public.ai_agents to anon,authenticated;
grant select,insert,update,delete on public.agent_skills to service_role;
grant select,insert,update,delete on public.agent_skill_versions to service_role;
""")
        psql(MIGRATION.read_text(encoding="utf-8"))
        psql("""
insert into auth.users(id) values ('11111111-1111-4111-8111-111111111111');
insert into public.ai_agents(id,visibility,status) values
 ('22222222-2222-4222-8222-222222222222','public','active'),
 ('44444444-4444-4444-8444-444444444444','private','active');
insert into public.agent_ownerships values
 ('22222222-2222-4222-8222-222222222222','11111111-1111-4111-8111-111111111111','owner','active'),
 ('44444444-4444-4444-8444-444444444444','11111111-1111-4111-8111-111111111111','owner','active');
""")
        # Owner can create only draft v1. The snapshot trigger writes as its definer.
        psql("""
set role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
insert into public.agent_skills(id,agent_id,created_by,slug,name,tests,evaluation_rubric,publication_terms,status,version)
values('33333333-3333-4333-8333-333333333333','22222222-2222-4222-8222-222222222222','11111111-1111-4111-8111-111111111111','safe_skill','Safe Skill','[{"case":"basic"}]','{"quality":1}','{"license":"owner"}','draft',1);
reset role;
""")
        # Owner cannot self-publish or delete a skill.
        denied = psql("""
set role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
update public.agent_skills set status='published' where id='33333333-3333-4333-8333-333333333333';
""",check=False)
        if denied.returncode == 0: raise RuntimeError("authenticated owner unexpectedly self-published a draft")
        denied = psql("""
set role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
delete from public.agent_skills where id='33333333-3333-4333-8333-333333333333';
""",check=False)
        if denied.returncode == 0: raise RuntimeError("authenticated owner unexpectedly deleted a Skill")
        # Operator publishes v2. Owner cannot edit published content, then rolls
        # to draft v3 while the old publication remains visible; operator publishes v5.
        psql("""
set role service_role;
update public.agent_skills set status='published' where id='33333333-3333-4333-8333-333333333333';
reset role;
""")
        denied = psql("""
set role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
update public.agent_skills set name='unauthorized overwrite' where id='33333333-3333-4333-8333-333333333333';
""",check=False)
        if denied.returncode == 0: raise RuntimeError("authenticated owner unexpectedly edited a published Skill")
        psql("""
set role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
update public.agent_skills set status='draft' where id='33333333-3333-4333-8333-333333333333';
reset role;
do $$ begin
 if (select version from public.agent_skill_publications where id='33333333-3333-4333-8333-333333333333')<>2 then raise exception 'published Passport snapshot disappeared during draft rollover'; end if;
end $$;
set role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
update public.agent_skills set name='Safe Skill v2',changelog='rollover draft' where id='33333333-3333-4333-8333-333333333333';
insert into public.agent_skills(id,agent_id,created_by,slug,name,status,version)
values('55555555-5555-4555-8555-555555555555','44444444-4444-4444-8444-444444444444','11111111-1111-4111-8111-111111111111','private_skill','Private Skill','draft',1);
reset role;
set role service_role;
update public.agent_skills set status='published' where id='33333333-3333-4333-8333-333333333333';
update public.agent_skills set status='published' where id='55555555-5555-4555-8555-555555555555';
reset role;
""")
        psql("""
do $$
declare v integer; n text; old_name text;
begin
 select version,name into v,n from public.agent_skill_publications where id='33333333-3333-4333-8333-333333333333';
 if v<>5 or n<>'Safe Skill v2' then raise exception 'Passport did not resolve latest published snapshot: %, %',v,n; end if;
 select snapshot->>'name' into old_name from public.agent_skill_versions where skill_id='33333333-3333-4333-8333-333333333333' and version=2;
 if old_name<>'Safe Skill' then raise exception 'Historical published snapshot was mutated'; end if;
 if has_table_privilege('authenticated','public.agent_skills','DELETE') then raise exception 'owner delete privilege remains'; end if;
 if has_table_privilege('authenticated','public.agent_skill_versions','INSERT') or has_table_privilege('authenticated','public.agent_skill_versions','UPDATE') or has_table_privilege('authenticated','public.agent_skill_versions','DELETE') then raise exception 'authenticated can mutate immutable snapshots'; end if;
 if has_table_privilege('anon','public.agent_skill_publications','SELECT') is false then raise exception 'public Passport view is not readable'; end if;
 if exists(select 1 from information_schema.columns where table_schema='public' and table_name='agent_skill_publications' and column_name in ('instructions','inputs_schema','outputs_schema','tool_dependencies','required_permission_scopes','budget_limits')) then raise exception 'public view leaks private Skill fields'; end if;
 if (select count(*) from public.agent_skill_publications where agent_id='44444444-4444-4444-8444-444444444444')<>0 then raise exception 'private Agent Skill leaked to public view'; end if;
end $$;
""")
        print("PASS: ENG-P06 owner draft rollover, immutable publication snapshots, server-only publication, public Passport snapshot view, delete/DML restrictions and historical version retention.")
    finally:
        run(["docker","rm","--force",NAME],check=False)

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"FAIL: ENG-P06 PostgreSQL 17 verification: {exc}",file=sys.stderr)
        raise SystemExit(1)
