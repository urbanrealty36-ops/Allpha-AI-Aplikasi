"""ENG-P08 PostgreSQL 17 verifier for owner-private Memory lifecycle and retrieval isolation."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[3]
MIGRATION=ROOT/"apps/api/supabase/migrations/20261124060000_eng_p08_memory_coordinator_lifecycle.sql"
NAME="allpha-p08-memory-"+uuid.uuid4().hex[:8]
OWNER="11111111-1111-4111-8111-111111111111"
OTHER="99999999-9999-4999-8999-999999999999"
AGENT="22222222-2222-4222-8222-222222222222"
CONTENT="The owner prefers concise summaries."


def run(args:list[str],sql:str|None=None,check:bool=True)->subprocess.CompletedProcess[str]:
 result=subprocess.run(args,input=sql,text=True,capture_output=True)
 if check and result.returncode:raise RuntimeError(result.stdout+"\n"+result.stderr)
 return result


def psql(sql:str,check:bool=True)->subprocess.CompletedProcess[str]:
 result=run(["docker","exec","-i",NAME,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres"],sql,check=False)
 if check and result.returncode:
  logs=run(["docker","logs",NAME],check=False)
  raise RuntimeError(result.stdout+"\n"+result.stderr+"\nPostgreSQL logs:\n"+logs.stdout+logs.stderr)
 return result


def main()->None:
 if not MIGRATION.is_file():raise RuntimeError(f"Missing P08 migration: {MIGRATION}")
 run(["docker","run","-d","--rm","--name",NAME,"-e","POSTGRES_PASSWORD=ci-only","postgres:17-alpine"])
 try:
  ready=False;streak=0
  for _ in range(90):
   probe=run(["docker","exec",NAME,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False)
   if probe.returncode==0:
    streak+=1
    if streak>=3:ready=True;break
   else:streak=0
   time.sleep(1)
  if not ready:raise RuntimeError("PostgreSQL 17 did not reach stable SQL readiness")
  psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create schema private;
create schema extensions;
create extension if not exists pgcrypto with schema extensions;
create function auth.uid() returns uuid language sql stable as $uid$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $uid$;
create table auth.users(id uuid primary key);
create table public.ai_agents(id uuid primary key);
create table public.agent_ownerships(
 agent_id uuid not null references public.ai_agents(id),
 owner_user_id uuid not null references auth.users(id) on delete cascade,
 ownership_role text not null,status text not null,
 primary key(agent_id,owner_user_id,ownership_role)
);
create table private.account_export_sources(
 source_key text primary key,table_name text not null,filter_kind text not null,
 owner_columns text[] not null,sort_order integer not null,enabled boolean not null default true
);
create table public.account_deletion_source_policies(
 source_key text primary key,data_class text,deletion_action text,dependency_order integer not null,
 policy_version text,reason text,approved_by uuid,approved_at timestamptz,active boolean not null,
 updated_at timestamptz not null,table_name text not null,filter_kind text not null,
 owner_columns text[] not null,decision_source text not null,decision_reference text
);
grant usage on schema public,private,extensions to anon,authenticated,service_role;
""")
  psql(MIGRATION.read_text(encoding="utf-8"))
  psql(f"""
insert into auth.users(id) values('{OWNER}'),('{OTHER}');
insert into public.ai_agents(id) values('{AGENT}');
insert into public.agent_ownerships(agent_id,owner_user_id,ownership_role,status)
 values('{AGENT}','{OWNER}','owner','active');
set role service_role;
select public.agent_memory_transition('set_policy','{OWNER}','{AGENT}',null,
 jsonb_build_object('memory_type','long_term','enabled',true,'consent_version','allpha.memory.v1',
  'allowed_purposes',jsonb_build_array('agent_generation_context','agent_runtime_context'),
  'allowed_sensitivities',jsonb_build_array('public','internal'),'retention_days',30));
select public.agent_memory_transition('set_policy','{OWNER}','{AGENT}',null,
 jsonb_build_object('memory_type','long_term','enabled',true,'consent_version','allpha.memory.v1',
  'allowed_purposes',jsonb_build_array('agent_generation_context','agent_runtime_context'),
  'allowed_sensitivities',jsonb_build_array('public','internal'),'retention_days',30));
select public.agent_memory_transition('set_policy','{OWNER}','{AGENT}',null,
 jsonb_build_object('memory_type','long_term','enabled',true,'consent_version','allpha.memory.v1',
  'allowed_purposes',jsonb_build_array('agent_generation_context','agent_runtime_context'),
  'allowed_sensitivities',jsonb_build_array('public','internal'),'retention_days',31));
select public.agent_memory_transition('create_proposal','{OWNER}','{AGENT}',null,
 jsonb_build_object('memory_type','long_term','purpose','agent_generation_context','classification','internal',
  'content','{CONTENT}','content_sha256',encode(extensions.digest('{CONTENT}','sha256'),'hex'),
  'source_ref',jsonb_build_object('message_id','test-message-1'),
  'provenance',jsonb_build_object('capture_mode','owner_manual'),'confidence',0.95,
  'retention_expires_at',(clock_timestamp()+interval '30 days')::text));
reset role;
""")
  psql(f"""
do $do$
declare v_item uuid; v_policy uuid;
begin
 select id,policy_id into v_item,v_policy from public.agent_memory_items where owner_user_id='{OWNER}' and agent_id='{AGENT}' limit 1;
 if v_item is null or v_policy is null then raise exception 'Memory proposal was not persisted'; end if;
 if not exists(select 1 from public.agent_memory_policies where id=v_policy and policy_version=2 and retention_days=31) then
  raise exception 'unchanged Memory policy caused version churn or changed retention was not versioned';
 end if;
 if (select status from public.agent_memory_items where id=v_item)<>'pending' then raise exception 'new Memory must require owner approval'; end if;
 if not exists(select 1 from private.account_export_sources where source_key='agent_memory_items' and enabled) then raise exception 'Memory items missing from P03 export registry'; end if;
 if not exists(select 1 from public.account_deletion_source_policies where source_key='agent_memory_events' and active and deletion_action='preserve') then raise exception 'Memory event audit not preserved by P03'; end if;
end $do$;
set role service_role;
select public.agent_memory_transition('decide','{OWNER}','{AGENT}',
 (select id from public.agent_memory_items where owner_user_id='{OWNER}' and agent_id='{AGENT}' limit 1),
 jsonb_build_object('decision','approve'));
reset role;
do $do$
declare v_count integer;
begin
 select count(*) into v_count from public.agent_memory_search(
  '{OWNER}','{AGENT}',array(select id from public.agent_memory_policies where owner_user_id='{OWNER}' and agent_id='{AGENT}'),
  'agent_generation_context',array['public','internal'], 'concise summaries','internal',10
 );
 if v_count<>1 then raise exception 'approved Memory was not retrievable inside owner Agent scope'; end if;
end $do$;
""")
  psql(f"""
set role service_role;
select public.agent_memory_transition('correct','{OWNER}','{AGENT}',
 (select id from public.agent_memory_items where owner_user_id='{OWNER}' and agent_id='{AGENT}' limit 1),
 jsonb_build_object('content','The owner prefers concise and structured summaries.'));
reset role;
do $do$
begin
 if not exists(select 1 from public.agent_memory_items where owner_user_id='{OWNER}' and content='The owner prefers concise and structured summaries.' and version=2) then
  raise exception 'Memory correction did not version content';
 end if;
end $do$;
""")
  denied=psql(f"""
set role service_role;
select public.agent_memory_search(
 '{OTHER}','{AGENT}',array(select id from public.agent_memory_policies where owner_user_id='{OWNER}' and agent_id='{AGENT}'),
 'agent_generation_context',array['public','internal'],'concise','internal',10
);
""",check=False)
  if denied.returncode==0 or "AGENT_OWNER_REQUIRED" not in denied.stderr:
   raise RuntimeError("Memory retrieval accepted a non-owner or leaked an empty result instead of denying")
  psql(f"""
set role service_role;
select public.agent_memory_transition('delete','{OWNER}','{AGENT}',
 (select id from public.agent_memory_items where owner_user_id='{OWNER}' and agent_id='{AGENT}' limit 1),'{{}}'::jsonb);
select public.agent_memory_transition('create_proposal','{OWNER}','{AGENT}',null,
 jsonb_build_object('memory_type','long_term','purpose','agent_generation_context','classification','internal',
  'content','Temporary retained context','content_sha256',encode(extensions.digest('Temporary retained context','sha256'),'hex'),
  'source_ref',jsonb_build_object('kind','expiry-test'),'provenance',jsonb_build_object('capture_mode','test'),
  'confidence',0.8,'retention_expires_at',(clock_timestamp()+interval '30 days')::text));
reset role;
update public.agent_memory_items set retention_expires_at=clock_timestamp()-interval '1 second'
 where owner_user_id='{OWNER}' and source_ref->>'kind'='expiry-test';
set role service_role;
select public.agent_memory_transition('expire','{OWNER}','{AGENT}',null,'{{}}'::jsonb);
reset role;
do $do$
begin
 if exists(select 1 from public.agent_memory_items where owner_user_id='{OWNER}' and source_ref->>'kind'='expiry-test' and status in ('pending','active')) then
  raise exception 'expired Memory remained active';
 end if;
 if not exists(select 1 from public.agent_memory_events where event_type='item_deleted' and owner_user_id='{OWNER}') then
  raise exception 'Memory deletion audit missing';
 end if;
 if not exists(select 1 from public.agent_memory_events where event_type='item_expired' and owner_user_id='{OWNER}') then
  raise exception 'Memory retention expiry audit missing';
 end if;
 if has_function_privilege('authenticated','public.agent_memory_transition(text,uuid,uuid,uuid,jsonb)','EXECUTE')
    or has_function_privilege('authenticated','public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer)','EXECUTE') then
  raise exception 'authenticated can execute privileged Memory RPCs';
 end if;
 if has_table_privilege('authenticated','public.agent_memory_items','SELECT')
    or not has_table_privilege('service_role','public.agent_memory_items','SELECT')
    or has_table_privilege('service_role','public.agent_memory_items','INSERT')
    or has_table_privilege('service_role','public.agent_memory_items','UPDATE')
    or has_table_privilege('service_role','public.agent_memory_items','DELETE') then
  raise exception 'Memory table access grants are not read-only for the service role';
 end if;
end $do$;
delete from auth.users where id='{OWNER}';
do $do$
begin
 if not exists(select 1 from public.agent_memory_events where owner_user_id is null and owner_subject_hash=encode(extensions.digest('{OWNER}','sha256'),'hex')) then
  raise exception 'P03 account deletion did not preserve pseudonymous Memory audit';
 end if;
 if exists(select 1 from public.agent_memory_items where owner_user_id='{OWNER}')
    or exists(select 1 from public.agent_memory_policies where owner_user_id='{OWNER}') then
  raise exception 'P03 account deletion retained owner-private Memory content or policy';
 end if;
end $do$;
""")
  print("PASS: ENG-P08 PostgreSQL 17 Memory consent, proposal approval, owner-scoped retrieval, correction, deletion, retention expiry, least-privilege RPCs and P03 pseudonymous audit integration.")
 finally:
  run(["docker","rm","--force",NAME],check=False)


if __name__=="__main__":
 try:main()
 except Exception as exc:
  print(f"FAIL: ENG-P08 Memory Coordinator verification: {exc}",file=sys.stderr)
  raise SystemExit(1)
