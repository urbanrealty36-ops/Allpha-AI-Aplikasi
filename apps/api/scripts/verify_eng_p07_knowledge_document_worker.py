"""ENG-P07 PostgreSQL 17 verifier for private document ingestion and lease-fenced chunk handoff."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[3]
MIGRATIONS=ROOT/"apps/api/supabase/migrations"
FILES=[
 MIGRATIONS/"20261014173000_eng_p07_knowledge_fulltext_index.sql",
 MIGRATIONS/"20261014180000_eng_p09_knowledge_job_leases.sql",
 MIGRATIONS/"20261124044949_eng_p07_knowledge_document_worker_pipeline.sql",
 MIGRATIONS/"20261124045041_eng_p07_knowledge_api_only_writes.sql",
 MIGRATIONS/"20261124045115_eng_p07_knowledge_document_enqueue.sql",
 MIGRATIONS/"20261124045158_eng_p07_knowledge_document_failure_atomic.sql",
 MIGRATIONS/"20261124050240_eng_p07_knowledge_source_delete_fence.sql",
 MIGRATIONS/"20261124052416_eng_p07_delete_fence_owner_atomicity.sql",
 MIGRATIONS/"20261124052559_eng_p07_delete_fence_authorize_before_lookup.sql",
 MIGRATIONS/"20261124081300_eng_p07_knowledge_job_lease_heartbeat.sql",
 MIGRATIONS/"20261124091500_eng_p07_knowledge_source_state_lease_fence.sql",
]
NAME="allpha-p07-knowledge-"+uuid.uuid4().hex[:8]
OWNER="11111111-1111-4111-8111-111111111111"
AGENT="22222222-2222-4222-8222-222222222222"
SOURCE="33333333-3333-4333-8333-333333333333"
SOURCE_RETRY="44444444-4444-4444-8444-444444444444"
SOURCE_STALE="55555555-5555-4555-8555-555555555555"


def run(args:list[str],sql:str|None=None,check:bool=True)->subprocess.CompletedProcess[str]:
 result=subprocess.run(args,input=sql,text=True,capture_output=True)
 if check and result.returncode: raise RuntimeError(result.stdout+"\n"+result.stderr)
 return result


def psql(sql:str,check:bool=True)->subprocess.CompletedProcess[str]:
 result=run(["docker","exec","-i",NAME,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres"],sql,check=False)
 if check and result.returncode:
  logs=run(["docker","logs",NAME],check=False)
  raise RuntimeError(result.stdout+"\n"+result.stderr+"\nPostgreSQL logs:\n"+logs.stdout+logs.stderr)
 return result


def main()->None:
 run(["docker","run","-d","--rm","--name",NAME,"-e","POSTGRES_PASSWORD=ci-only","postgres:17-alpine"])
 try:
  ready=False
  ready_streak=0
  for _ in range(90):
   probe=run(["docker","exec",NAME,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False)
   if probe.returncode==0:
    ready_streak+=1
    if ready_streak>=3:
     ready=True
     break
   else:
    ready_streak=0
   time.sleep(1)
  if not ready:raise RuntimeError("PostgreSQL 17 did not reach stable SQL readiness")
  psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create schema private;
create schema extensions;
create schema storage;
create extension if not exists pgcrypto with schema extensions;
create function auth.uid() returns uuid language sql stable as $uid$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $uid$;
create function auth.role() returns text language sql stable as $role$ select nullif(current_setting('request.jwt.claim.role',true),'') $role$;
create table auth.users(id uuid primary key);
create table public.ai_agents(id uuid primary key);
create table public.agent_ownerships(
 agent_id uuid not null references public.ai_agents(id),
 owner_user_id uuid not null references auth.users(id),
 ownership_role text not null,status text not null,
 primary key(agent_id,owner_user_id,ownership_role)
);
create table public.agent_knowledge_sources(
 id uuid primary key,agent_id uuid not null,owner_id uuid not null,filename text not null,
 media_type text not null,size_bytes bigint not null,sha256 text not null,storage_path text not null,
 source_version integer not null default 1,status text not null,processing_stage text not null,
 error_code text,provenance jsonb not null default '{}',created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create table public.agent_knowledge_jobs(
 id uuid primary key default gen_random_uuid(),source_id uuid not null references public.agent_knowledge_sources(id) on delete cascade,
 agent_id uuid not null,owner_id uuid not null,status text not null,stage text not null,
 attempt integer not null default 0,progress integer not null default 0,error_code text,
 created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
create table public.agent_knowledge_chunks(
 id uuid primary key default gen_random_uuid(),source_id uuid not null references public.agent_knowledge_sources(id) on delete cascade,
 agent_id uuid not null,owner_id uuid not null,chunk_index integer not null,
 content text not null,source_location jsonb not null,source_version integer not null,
 content_sha256 text not null,created_at timestamptz not null default now(),
 unique(source_id,source_version,chunk_index)
);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text,name text);
grant usage on schema public,storage,extensions to anon,authenticated,service_role;
grant select,insert,update,delete on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks to authenticated,service_role;
grant all on storage.objects to authenticated,service_role;
""")
  for migration in FILES:
   if not migration.is_file():raise RuntimeError(f"Missing P07 migration: {migration}")
   psql(migration.read_text(encoding="utf-8"))
  psql(f"""
insert into auth.users(id) values('{OWNER}');
insert into public.ai_agents(id) values('{AGENT}');
insert into public.agent_ownerships(agent_id,owner_user_id,ownership_role,status)
 values('{AGENT}','{OWNER}','owner','active');
insert into public.agent_knowledge_sources(id,agent_id,owner_id,filename,media_type,size_bytes,sha256,storage_path,status,processing_stage,provenance)
values('{SOURCE}','{AGENT}','{OWNER}','notes.txt','text/plain',5,encode(extensions.digest('alpha','sha256'),'hex'),
 '{OWNER}/{AGENT}/{SOURCE}/notes.txt','quarantined','awaiting_malware_scan','{{"sensitivity":"internal"}}');
set role service_role;
set request.jwt.claim.role = 'service_role';
select public.enqueue_agent_knowledge_document_job('{SOURCE}','{AGENT}','{OWNER}',null);
select public.enqueue_agent_knowledge_document_job('{SOURCE}','{AGENT}','{OWNER}','duplicate request');
reset role;
do $do$
declare v_job public.agent_knowledge_jobs%rowtype;
begin
 if (select count(*) from public.agent_knowledge_jobs where source_id='{SOURCE}' and stage='awaiting_malware_scan')<>1 then
  raise exception 'enqueue idempotency created duplicate document jobs';
 end if;
 select * into v_job from public.agent_knowledge_jobs where source_id='{SOURCE}' and stage='awaiting_malware_scan';
 if v_job.status<>'queued' or v_job.idempotency_key is null then raise exception 'document job was not durably queued'; end if;
end $do$;
""")
  psql(f"""
set role service_role;
set request.jwt.claim.role = 'service_role';
select * from public.claim_agent_knowledge_job(90,'awaiting_malware_scan');
reset role;
set role service_role;
set request.jwt.claim.role = 'service_role';
do $do$
declare v_job public.agent_knowledge_jobs%rowtype; v_result jsonb;
begin
 select * into v_job from public.agent_knowledge_jobs where source_id='{SOURCE}' and stage='awaiting_malware_scan';
 if v_job.status<>'processing' or v_job.lease_token is null then raise exception 'document job lease not acquired'; end if;
 if not public.update_agent_knowledge_source_processing_state(
   v_job.id,v_job.lease_token,1,'malware_scan',null
 ) then raise exception 'valid document lease could not enter malware scan'; end if;
 if not public.update_agent_knowledge_source_processing_state(
   v_job.id,v_job.lease_token,1,'document_parsing',
   jsonb_build_object(
     'scanner_id','ci-scanner','engine_version','1.0','signature_version','ci-signatures',
     'sha256',(select sha256 from public.agent_knowledge_sources where id='{SOURCE}'),
     'contract_version','allpha.document-scan.v1'
   )
 ) then raise exception 'valid document lease could not persist scanner receipt'; end if;
 if not exists(
   select 1 from public.agent_knowledge_sources
   where id='{SOURCE}' and provenance->'malware_scan'->>'scanner_id'='ci-scanner'
 ) then raise exception 'scanner receipt provenance was not persisted'; end if;
 if not public.update_agent_knowledge_source_processing_state(
   v_job.id,v_job.lease_token,1,'chunk_persistence',null
 ) then raise exception 'valid document lease could not enter chunk persistence'; end if;
 perform public.persist_agent_knowledge_chunk_batch(
  v_job.id,v_job.lease_token,1,true,
  jsonb_build_array(
   jsonb_build_object('chunk_index',0,'content','alpha','source_location',jsonb_build_object('kind','page','index',1),'content_sha256',encode(extensions.digest('alpha','sha256'),'hex')),
   jsonb_build_object('chunk_index',1,'content','beta','source_location',jsonb_build_object('kind','page','index',2),'content_sha256',encode(extensions.digest('beta','sha256'),'hex'))
  )
 );
 select public.complete_agent_knowledge_document_parse(v_job.id,v_job.lease_token,1,2) into v_result;
 if v_result->>'retrieval_ready'<>'false' or (v_result->>'chunks_created')::integer<>2 then raise exception 'parse completion did not report pending retrieval QA'; end if;
 if not exists(select 1 from public.agent_knowledge_sources where id='{SOURCE}' and status='indexed_pending_embeddings' and processing_stage='awaiting_model_router') then
  raise exception 'source was not moved to embedding handoff state';
 end if;
 if not exists(select 1 from public.agent_knowledge_jobs where source_id='{SOURCE}' and stage='text_extracted' and status='succeeded') then
  raise exception 'document parse job not finalized';
 end if;
 if not exists(select 1 from public.agent_knowledge_jobs where source_id='{SOURCE}' and stage='embedding_indexing' and status='queued' and idempotency_key like 'knowledge:%') then
  raise exception 'embedding job was not durably queued';
 end if;
 if (select count(*) from public.agent_knowledge_chunks where source_id='{SOURCE}' and source_version=1)<>2 then
  raise exception 'chunk persistence count mismatch';
 end if;
end $do$;
reset role;
""")
  psql(f"""
insert into public.agent_knowledge_sources(id,agent_id,owner_id,filename,media_type,size_bytes,sha256,storage_path,status,processing_stage,provenance)
values('{SOURCE_RETRY}','{AGENT}','{OWNER}','retry.txt','text/plain',5,encode(extensions.digest('alpha','sha256'),'hex'),
 '{OWNER}/{AGENT}/{SOURCE_RETRY}/retry.txt','quarantined','awaiting_malware_scan','{{"sensitivity":"internal"}}');
set role service_role;
set request.jwt.claim.role = 'service_role';
select public.enqueue_agent_knowledge_document_job('{SOURCE_RETRY}','{AGENT}','{OWNER}',null);
select * from public.claim_agent_knowledge_job(90,'awaiting_malware_scan');
select public.fail_agent_knowledge_document_job(
 (select id from public.agent_knowledge_jobs where source_id='{SOURCE_RETRY}'),
 (select lease_token from public.agent_knowledge_jobs where source_id='{SOURCE_RETRY}'),
 'SCANNER_UNAVAILABLE','malware_scan_retry',true,0
);
reset role;
do $do$
begin
 if not exists(select 1 from public.agent_knowledge_sources where id='{SOURCE_RETRY}' and status='quarantined' and error_code='SCANNER_UNAVAILABLE') then
  raise exception 'retryable scanner failure did not retain source in quarantine';
 end if;
 if not exists(select 1 from public.agent_knowledge_jobs where source_id='{SOURCE_RETRY}' and status='queued' and stage='awaiting_malware_scan' and error_code='SCANNER_UNAVAILABLE') then
  raise exception 'retryable scanner failure did not requeue the job';
 end if;
end $do$;
""")
  psql(f"update public.agent_knowledge_jobs set available_at=clock_timestamp()+interval '1 hour' where source_id='{SOURCE_RETRY}' and status='queued';")
  psql(f"""
insert into public.agent_knowledge_sources(id,agent_id,owner_id,filename,media_type,size_bytes,sha256,storage_path,status,processing_stage,provenance)
values('{SOURCE_STALE}','{AGENT}','{OWNER}','stale.txt','text/plain',5,encode(extensions.digest('alpha','sha256'),'hex'),
 '{OWNER}/{AGENT}/{SOURCE_STALE}/stale.txt','quarantined','awaiting_malware_scan','{{"sensitivity":"internal"}}');
set role service_role;
set request.jwt.claim.role = 'service_role';
select public.enqueue_agent_knowledge_document_job('{SOURCE_STALE}','{AGENT}','{OWNER}',null);
select * from public.claim_agent_knowledge_job(90,'awaiting_malware_scan');
do $do$
declare v_job public.agent_knowledge_jobs%rowtype; v_old_token uuid; v_new_token uuid;
begin
 select * into v_job from public.agent_knowledge_jobs where source_id='{SOURCE_STALE}';
 v_old_token := v_job.lease_token;
 if v_job.status<>'processing' or v_old_token is null then
  raise exception 'Knowledge stale-lease fixture was not claimed';
 end if;
 update public.agent_knowledge_jobs set lease_expires_at=clock_timestamp()-interval '1 second' where id=v_job.id;
 if public.heartbeat_agent_knowledge_job(v_job.id,v_old_token,90) then
  raise exception 'expired Knowledge lease was incorrectly revived';
 end if;
 if public.update_agent_knowledge_source_processing_state(v_job.id,v_old_token,1,'malware_scan',null) then
  raise exception 'expired Knowledge lease updated source processing state';
 end if;
 perform public.claim_agent_knowledge_job(90,'awaiting_malware_scan');
 select lease_token into v_new_token from public.agent_knowledge_jobs where id=v_job.id;
 if v_new_token is null or v_new_token=v_old_token then
  raise exception 'expired Knowledge lease was not recovered with a new fencing token';
 end if;
 if not public.heartbeat_agent_knowledge_job(v_job.id,v_new_token,90) then
  raise exception 'current recovered Knowledge lease could not be renewed';
 end if;
 if not public.update_agent_knowledge_source_processing_state(v_job.id,v_new_token,1,'malware_scan',null) then
  raise exception 'current recovered Knowledge lease could not update source state';
 end if;
 update public.agent_knowledge_sources set source_version=source_version+1 where id='{SOURCE_STALE}';
 if public.heartbeat_agent_knowledge_job(v_job.id,v_new_token,90) then
  raise exception 'stale source-version Knowledge lease was incorrectly renewed';
 end if;
 if public.update_agent_knowledge_source_processing_state(v_job.id,v_new_token,1,'document_parsing',null) then
  raise exception 'stale source-version Knowledge lease updated source state';
 end if;
end $do$;
reset role;
""")
  psql("""
do $do$
begin
 if has_table_privilege('authenticated','public.agent_knowledge_sources','INSERT')
    or has_table_privilege('authenticated','public.agent_knowledge_sources','UPDATE')
    or has_table_privilege('authenticated','public.agent_knowledge_jobs','INSERT')
    or has_table_privilege('authenticated','public.agent_knowledge_chunks','DELETE') then
  raise exception 'authenticated role retains Knowledge lifecycle DML';
 end if;
 if not has_table_privilege('authenticated','public.agent_knowledge_sources','SELECT') then
  raise exception 'authenticated owner read access was removed';
 end if;
 if has_function_privilege('authenticated','public.persist_agent_knowledge_chunk_batch(uuid,uuid,integer,boolean,jsonb)','EXECUTE')
    or has_function_privilege('authenticated','public.complete_agent_knowledge_document_parse(uuid,uuid,integer,integer)','EXECUTE')
    or has_function_privilege('authenticated','public.enqueue_agent_knowledge_document_job(uuid,uuid,uuid,text)','EXECUTE')
    or has_function_privilege('authenticated','public.fail_agent_knowledge_document_job(uuid,uuid,text,text,boolean,integer)','EXECUTE')
    or has_function_privilege('authenticated','public.heartbeat_agent_knowledge_job(uuid,uuid,integer)','EXECUTE')
    or has_function_privilege('authenticated','public.update_agent_knowledge_source_processing_state(uuid,uuid,integer,text,jsonb)','EXECUTE') then
  raise exception 'authenticated role can execute privileged Knowledge RPCs';
 end if;
 if not has_function_privilege('service_role','public.persist_agent_knowledge_chunk_batch(uuid,uuid,integer,boolean,jsonb)','EXECUTE')
    or not has_function_privilege('service_role','public.complete_agent_knowledge_document_parse(uuid,uuid,integer,integer)','EXECUTE')
    or not has_function_privilege('service_role','public.enqueue_agent_knowledge_document_job(uuid,uuid,uuid,text)','EXECUTE')
    or not has_function_privilege('service_role','public.fail_agent_knowledge_document_job(uuid,uuid,text,text,boolean,integer)','EXECUTE')
    or not has_function_privilege('service_role','public.heartbeat_agent_knowledge_job(uuid,uuid,integer)','EXECUTE')
    or not has_function_privilege('service_role','public.update_agent_knowledge_source_processing_state(uuid,uuid,integer,text,jsonb)','EXECUTE') then
  raise exception 'service_role cannot execute Knowledge worker RPCs';
 end if;
end $do$;
""")
  unauthorized_delete=psql(f"""
set role service_role;
set request.jwt.claim.role = 'service_role';
select public.begin_agent_knowledge_source_delete('{SOURCE_RETRY}','{AGENT}','99999999-9999-4999-8999-999999999999');
""",check=False)
  if unauthorized_delete.returncode==0 or "AGENT_OWNER_REQUIRED" not in unauthorized_delete.stderr:
   raise RuntimeError("Knowledge source deletion fence accepted a non-owner")
  psql(f"""
set role service_role;
set request.jwt.claim.role = 'service_role';
select public.begin_agent_knowledge_source_delete('{SOURCE}','{AGENT}','{OWNER}');
reset role;
do $do$
declare v_source public.agent_knowledge_sources%rowtype; v_job public.agent_knowledge_jobs%rowtype;
begin
 select * into v_source from public.agent_knowledge_sources where id='{SOURCE}';
 if v_source.status<>'deleting' or v_source.processing_stage<>'source_deleting' then
  raise exception 'source delete fence did not persist deleting state';
 end if;
 select * into v_job from public.agent_knowledge_jobs where source_id='{SOURCE}' and stage='source_deleted';
 if not found or v_job.status<>'cancelled' or v_job.lease_token is not null or v_job.lease_expires_at is not null then
  raise exception 'in-flight knowledge job was not cancelled and lease-fenced';
 end if;
end $do$;
select public.begin_agent_knowledge_source_delete('{SOURCE}','{AGENT}','{OWNER}');
do $do$
begin
 if has_function_privilege('authenticated','public.begin_agent_knowledge_source_delete(uuid,uuid,uuid)','EXECUTE') then
  raise exception 'authenticated can execute privileged source deletion fence';
 end if;
end $do$;
""")
  print("PASS: ENG-P07 PostgreSQL 17 private quarantine enqueue, idempotency, lease-fenced chunk persistence, atomic embedding handoff, retry recovery, deletion fencing and client DML lockdown.")
 finally:
  run(["docker","rm","--force",NAME],check=False)


if __name__=="__main__":
 try:main()
 except Exception as exc:
  print(f"FAIL: ENG-P07 Knowledge document worker verification: {exc}",file=sys.stderr)
  raise SystemExit(1)
