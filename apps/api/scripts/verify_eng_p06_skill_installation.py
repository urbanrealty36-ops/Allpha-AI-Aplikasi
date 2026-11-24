"""ENG-P06 PostgreSQL 17 verifier for licensed Skill installation, expiry and runtime revocation."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "apps/api/supabase/migrations"
MIGRATION_FILES = [
    MIGRATIONS / "20261122154257_eng_p06_skill_version_rollover_runtime_pinning.sql",
    MIGRATIONS / "20261124034103_eng_p06_skill_installation_licensing_runtime_gate.sql",
    MIGRATIONS / "20261124034604_eng_p06_skill_license_expiry_lifecycle.sql",
    MIGRATIONS / "20261124035118_eng_p06_install_idempotency_and_paid_entitlement_guard.sql",
]
NAME = "allpha-p06-install-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
SOURCE_AGENT = "22222222-2222-4222-8222-222222222222"
TARGET_AGENT = "66666666-6666-4666-8666-666666666666"
SOURCE_SKILL = "33333333-3333-4333-8333-333333333333"


def run(args: list[str], sql: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, input=sql, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout + "\n" + result.stderr)
    return result


def psql(sql: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = run(
        ["docker", "exec", "-i", NAME, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        sql,
        check=False,
    )
    if check and result.returncode:
        logs = run(["docker", "logs", NAME], check=False)
        raise RuntimeError(result.stdout + "\n" + result.stderr + "\nPostgreSQL container logs:\n" + logs.stdout + logs.stderr)
    return result


def main() -> None:
    run(["docker", "run", "-d", "--rm", "--name", NAME, "-e", "POSTGRES_PASSWORD=ci-only", "postgres:17-alpine"])
    try:
        ready = False
        for _ in range(60):
            probe = run(["docker", "exec", NAME, "pg_isready", "-U", "postgres", "-d", "postgres"], check=False)
            if probe.returncode == 0:
                ready = True
                break
            time.sleep(1)
        if not ready:
            raise RuntimeError("PostgreSQL 17 did not reach readiness")

        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create schema private;
create schema extensions;
create extension if not exists pgcrypto with schema extensions;
create function auth.uid() returns uuid language sql stable as $auth_uid$
 select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$auth_uid$;
create function auth.role() returns text language sql stable as $auth_role$
 select nullif(current_setting('request.jwt.claim.role',true),'')
$auth_role$;
grant usage on schema auth,private,extensions to public;
grant execute on function auth.uid(),auth.role() to public;

create table auth.users(id uuid primary key);
create table public.ai_agents(id uuid primary key,visibility text not null,status text not null);
create table public.agent_ownerships(
 agent_id uuid not null references public.ai_agents(id),
 owner_user_id uuid not null references auth.users(id),
 ownership_role text not null,status text not null
);
create function private.has_agent_ownership(p_agent_id uuid,p_user_id uuid,p_role text)
returns boolean language sql stable security definer set search_path=''
as $has_owner$
 select exists(select 1 from public.agent_ownerships o
  where o.agent_id=p_agent_id and o.owner_user_id=p_user_id
    and o.ownership_role=p_role and o.status='active')
$has_owner$;
grant execute on function private.has_agent_ownership(uuid,uuid,text) to public;

create table private.account_export_sources(
 source_key text primary key,table_name text not null,filter_kind text not null,
 owner_columns text[] not null,sort_order integer not null,enabled boolean not null default true
);
create table public.account_deletion_source_policies(
 source_key text primary key,data_class text not null,deletion_action text not null,
 dependency_order integer not null,policy_version integer not null,reason text not null,
 approved_by uuid,approved_at timestamptz,active boolean not null default true,
 table_name text not null,filter_kind text not null,owner_columns text[] not null,
 decision_source text not null,decision_reference text not null,updated_at timestamptz not null default now()
);
create table public.account_deletion_dependency_rules(
 child_schema text not null,child_table text not null,constraint_name text not null,
 fk_column text not null,delete_rule text not null,resolution_action text not null,
 reason text not null,active boolean not null default true,
 unique(child_schema,child_table,constraint_name)
);
insert into public.account_deletion_source_policies(
 source_key,data_class,deletion_action,dependency_order,policy_version,reason,active,
 table_name,filter_kind,owner_columns,decision_source,decision_reference
) values(
 'agent_ownerships','agent_operational','preserve',51,1,'CI-only canonical ownership source policy',true,
 'agent_ownerships','owner_columns',array['owner_user_id'],'product_owner_directive','CI fixture only'
);

create table public.agent_skills(
 id uuid primary key default gen_random_uuid(),agent_id uuid not null references public.ai_agents(id),
 created_by uuid not null references auth.users(id),slug text not null,name text not null,
 description text not null default '',category text not null default 'general',
 inputs_schema jsonb not null default '{"type":"object"}',outputs_schema jsonb not null default '{"type":"object"}',
 instructions text not null default '',constraints jsonb not null default '{}',
 tool_dependencies text[] not null default '{}',required_permission_scopes text[] not null default '{}',
 model_requirements jsonb not null default '{}',budget_limits jsonb not null default '{}',
 tests jsonb not null default '[]',evaluation_rubric jsonb not null default '{}',
 provenance jsonb not null default '{}',version integer not null default 1,changelog text not null default '',
 publication_terms jsonb not null default '{}',status text not null default 'draft',
 created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
create table public.agent_skill_versions(
 id uuid primary key default gen_random_uuid(),skill_id uuid not null references public.agent_skills(id),
 agent_id uuid not null references public.ai_agents(id),version integer not null,
 created_by uuid not null references auth.users(id),snapshot jsonb not null,
 created_at timestamptz not null default now(),unique(skill_id,version)
);
create function public.prepare_agent_skill_update() returns trigger language plpgsql set search_path=''
as $prepare$ begin new.version:=old.version+1; new.updated_at:=clock_timestamp(); return new; end $prepare$;
create function public.capture_agent_skill_version() returns trigger language plpgsql security definer set search_path=''
as $capture$ begin
 insert into public.agent_skill_versions(skill_id,agent_id,version,created_by,snapshot)
 values(new.id,new.agent_id,new.version,new.created_by,to_jsonb(new));
 return new;
end $capture$;
create trigger agent_skills_prepare_update before update on public.agent_skills
for each row execute function public.prepare_agent_skill_update();
create trigger agent_skills_capture_version after insert or update on public.agent_skills
for each row execute function public.capture_agent_skill_version();
alter table public.agent_skills enable row level security;
alter table public.agent_skill_versions enable row level security;
create policy agent_skills_owner_insert on public.agent_skills for insert to authenticated
 with check(created_by=auth.uid() and private.has_agent_ownership(agent_id,auth.uid(),'owner'));
create policy agent_skills_owner_update on public.agent_skills for update to authenticated
 using(private.has_agent_ownership(agent_id,auth.uid(),'owner'))
 with check(created_by=auth.uid() and private.has_agent_ownership(agent_id,auth.uid(),'owner'));
create policy agent_skills_owner_select on public.agent_skills for select to authenticated
 using(private.has_agent_ownership(agent_id,auth.uid(),'owner'));
create policy agent_skill_versions_owner_select on public.agent_skill_versions for select to authenticated
 using(private.has_agent_ownership(agent_id,auth.uid(),'owner'));
create policy agent_skill_versions_owner_insert on public.agent_skill_versions for insert to authenticated
 with check(created_by=auth.uid());

grant usage on schema public to anon,authenticated,service_role;
grant select on public.ai_agents to anon,authenticated,service_role;
grant select on public.agent_ownerships to authenticated,service_role;
grant select,insert,update,delete on public.agent_skills,public.agent_skill_versions to authenticated,service_role;
""")

        for migration in MIGRATION_FILES:
            if not migration.is_file():
                raise RuntimeError(f"Missing P06 migration: {migration}")
            psql(migration.read_text(encoding="utf-8"))

        psql(f"""
insert into auth.users(id) values ('{OWNER}');
insert into public.ai_agents(id,visibility,status) values
 ('{SOURCE_AGENT}','public','active'),
 ('{TARGET_AGENT}','public','active');
insert into public.agent_ownerships(agent_id,owner_user_id,ownership_role,status) values
 ('{SOURCE_AGENT}','{OWNER}','owner','active'),
 ('{TARGET_AGENT}','{OWNER}','owner','active');
""")

        # Build a real immutable published source snapshot at version 5.
        psql(f"""
set role authenticated;
select set_config('request.jwt.claim.sub','{OWNER}',false);
select set_config('request.jwt.claim.role','authenticated',false);
insert into public.agent_skills(id,agent_id,created_by,slug,name,description,category,publication_terms,status,version)
values('{SOURCE_SKILL}','{SOURCE_AGENT}','{OWNER}','licensed_source','Licensed Source Skill',
 'Public Skill with explicit license terms','research','{{"license":"owner"}}'::jsonb,'draft',1);
update public.agent_skills set description='Source v2' where id='{SOURCE_SKILL}';
update public.agent_skills set description='Source v3' where id='{SOURCE_SKILL}';
update public.agent_skills set description='Source v4' where id='{SOURCE_SKILL}';
reset role;
set role service_role;
update public.agent_skills set status='published' where id='{SOURCE_SKILL}';
reset role;
do $do$
begin
 if not exists(select 1 from public.agent_skill_versions where skill_id='{SOURCE_SKILL}' and version=5 and snapshot->>'status'='published') then
  raise exception 'source published version 5 snapshot missing';
 end if;
 if not exists(select 1 from public.agent_skill_publications where id='{SOURCE_SKILL}' and version=5) then
  raise exception 'source Skill is not discoverable in public catalog';
 end if;
end $do$;
""")

        # Explicit owner acceptance, idempotent replay, and immutable license evidence.
        psql(f"""
set role authenticated;
select set_config('request.jwt.claim.sub','{OWNER}',false);
select set_config('request.jwt.claim.role','authenticated',false);
select public.install_agent_skill('{TARGET_AGENT}','{SOURCE_AGENT}','{SOURCE_SKILL}',5,true,'p06-install-key-0001');
select public.install_agent_skill('{TARGET_AGENT}','{SOURCE_AGENT}','{SOURCE_SKILL}',5,true,'p06-install-key-0001');
reset role;
do $do$
begin
 if (select count(*) from public.agent_skill_installations where agent_id='{TARGET_AGENT}')<>1 then
  raise exception 'idempotent Skill install duplicated entitlement';
 end if;
 if not exists(select 1 from public.agent_skill_installations where agent_id='{TARGET_AGENT}' and source_version=5 and status='active' and license_terms_digest ~ '^[0-9a-f]{64}$') then
  raise exception 'license snapshot not persisted';
 end if;
 if not exists(select 1 from public.agent_skill_installation_events where event_type='installed') then
  raise exception 'installation event missing';
 end if;
 if not exists(select 1 from public.agent_skills where id=(select installed_skill_id from public.agent_skill_installations where agent_id='{TARGET_AGENT}') and status='draft' and version=1) then
  raise exception 'installed Skill must start as local draft v1';
 end if;
end $do$;
""")

        # Only an active, unexpired license is eligible for public Passport and Runtime.
        psql(f"""
set role service_role;
update public.agent_skills set status='published'
 where id=(select installed_skill_id from public.agent_skill_installations where agent_id='{TARGET_AGENT}');
reset role;
do $do$
begin
 if not exists(select 1 from public.agent_skill_publications where id=(select installed_skill_id from public.agent_skill_installations where agent_id='{TARGET_AGENT}')) then
  raise exception 'active licensed installation not visible in public Passport';
 end if;
end $do$;
""")

        # Owner revocation is immutable, removes public Passport visibility and disables Runtime.
        psql(f"""
set role authenticated;
select set_config('request.jwt.claim.sub','{OWNER}',false);
select set_config('request.jwt.claim.role','authenticated',false);
select public.revoke_agent_skill_installation(
 '{TARGET_AGENT}',
 (select id from public.agent_skill_installations where agent_id='{TARGET_AGENT}'),
 'Owner revoked the source license'
);
reset role;
do $do$
begin
 if not exists(select 1 from public.agent_skill_installations where agent_id='{TARGET_AGENT}' and status='revoked') then
  raise exception 'license revocation state not persisted';
 end if;
 if (select count(*) from public.agent_skill_installation_events where event_type in ('installed','revoked'))<>2 then
  raise exception 'install/revoke audit trail incomplete';
 end if;
 if exists(select 1 from public.agent_skill_publications where id=(select installed_skill_id from public.agent_skill_installations where agent_id='{TARGET_AGENT}')) then
  raise exception 'revoked installation still appears in public Passport';
 end if;
 if not exists(select 1 from private.account_export_sources where source_key='agent_skill_installations' and enabled) then
  raise exception 'installation missing from account export';
 end if;
 if not exists(select 1 from public.account_deletion_source_policies where source_key='agent_skill_installations' and active and deletion_action='preserve') then
  raise exception 'installation license audit not protected by P03';
 end if;
end $do$;
""")

        # Re-install after revocation, then materialize expiry as an auditable lifecycle event.
        psql(f"""
set role authenticated;
select set_config('request.jwt.claim.sub','{OWNER}',false);
select set_config('request.jwt.claim.role','authenticated',false);
select public.install_agent_skill('{TARGET_AGENT}','{SOURCE_AGENT}','{SOURCE_SKILL}',5,true,'p06-install-key-0002');
reset role;
update public.agent_skill_installations set license_expires_at=clock_timestamp()-interval '1 second'
 where agent_id='{TARGET_AGENT}' and status='active';
""")
        psql(f"""
set role authenticated;
select set_config('request.jwt.claim.sub','{OWNER}',false);
select set_config('request.jwt.claim.role','authenticated',false);
select public.expire_agent_skill_installations('{TARGET_AGENT}');
reset role;
do $do$
begin
 if not exists(select 1 from public.agent_skill_installations where agent_id='{TARGET_AGENT}' and status='expired' and revocation_reason='license_expired') then
  raise exception 'elapsed Skill license was not marked expired';
 end if;
 if (select count(*) from public.agent_skill_installation_events where event_type in ('installed','revoked','expired'))<>4 then
  raise exception 'install/revoke/expiry audit trail incomplete';
 end if;
 if exists(select 1 from public.agent_skill_publications where id=(select installed_skill_id from public.agent_skill_installations where agent_id='{TARGET_AGENT}' and status='expired')) then
  raise exception 'expired installation remains visible in public Passport';
 end if;
end $do$;
""")

        # Paid licenses cannot be installed without a Billing entitlement.
        psql(f"""
set role authenticated;
select set_config('request.jwt.claim.sub','{OWNER}',false);
select set_config('request.jwt.claim.role','authenticated',false);
update public.agent_skills set status='draft' where id='{SOURCE_SKILL}';
update public.agent_skills set publication_terms='{{"license":"owner","requires_purchase":true}}'::jsonb
 where id='{SOURCE_SKILL}';
reset role;
set role service_role;
update public.agent_skills set status='published' where id='{SOURCE_SKILL}';
reset role;
""")
        paid = psql(f"""
set role authenticated;
select set_config('request.jwt.claim.sub','{OWNER}',false);
select set_config('request.jwt.claim.role','authenticated',false);
select public.install_agent_skill('{TARGET_AGENT}','{SOURCE_AGENT}','{SOURCE_SKILL}',8,true,'p06-paid-license-denied');
""", check=False)
        if paid.returncode == 0 or "SKILL_LICENSE_ENTITLEMENT_REQUIRED" not in paid.stderr:
            raise RuntimeError("Paid Skill installation bypassed the Billing entitlement gate")

        denied = psql(f"""
set role authenticated;
select set_config('request.jwt.claim.sub','{OWNER}',false);
select set_config('request.jwt.claim.role','authenticated',false);
select public.install_agent_skill('{TARGET_AGENT}','{SOURCE_AGENT}','{SOURCE_SKILL}',8,false,'p06-license-not-accepted');
""", check=False)
        if denied.returncode == 0 or "SKILL_LICENSE_ACCEPTANCE_REQUIRED" not in denied.stderr:
            raise RuntimeError("Skill installation unexpectedly succeeded without explicit license acceptance")

        print("PASS: ENG-P06 PostgreSQL 17 Skill versioning, explicit license acceptance, idempotent installation, local draft clone, Passport publication, revocation, expiry, paid-entitlement gate and P03 export/retention.")
    finally:
        run(["docker", "rm", "--force", NAME], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: ENG-P06 Skill installation verification: {exc}", file=sys.stderr)
        raise SystemExit(1)
