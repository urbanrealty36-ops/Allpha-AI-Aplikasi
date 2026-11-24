"""ENG-P05 PostgreSQL 17 integration verifier for Agent identity, consent and ownership transfer."""
from __future__ import annotations

from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "apps/api/supabase/migrations"
MIGRATION_FILES = [
    MIGRATIONS / "20261124031340_eng_p05_agent_identity_versions_and_passport_attribution.sql",
    MIGRATIONS / "20261124032135_eng_p05_agent_ownership_transfer_and_consent_audit.sql",
    MIGRATIONS / "20261124032413_eng_p05_ownership_transfer_retention_and_export.sql",
]
CONTAINER = "allpha-p05-agent-identity-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
RECIPIENT = "22222222-2222-4222-8222-222222222222"
THIRD = "33333333-3333-4333-8333-333333333333"
AGENT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
AGENT_REJECT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
AGENT_CANCEL = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def run(args: list[str], sql: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, input=sql, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout + "\n" + result.stderr)
    return result


def psql(sql: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        sql,
        check=check,
    )


def as_user(user_id: str, sql: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return psql(
        "set role authenticated;\n"
        f"set request.jwt.claim.sub='{user_id}';\n"
        "set request.jwt.claim.role='authenticated';\n"
        + sql + "\nreset role;\n",
        check=check,
    )


def main() -> None:
    run(["docker", "run", "-d", "--rm", "--name", CONTAINER, "-e", "POSTGRES_PASSWORD=ci-only", "postgres:17-alpine"])
    try:
        ready = False
        for _ in range(60):
            probe = run(["docker", "exec", CONTAINER, "psql", "-X", "-A", "-t", "-U", "postgres", "-d", "postgres", "-c", "select 1"], check=False)
            if probe.returncode == 0:
                ready = True
                break
            time.sleep(1)
        if not ready:
            raise RuntimeError("PostgreSQL 17 did not reach SQL readiness")

        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create schema private;
create schema extensions;
create extension if not exists pgcrypto with schema extensions;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$$;
create function auth.role() returns text language sql stable as $$
  select nullif(current_setting('request.jwt.claim.role',true),'')
$$;
grant usage on schema auth,private,extensions to public;
grant execute on function auth.uid(),auth.role() to public;

create table public.profiles(
  id uuid primary key references auth.users(id) on delete cascade,
  username text,
  display_name text,
  avatar_url text,
  visibility text not null,
  account_status text not null
);
create table public.ai_agents(
  id uuid primary key default gen_random_uuid(),
  handle text not null unique,
  display_name text not null,
  description text not null default '',
  avatar_url text,
  persona jsonb not null default '{}'::jsonb,
  disclosure text not null default '',
  boundaries jsonb not null default '{}'::jsonb,
  visibility text not null default 'private',
  status text not null default 'draft',
  created_by uuid references auth.users(id),
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table public.agent_ownerships(
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  ownership_role text not null check(ownership_role in ('owner','operator','viewer')),
  status text not null check(status in ('active','revoked')),
  created_at timestamptz not null default now(),
  primary key(agent_id,owner_user_id)
);
create function private.has_agent_ownership(p_agent_id uuid,p_user_id uuid,p_role text)
returns boolean language sql stable security definer set search_path=''
as $$
 select exists(select 1 from public.agent_ownerships o
   where o.agent_id=p_agent_id and o.owner_user_id=p_user_id
     and o.ownership_role=p_role and o.status='active')
$$;
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
 'agents_created','agent_operational','preserve',52,1,'CI-only source policy fixture',true,
 'ai_agents','owned_agents',array['id'],'product_owner_directive','CI fixture only'
);

create table public.agent_consumer_grants(
 id uuid primary key default gen_random_uuid(),agent_id uuid not null,
 owner_user_id uuid not null,status text not null,revoked_by uuid,revoked_at timestamptz,
 revoke_reason text,updated_at timestamptz not null default now()
);
create table public.agent_resource_grants(
 id uuid primary key default gen_random_uuid(),agent_id uuid not null,
 status text not null,revoked_by uuid,revoked_at timestamptz,
 revocation_reason text,updated_at timestamptz not null default now()
);
create table public.agent_runtime_policies(
 id uuid primary key default gen_random_uuid(),agent_id uuid not null,
 status text not null,revoked_by uuid,revoked_at timestamptz
);
create table public.agent_social_presence_policies(
 id uuid primary key default gen_random_uuid(),agent_id uuid not null,
 owner_user_id uuid not null,is_enabled boolean not null,
 revoked_at timestamptz,updated_at timestamptz not null default now()
);
create table public.official_agent_bots(
 id uuid primary key default gen_random_uuid(),agent_id uuid,status text not null
);

create function private.bump_agent_version()
returns trigger language plpgsql set search_path=''
as $$ begin new.version:=old.version+1; new.updated_at:=clock_timestamp(); return new; end $$;
create trigger ai_agents_bump_version before update on public.ai_agents
for each row execute function private.bump_agent_version();

grant usage on schema public to authenticated,anon,service_role;
grant select,update on public.ai_agents to authenticated;
grant select on public.agent_ownerships,public.profiles to authenticated,anon;
""")

        for migration in MIGRATION_FILES:
            if not migration.is_file():
                raise RuntimeError(f"Missing migration file: {migration}")
            psql(migration.read_text(encoding="utf-8"))

        psql(f"""
insert into auth.users(id) values ('{OWNER}'),('{RECIPIENT}'),('{THIRD}');
insert into public.profiles(id,username,display_name,avatar_url,visibility,account_status) values
 ('{OWNER}','owner-one','Owner One','https://cdn.invalid/owner.png','public','active'),
 ('{RECIPIENT}','owner-two','Owner Two','https://cdn.invalid/two.png','public','active'),
 ('{THIRD}','owner-three','Owner Three','https://cdn.invalid/three.png','public','active');
insert into public.ai_agents(id,handle,display_name,description,disclosure,created_by,version)
values
 ('{AGENT}','transfer_agent','Transfer Agent','Original identity','AI Agent; responses may be generated by a model.','{OWNER}',1),
 ('{AGENT_REJECT}','reject_agent','Reject Agent','Reject path','AI Agent; responses may be generated by a model.','{OWNER}',1),
 ('{AGENT_CANCEL}','cancel_agent','Cancel Agent','Cancel path','AI Agent; responses may be generated by a model.','{OWNER}',1);
insert into public.agent_ownerships(agent_id,owner_user_id,ownership_role,status) values
 ('{AGENT}','{OWNER}','owner','active'),
 ('{AGENT_REJECT}','{OWNER}','owner','active'),
 ('{AGENT_CANCEL}','{OWNER}','owner','active');
""")

        # Owner edits persona and identity using optimistic version and explicit owner identity.
        as_user(OWNER, f"""
select * from public.update_my_ai_agent('{AGENT}',1,'{{"display_name":"Updated Agent","persona":{{"tone":"calm"}}}}'::jsonb);
do $$
begin
 if not exists(select 1 from public.agent_identity_versions where agent_id='{AGENT}' and version=2 and event_type='updated') then
   raise exception 'owner identity update did not create immutable version 2';
 end if;
 if exists(select 1 from public.update_my_ai_agent('{AGENT}',1,'{{"display_name":"stale"}}'::jsonb)) then
   raise exception 'stale Agent version unexpectedly updated';
 end if;
end $$;
select * from public.publish_my_ai_agent('{AGENT}',2,true);
do $$
begin
 if not exists(select 1 from public.agent_identity_versions where agent_id='{AGENT}' and version=3 and event_type='published') then
   raise exception 'publication did not create immutable identity version';
 end if;
 if not exists(select 1 from public.agent_owner_attribution_consent_events where agent_id='{AGENT}' and owner_user_id='{OWNER}' and event_type='granted') then
   raise exception 'owner attribution grant was not audited';
 end if;
 if not exists(select 1 from public.get_public_agent_owner_attribution('{AGENT}') where username='owner-one') then
   raise exception 'consented public Human Owner attribution not returned';
 end if;
end $$;
""")

        # Idempotent request, active recipient and two-party acceptance.
        request = as_user(OWNER, f"""
select public.request_agent_ownership_transfer('{AGENT}','{RECIPIENT}','p05-transfer-key-0001');
select public.request_agent_ownership_transfer('{AGENT}','{RECIPIENT}','p05-transfer-key-0001');
do $$
begin
 if (select count(*) from public.agent_ownership_transfer_requests where agent_id='{AGENT}' and status='pending')<>1 then
   raise exception 'idempotent request created duplicate transfer';
 end if;
end $$;
""")
        if request.returncode:
            raise RuntimeError(request.stderr)

        psql(f"""
insert into public.agent_consumer_grants(agent_id,owner_user_id,status)
values ('{AGENT}','{OWNER}','active');
insert into public.agent_resource_grants(agent_id,status) values ('{AGENT}','active');
insert into public.agent_runtime_policies(agent_id,status) values ('{AGENT}','approved');
insert into public.agent_social_presence_policies(agent_id,owner_user_id,is_enabled)
values ('{AGENT}','{OWNER}',true);
""")

        as_user(RECIPIENT, f"""
select public.respond_agent_ownership_transfer(
 (select id from public.agent_ownership_transfer_requests where agent_id='{AGENT}' and status='pending'),true
);
do $$
begin
 if not private.has_agent_ownership('{AGENT}','{RECIPIENT}','owner') then raise exception 'recipient did not become Agent owner'; end if;
 if private.has_agent_ownership('{AGENT}','{OWNER}','owner') then raise exception 'previous owner retained active ownership'; end if;
 if not exists(select 1 from public.ai_agents where id='{AGENT}' and status='draft' and visibility='private' and public_owner_attribution=false) then
   raise exception 'ownership transfer did not reset public identity';
 end if;
 if exists(select 1 from public.agent_consumer_grants where agent_id='{AGENT}' and status='active') then raise exception 'consumer grant survived ownership transfer'; end if;
 if exists(select 1 from public.agent_resource_grants where agent_id='{AGENT}' and status='active') then raise exception 'resource grant survived ownership transfer'; end if;
 if exists(select 1 from public.agent_runtime_policies where agent_id='{AGENT}' and status='approved') then raise exception 'runtime policy survived ownership transfer'; end if;
 if exists(select 1 from public.agent_social_presence_policies where agent_id='{AGENT}' and is_enabled) then raise exception 'social presence policy survived ownership transfer'; end if;
 if not exists(select 1 from public.agent_owner_attribution_consent_events where agent_id='{AGENT}' and owner_user_id='{OWNER}' and event_type='revoked') then
   raise exception 'previous Human Owner attribution consent was not revoked';
 end if;
 if not exists(select 1 from public.agent_ownership_transfer_events where agent_id='{AGENT}' and event_type='accepted') then
   raise exception 'ownership acceptance event missing';
 end if;
 if exists(select 1 from public.get_public_agent_owner_attribution('{AGENT}')) then
   raise exception 'old owner attribution still public after transfer';
 end if;
 if exists(select 1 from public.update_my_ai_agent('{AGENT}',4,'{{"display_name":"old owner takeover"}}'::jsonb)) then
   raise exception 'previous owner can still update transferred Agent';
 end if;
end $$;
select * from public.update_my_ai_agent('{AGENT}',(select version from public.ai_agents where id='{AGENT}'),'{{"display_name":"Recipient Managed Agent"}}'::jsonb);
""")

        # Rejection does not transfer ownership.
        as_user(OWNER, f"select public.request_agent_ownership_transfer('{AGENT_REJECT}','{RECIPIENT}','p05-reject-key-0001');")
        as_user(RECIPIENT, f"""
select public.respond_agent_ownership_transfer(
 (select id from public.agent_ownership_transfer_requests where agent_id='{AGENT_REJECT}' and status='pending'),false
);
do $$
begin
 if not private.has_agent_ownership('{AGENT_REJECT}','{OWNER}','owner') then raise exception 'rejection changed existing ownership'; end if;
 if exists(select 1 from public.agent_ownerships where agent_id='{AGENT_REJECT}' and owner_user_id='{RECIPIENT}' and status='active') then
   raise exception 'rejected recipient gained ownership';
 end if;
end $$;
""")

        # Owner cancellation and recipient expiry; the expired pending slot is reclaimed on next request.
        as_user(OWNER, f"""
select public.request_agent_ownership_transfer('{AGENT_CANCEL}','{RECIPIENT}','p05-cancel-key-0001');
select public.cancel_agent_ownership_transfer((select id from public.agent_ownership_transfer_requests where agent_id='{AGENT_CANCEL}' and status='pending'));
do $$
begin
 if not exists(select 1 from public.agent_ownership_transfer_requests where agent_id='{AGENT_CANCEL}' and status='cancelled') then
   raise exception 'owner cancellation was not persisted';
 end if;
end $$;
""")
        as_user(OWNER, f"select public.request_agent_ownership_transfer('{AGENT_CANCEL}','{RECIPIENT}','p05-expire-key-0002');")
        psql(f"update public.agent_ownership_transfer_requests set expires_at=clock_timestamp()-interval '1 second' where agent_id='{AGENT_CANCEL}' and status='pending';")
        as_user(RECIPIENT, f"""
select public.respond_agent_ownership_transfer(
 (select id from public.agent_ownership_transfer_requests where agent_id='{AGENT_CANCEL}' and status='pending'),true
);
do $$
begin
 if not exists(select 1 from public.agent_ownership_transfer_requests where agent_id='{AGENT_CANCEL}' and status='expired') then
   raise exception 'expired transfer was not closed';
 end if;
 if not private.has_agent_ownership('{AGENT_CANCEL}','{OWNER}','owner') then
   raise exception 'expired transfer changed ownership';
 end if;
end $$;
""")
        as_user(OWNER, f"""
select public.request_agent_ownership_transfer('{AGENT_CANCEL}','{THIRD}','p05-expire-key-0003');
do $$
begin
 if (select count(*) from public.agent_ownership_transfer_requests where agent_id='{AGENT_CANCEL}' and status='pending')<>1 then
   raise exception 'expired pending slot was not reclaimed';
 end if;
end $$;
""")

        psql("""
do $$
begin
 if not exists(select 1 from private.account_export_sources where source_key='agent_ownership_transfer_requests' and enabled) then raise exception 'transfer requests missing from account export'; end if;
 if not exists(select 1 from private.account_export_sources where source_key='agent_ownership_transfer_events' and enabled) then raise exception 'transfer events missing from account export'; end if;
 if not exists(select 1 from private.account_export_sources where source_key='agent_owner_attribution_consent_events' and enabled) then raise exception 'consent events missing from account export'; end if;
 if (select count(*) from public.account_deletion_source_policies where source_key in ('agent_ownership_transfer_requests','agent_ownership_transfer_events','agent_owner_attribution_consent_events') and active and deletion_action='preserve')<>3 then
   raise exception 'P05 audit retention policy missing';
 end if;
 if not has_function_privilege('authenticated','public.request_agent_ownership_transfer(uuid,uuid,text)','EXECUTE') then raise exception 'authenticated transfer request RPC not granted'; end if;
 if has_table_privilege('authenticated','public.agent_ownership_transfer_requests','INSERT') then raise exception 'authenticated can bypass ownership transfer RPC'; end if;
end $$;
""")
        print("PASS: ENG-P05 PostgreSQL 17 identity versioning, consent, publication, two-party transfer, revocation, rejection, cancellation, expiry, idempotency and P03 export/retention integration.")
    finally:
        run(["docker", "rm", "-f", CONTAINER], check=False)


if __name__ == "__main__":
    main()
