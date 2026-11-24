"""ENG-P03 PostgreSQL 17 verification for legal-hold reconciliation and fail-closed deletion policy gates."""
from __future__ import annotations
from pathlib import Path
import subprocess,sys,time,uuid

ROOT=Path(__file__).resolve().parents[3]
EXECUTOR_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123142156_eng_p03_account_deletion_executor.sql"
DEPENDENCY_REQUEUE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123142329_eng_p03_deletion_dependency_requeue.sql"
RETENTION_CANONICAL_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123142451_eng_p03_retention_canonical_data_classes.sql"
LEGAL_HOLD_REQUEUE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123142930_eng_p03_deletion_legal_hold_release_requeue.sql"
STORAGE_DISPOSITION_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123143130_eng_p03_deletion_storage_disposition_gate.sql"
SOURCE_METADATA_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123143201_eng_p03_deletion_source_registry_metadata.sql"
REQUEUE_AUDIT_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124012454_eng_p03_requeue_audit_trail.sql"
RETENTION_PRECISION_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123170511_eng_p03_retention_legal_basis_precision.sql"
STORAGE_RETENTION_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123170158_eng_p03_storage_retention_snapshot_gate.sql"
IDENTITY_TOMBSTONE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123180112_eng_p03_identity_tombstones_and_provider_cancellation.sql"
EXECUTOR_HARDENING_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123180725_eng_p03_executor_referential_integrity_hardening.sql"
OWNERSHIP_TOMBSTONE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124005951_eng_p03_agent_ownership_tombstone_attribution.sql"
SUBJECT_DIGEST_REPAIR_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124010254_eng_p03_subject_digest_path_repairs.sql"
RETENTION_METADATA_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124010416_eng_p03_retention_request_metadata_accuracy.sql"
REQUEUE_AUDIT_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124012454_eng_p03_requeue_audit_trail.sql"
OWNER_DIRECTIVE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123170014_eng_p03_owner_directed_retention_baseline.sql"
OWNERSHIP_TRANSFER_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123173919_eng_p03_account_deletion_ownership_transfers.sql"
GOVERNANCE_RETRY_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123182248_eng_p03_governance_policy_gate_and_retry.sql"
FK_ACTION_GATE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124010741_eng_p03_fk_action_integrity_gate.sql"
EXPORT_DELETION_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124015229_eng_p03_account_export_deletion_lifecycle.sql"
DELETION_RPC_AMBIGUITY_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124020721_eng_p03_account_deletion_rpc_ambiguity_fix.sql"
MIGRATION=ROOT/"apps/api/supabase/migrations/20261123192200_eng_p03_deletion_legal_hold_governance_worker.sql"
SOURCE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123153243_eng_p03_account_deletion_specialized_source_handlers.sql"
OWNER_SCOPE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123153456_eng_p03_agent_skill_deletion_owner_scope.sql"
CANONICAL_REGISTRY_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123154208_eng_p03_canonical_source_handler_registry.sql"
FK_GUARD_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123154656_eng_p03_dependency_fk_parent_guard.sql"
USER_SCOPED_DEPENDENCY_MIGRATION=ROOT/"apps/api/supabase/migrations/20261123165628_eng_p03_user_scoped_deletion_dependencies.sql"
CONTAINER="allpha-p03-deletion-"+uuid.uuid4().hex[:8]
A="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
C="cccccccc-cccc-4ccc-8ccc-cccccccccccc"
D="dddddddd-dddd-4ddd-8ddd-dddddddddddd"
E="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
F="ffffffff-ffff-4fff-8fff-ffffffffffff"
HOLD_A="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
HOLD_B="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
OPEN_C="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"

def run(args,sql=None,check=True):
    result=subprocess.run(args,input=sql,text=True,capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout+"\\n"+result.stderr)
    return result

def psql(sql):
    return run(["docker","exec","-i",CONTAINER,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres"],sql)

def main():
    dollar_quote = chr(36) * 2
    run(["docker","run","-d","--rm","--name",CONTAINER,"-e","POSTGRES_PASSWORD=ci-only","postgres:17-alpine"])
    try:
        time.sleep(1)
        ready=False
        for _ in range(60):
            probe=run(["docker","exec",CONTAINER,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False)
            if probe.returncode==0:
                time.sleep(1)
                if run(["docker","exec",CONTAINER,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False).returncode==0:
                    ready=True;break
            time.sleep(1)
        if not ready: raise RuntimeError("PostgreSQL 17 did not reach stable SQL readiness")
        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create schema extensions;
create extension if not exists pgcrypto with schema extensions;
create schema private;
create table auth.users(id uuid primary key);
create table public.profiles(
 id uuid primary key references auth.users(id) on delete cascade,
 account_status text not null default 'active'
);
create table public.account_export_jobs(
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null constraint account_export_jobs_user_id_fkey references auth.users(id) on delete cascade,
 idempotency_key text not null,
 status text not null default 'queued'
   check(status in ('queued','running','succeeded','failed','cancelled','expired')),
 attempts integer not null default 0,
 max_attempts integer not null default 5,
 next_attempt_at timestamptz not null default now(),
 lease_token uuid,lease_owner text,lease_expires_at timestamptz,
 storage_bucket text not null default 'account-exports',storage_path text,
 file_sha256 text,file_size_bytes bigint,manifest jsonb not null default '{}'::jsonb,
 error_code text,requested_at timestamptz not null default now(),started_at timestamptz,
 completed_at timestamptz,failed_at timestamptz,expires_at timestamptz,
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
 unique(user_id,idempotency_key)
);
create table public.agent_knowledge_sources(owner_id uuid,storage_path text);
create table public.content_media(owner_id uuid,bucket_id text,storage_path text,derivatives jsonb);
create table public.generation_artifacts(owner_user_id uuid,storage_bucket text,storage_path text);
create table public.generation_artifact_deletion_jobs(owner_user_id uuid,bucket_id text,object_path text,status text,lease_expires_at timestamptz);
create table public.agent_consumer_grant_events(
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null constraint agent_consumer_grant_events_owner_user_id_fkey references auth.users(id) on delete restrict,
 details jsonb not null default '{}'::jsonb
);
create table public.billing_orders(
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null constraint billing_orders_owner_user_id_fkey references auth.users(id) on delete restrict,
 stripe_checkout_url text
);
create table public.billing_receipts(
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null constraint billing_receipts_owner_user_id_fkey references auth.users(id) on delete restrict,
 hosted_invoice_url text
);
create table public.billing_subscriptions(
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null constraint billing_subscriptions_owner_user_id_fkey references auth.users(id) on delete restrict,
 stripe_subscription_id text,stripe_environment text,
 status text not null default 'canceled',cancel_at_period_end boolean not null default false,
 updated_at timestamptz not null default now()
);
create table public.content_retention_holds(
 id uuid primary key default gen_random_uuid(),
 created_by uuid not null constraint content_retention_holds_created_by_fkey references auth.users(id) on delete restrict,
 reason text not null default 'retained'
);
create table public.credit_ledger_accounts(
 owner_user_id uuid primary key constraint credit_ledger_accounts_owner_user_id_fkey references auth.users(id) on delete restrict,
 balance numeric not null default 0
);
create table public.playback_entitlements(
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null constraint playback_entitlements_owner_user_id_fkey references auth.users(id) on delete restrict,
 status text not null default 'active',updated_at timestamptz not null default now()
);
create function auth.uid() returns uuid language sql stable as $uid$
 select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$uid$;
create function auth.role() returns text language sql stable as $role$
 select nullif(current_setting('request.jwt.claim.role',true),'')
$role$;
create function auth.jwt() returns jsonb language sql stable as $jwt$
 select coalesce(nullif(current_setting('request.jwt.claims',true),'')::jsonb,'{}'::jsonb)
$jwt$;
create function public.digest(text,text) returns bytea language sql immutable as $digest$
 select extensions.digest($1,$2)
$digest$;
grant usage on schema auth to public;
grant execute on function auth.role() to public;
create table public.account_deletion_requests(
 id uuid primary key default gen_random_uuid(),
 user_id uuid references auth.users(id) on delete set null,
 subject_ref text not null,
 status text not null check(status in ('awaiting_policy','scheduled','processing','blocked_legal_hold','completed','cancelled','failed')),
 policy_version text,
 requested_at timestamptz not null default now(),
 scheduled_for timestamptz,
 completed_at timestamptz,
 cancelled_at timestamptz,
 error_code text,
 request_metadata jsonb not null default '{}'::jsonb check(jsonb_typeof(request_metadata)='object'),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create table public.account_legal_holds(
 id uuid primary key default gen_random_uuid(),
 subject_ref text not null,
 reference_code text not null,
 reason_code text not null,
 active boolean not null default true,
 created_by uuid references auth.users(id) on delete set null,
 created_at timestamptz not null default now(),
 released_by uuid references auth.users(id),
 released_at timestamptz
);
create table public.account_lifecycle_events(
 id uuid primary key default gen_random_uuid(),
 request_id uuid references public.account_deletion_requests(id),
 export_job_id uuid,
 user_id uuid references auth.users(id) on delete set null,
 subject_ref text not null,
 event_type text not null check(event_type in ('export_requested','export_started','export_completed','export_failed','deletion_requested','deletion_cancelled','deletion_scheduled','deletion_started','deletion_blocked','deletion_unblocked','deletion_policy_pending','deletion_completed','deletion_failed')),
 metadata jsonb not null check(jsonb_typeof(metadata)='object'),
 recorded_at timestamptz not null default now()
);
create table private.account_export_sources(
 source_key text primary key, table_name text not null, filter_kind text not null,
 owner_columns text[] not null default '{}', sort_order integer not null default 100, enabled boolean not null default true
);
insert into private.account_export_sources(source_key,table_name,filter_kind) values
 ('unmapped_source','messages','participant_conversations'),
 ('agent_skills_owned','agent_skills','owned_agents'),
 ('agent_runtime_checkpoints','agent_runtime_checkpoints','owned_runtime_tasks'),
 ('agent_runtime_effect_receipts','agent_runtime_effect_receipts','owned_runtime_tasks'),
 ('content_comments_on_owned','content_comments','owned_content'),
 ('content_reactions_on_owned','content_reactions','content_activity'),
 ('messages_in_conversations','messages','conversation_messages'),
 ('community_posts_in_memberships','community_posts','member_communities'),
 ('workspace_documents_in_memberships','workspace_documents','member_workspaces'),
 ('workspace_annotations_in_memberships','workspace_annotations','member_workspaces');
""")
        # This isolated fixture has 10 representative source rows; the separate
        # production classification migration backfills 106 enabled sources.
        # Its exact migration contract is covered by test_eng_p03_account_deletion_disposition_migration_contract.py.
        for migration in (
            EXECUTOR_MIGRATION,DEPENDENCY_REQUEUE_MIGRATION,RETENTION_CANONICAL_MIGRATION,
            LEGAL_HOLD_REQUEUE_MIGRATION,STORAGE_DISPOSITION_MIGRATION,SOURCE_METADATA_MIGRATION,
            REQUEUE_AUDIT_MIGRATION,
        ):
            psql(migration.read_text(encoding="utf-8"))
        psql(MIGRATION.read_text(encoding="utf-8"))
        psql(MIGRATION.read_text(encoding="utf-8")) # repeatable forward migration
        psql(f"""
insert into auth.users(id) values ('{A}'),('{B}'),('{C}'),('{D}'),('{E}'),('{F}');
insert into public.account_legal_holds(subject_ref,reference_code,reason_code,active,created_by)
values ('{HOLD_A}','CASE-A','legal_preservation',true,'{A}'),
       ('{HOLD_B}','CASE-B','legal_preservation',false,'{B}');
insert into public.account_deletion_requests(user_id,subject_ref,status,request_metadata)
values ('{A}','{HOLD_A}','awaiting_policy','{{}}'),
       ('{B}','{HOLD_B}','blocked_legal_hold','{{}}'),
       ('{C}','{OPEN_C}','awaiting_policy','{{}}');
set request.jwt.claim.role='service_role';
do $$
declare v record;
begin
  select * into v from public.evaluate_account_deletion_governance(100);
  if v.processed_count<>3 or v.blocked_count<>1 or v.unblocked_count<>1 or v.policy_pending_count<>1 then
    raise exception 'unexpected first governance counts: %',row_to_json(v);
  end if;
end $$;
do $$
begin
  if (select status from public.account_deletion_requests where subject_ref='{HOLD_A}')<>'blocked_legal_hold' then
    raise exception 'active legal hold did not block deletion';
  end if;
  if (select status from public.account_deletion_requests where subject_ref='{HOLD_B}')<>'awaiting_policy' then
    raise exception 'released legal hold did not return to policy gate';
  end if;
  if (select status from public.account_deletion_requests where subject_ref='{OPEN_C}')<>'awaiting_policy' then
    raise exception 'request without policy was incorrectly scheduled';
  end if;
  if not exists(select 1 from public.account_lifecycle_events where event_type='deletion_blocked' and subject_ref='{HOLD_A}') then
    raise exception 'legal hold block audit event missing';
  end if;
  if not exists(select 1 from public.account_lifecycle_events where event_type='deletion_unblocked' and subject_ref='{HOLD_B}') then
    raise exception 'legal hold release audit event missing';
  end if;
  if not exists(select 1 from public.account_lifecycle_events where event_type='deletion_policy_pending' and subject_ref='{OPEN_C}') then
    raise exception 'missing policy audit event missing';
  end if;
  if exists(select 1 from public.account_deletion_requests where status in ('processing','completed')) then
    raise exception 'governance evaluator performed destructive deletion without dependency map';
  end if;
end $$;
update public.account_legal_holds set active=false,released_by='{A}',released_at=now() where subject_ref='{HOLD_A}';
do $$
declare v record;
begin
  if (select status from public.account_deletion_requests where subject_ref='{HOLD_A}')<>'awaiting_policy' then
    raise exception 'legal hold release trigger did not requeue request';
  end if;
  if not exists(select 1 from public.account_lifecycle_events
    where subject_ref='{HOLD_A}' and event_type='deletion_unblocked'
      and metadata->>'reason_code'='LEGAL_HOLD_RELEASED_REEVALUATION_REQUIRED') then
    raise exception 'legal hold release requeue audit event missing';
  end if;
  select * into v from public.evaluate_account_deletion_governance(100);
  if v.unblocked_count<>0 then raise exception 'governance double-counted a trigger-requeued request'; end if;
end $$;
insert into public.account_deletion_requests(user_id,subject_ref,status,request_metadata)
values ('{D}','{D}','blocked_dependency','{{}}');
insert into public.account_deletion_dependency_rules(
 child_schema,child_table,constraint_name,delete_rule,resolution_action,reason,active
) values ('public','ci_requeue_test','ci_requeue_test_fkey','RESTRICT','block',
 'isolated trigger audit verification',true);
do $$
begin
  if (select status from public.account_deletion_requests where subject_ref='{D}')<>'awaiting_policy' then
    raise exception 'dependency policy change did not requeue blocked request';
  end if;
  if not exists(select 1 from public.account_lifecycle_events
    where subject_ref='{D}' and event_type='deletion_unblocked'
      and metadata->>'reason_code'='DEPENDENCY_POLICY_CHANGED_REEVALUATION_REQUIRED') then
    raise exception 'dependency requeue audit event missing';
  end if;
end $$;
do $$
begin
  if has_function_privilege('authenticated','public.evaluate_account_deletion_governance(integer)','EXECUTE')
     or has_function_privilege('anon','public.evaluate_account_deletion_governance(integer)','EXECUTE') then
    raise exception 'deletion governance RPC exposed to clients';
  end if;
  if not has_function_privilege('service_role','public.evaluate_account_deletion_governance(integer)','EXECUTE') then
    raise exception 'service_role governance grant missing';
  end if;
end $$;
""")
        # Exercise the specialized source handlers in an isolated PostgreSQL database.
        psql("""
grant usage on schema private to service_role;
create table public.ai_agents(id uuid primary key,handle text unique,display_name text);
create table public.agent_ownerships(
 agent_id uuid not null constraint agent_ownerships_agent_id_fkey references public.ai_agents(id) on delete cascade,
 owner_user_id uuid not null constraint agent_ownerships_owner_user_id_fkey references auth.users(id) on delete restrict,
 ownership_role text not null,status text not null,primary key(agent_id,owner_user_id)
);
create table public.organizations(
 id uuid primary key,slug text unique,name text not null,
 owner_id uuid not null constraint organizations_owner_id_fkey references auth.users(id) on delete restrict,
 created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
create table public.organization_memberships(
 organization_id uuid not null references public.organizations(id) on delete cascade,
 user_id uuid not null constraint organization_memberships_user_id_fkey references auth.users(id) on delete cascade,
 role text not null default 'member',primary key(organization_id,user_id)
);
create table public.agent_skills(id uuid primary key,agent_id uuid,created_by uuid);
create table public.agent_runtime_tasks(id uuid primary key,owner_user_id uuid);
create table public.agent_runtime_checkpoints(id uuid primary key,task_id uuid);
create table public.agent_runtime_effect_receipts(id uuid primary key,task_id uuid);
create table public.content_items(id uuid primary key,owner_id uuid);
create table public.content_comments(id uuid primary key,content_id uuid,actor_user_id uuid);
create table public.content_reactions(id uuid primary key,content_id uuid,actor_user_id uuid);
create table public.messages(id uuid primary key,sender_user_id uuid,conversation_id uuid);
create table public.community_posts(id uuid primary key,author_id uuid,community_id uuid);
create table public.workspace_documents(id uuid primary key,created_by uuid,workspace_id uuid);
create table public.workspace_annotations(id uuid primary key,author_id uuid,workspace_id uuid);
""")
        psql(f"create function public.list_account_deletion_source_registry() returns boolean language sql as {dollar_quote} select true {dollar_quote};")
        source_sql=SOURCE_MIGRATION.read_text(encoding="utf-8").split("\ndo " + chr(36) + chr(36),1)[0]
        psql(source_sql)
        psql(OWNER_SCOPE_MIGRATION.read_text(encoding="utf-8"))
        psql(CANONICAL_REGISTRY_MIGRATION.read_text(encoding="utf-8"))
        psql(FK_GUARD_MIGRATION.read_text(encoding="utf-8"))
        psql(USER_SCOPED_DEPENDENCY_MIGRATION.read_text(encoding="utf-8"))
        psql(f"""
do {dollar_quote}
begin
 if position('account_deletion_fk_parent_not_auth_user' in pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure))=0 then
   raise exception 'dependency FK parent guard was not installed';
 end if;
 if position('auth.users' in pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure))=0 then
   raise exception 'dependency FK parent check is missing';
 end if;
 if position('account_deletion_storage_jobs' in pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure))=0
    or position('preserved' in pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure))=0 then
   raise exception 'database executor does not wait for completed/preserved Storage disposition';
 end if;
 if not exists(select 1 from information_schema.columns where table_schema='public'
   and table_name='account_deletion_storage_jobs' and column_name='source_key') then
   raise exception 'source-aware Storage job key is missing';
 end if;
 if not exists(select 1 from information_schema.columns where table_schema='public'
   and table_name='account_deletion_source_policies' and column_name='owner_columns') then
   raise exception 'source registry metadata columns are missing';
 end if;
 if to_regclass('public.account_data_retention_policies') is null then
   raise exception 'canonical retention policy table is missing';
 end if;
end {dollar_quote};
""")
        psql(f"""
insert into public.ai_agents(id,handle,display_name) values
 ('{A}','agent-a','Agent A'),('{B}','agent-b','Agent B'),('{C}','agent-c','Agent C'),('{D}','agent-d','Agent D'),('{E}','agent-e','Agent E');
insert into public.agent_ownerships values
 ('{A}','{A}','owner','active'),('{B}','{B}','owner','active'),('{C}','{A}','operator','active'),
 ('{D}','{A}','owner','inactive');
insert into public.agent_skills(id,agent_id,created_by) values
 ('{uuid.uuid4()}','{A}','{A}'),('{uuid.uuid4()}','{B}','{B}'),('{uuid.uuid4()}','{C}','{A}'),('{uuid.uuid4()}','{D}','{A}');
insert into public.agent_runtime_tasks values ('{A}','{A}'),('{B}','{B}');
insert into public.agent_runtime_checkpoints values ('{uuid.uuid4()}','{A}'),('{uuid.uuid4()}','{B}');
insert into public.agent_runtime_effect_receipts values ('{uuid.uuid4()}','{A}'),('{uuid.uuid4()}','{B}');
insert into public.content_items values ('{A}','{A}'),('{B}','{B}');
insert into public.content_comments values ('{uuid.uuid4()}','{A}','{B}'),('{uuid.uuid4()}','{B}','{A}');
insert into public.content_reactions values ('{uuid.uuid4()}','{A}','{B}'),('{uuid.uuid4()}','{B}','{A}'),('{uuid.uuid4()}','{B}','{B}');
insert into public.messages values ('{uuid.uuid4()}','{A}','{C}'),('{uuid.uuid4()}','{B}','{C}');
insert into public.community_posts values ('{uuid.uuid4()}','{A}','{C}'),('{uuid.uuid4()}','{B}','{C}');
insert into public.workspace_documents values ('{uuid.uuid4()}','{A}','{C}'),('{uuid.uuid4()}','{B}','{C}');
insert into public.workspace_annotations values ('{uuid.uuid4()}','{A}','{C}'),('{uuid.uuid4()}','{B}','{C}');
set request.jwt.claim.role='service_role';
set role service_role;
select private.delete_account_source_rows('agent_skills_owned','{A}');
select private.delete_account_source_rows('agent_runtime_checkpoints','{A}');
select private.delete_account_source_rows('agent_runtime_effect_receipts','{A}');
select private.delete_account_source_rows('content_comments_on_owned','{A}');
select private.delete_account_source_rows('content_reactions_on_owned','{A}');
select private.delete_account_source_rows('messages_in_conversations','{A}');
select private.delete_account_source_rows('community_posts_in_memberships','{A}');
select private.delete_account_source_rows('workspace_documents_in_memberships','{A}');
select private.delete_account_source_rows('workspace_annotations_in_memberships','{A}');
do {dollar_quote}
begin
 if (select count(*) from public.list_account_deletion_source_registry() where enabled and deletion_handler_available)<>9 then
   raise exception 'canonical deletion handler registry did not expose all nine specialized handlers';
 end if;
 if (select count(*) from public.list_account_deletion_source_registry() where enabled and not deletion_handler_available)<>1 then
   raise exception 'canonical deletion handler registry failed closed for unknown source';
 end if;
end {dollar_quote};
reset role;
do {dollar_quote}
begin
 if (select count(*) from public.agent_skills)<>3 then raise exception 'agent skill deletion escaped active owner scope'; end if;
 if (select count(*) from public.agent_runtime_checkpoints)<>1 or (select count(*) from public.agent_runtime_effect_receipts)<>1 then raise exception 'runtime task child deletion scope incorrect'; end if;
 if (select count(*) from public.content_comments)<>1 then raise exception 'owned content comments deletion scope incorrect'; end if;
 if (select count(*) from public.content_reactions)<>1 then raise exception 'content activity deletion scope incorrect'; end if;
 if (select count(*) from public.messages)<>1 then raise exception 'shared conversation deleted another sender message'; end if;
 if (select count(*) from public.community_posts)<>1 then raise exception 'community membership deleted another author post'; end if;
 if (select count(*) from public.workspace_documents)<>1 then raise exception 'workspace membership deleted another creator document'; end if;
 if (select count(*) from public.workspace_annotations)<>1 then raise exception 'workspace membership deleted another author annotation'; end if;
 if has_function_privilege('authenticated','private.delete_account_source_rows(text,uuid)','EXECUTE')
    or has_function_privilege('anon','private.delete_account_source_rows(text,uuid)','EXECUTE') then
   raise exception 'specialized deletion helper exposed to client roles';
 end if;
end $$;
""")
        # This fixture has 10 source rows, not the production 106-source catalog.
        # Keep generic source policies inactive and seed only six isolated retention classes.
        psql("""
update public.account_deletion_source_policies set active=false;
alter table public.account_data_retention_policies
  add column if not exists decision_source text not null default 'operator_approval',
  add column if not exists decision_reference text;
alter table public.account_data_retention_policies
  alter column approved_by drop not null,
  alter column approved_at drop not null;
alter table public.account_deletion_source_policies
  add column if not exists decision_source text not null default 'operator_approval',
  add column if not exists decision_reference text;
insert into public.account_data_retention_policies(
 data_class,retention_days,policy_version,legal_basis,approved_by,approved_at,
 active,decision_source,decision_reference
) values
 ('owner_private',0,'owner-directive-2026-11-23-v1','UU No. 27/2022 Pasal 42-44: CI-only synthetic retention fixture',null,null,true,'product_owner_directive','CI_ONLY'),
 ('agent_operational',0,'owner-directive-2026-11-23-v1','UU No. 27/2022 Pasal 42-44: CI-only synthetic retention fixture',null,null,true,'product_owner_directive','CI_ONLY'),
 ('tenant_shared',0,'owner-directive-2026-11-23-v1','UU No. 27/2022 Pasal 42-44: CI-only synthetic retention fixture',null,null,true,'product_owner_directive','CI_ONLY'),
 ('published_knowledge',0,'owner-directive-2026-11-23-v1','UU No. 27/2022 Pasal 42-44: CI-only synthetic retention fixture',null,null,true,'product_owner_directive','CI_ONLY'),
 ('session_scoped',0,'owner-directive-2026-11-23-v1','UU No. 27/2022 Pasal 42-44: CI-only synthetic retention fixture',null,null,true,'product_owner_directive','CI_ONLY'),
 ('public_catalog',0,'owner-directive-2026-11-23-v1','UU No. 27/2022 Pasal 42-44: CI-only synthetic retention fixture',null,null,true,'product_owner_directive','CI_ONLY');
""")
        # Reuse only the canonical owner-directive function definitions here. The
        # production migration's 106-source backfill is intentionally not replayed
        # into this 10-source fixture.
        owner_source=OWNER_DIRECTIVE_MIGRATION.read_text(encoding="utf-8")
        owner_lower=owner_source.lower()
        for function_name in (
            "public.prepare_account_deletion_execution",
            "public.evaluate_account_deletion_governance",
            "public.execute_account_deletion_execution_job",
        ):
            marker="create or replace function "+function_name
            start=owner_lower.index(marker)
            opening=owner_lower.index("$function$",start)
            closing=owner_lower.index("$function$",opening+len("$function$"))
            end=owner_lower.index(";",closing)+1
            psql(owner_source[start:end])
        for migration in (
            STORAGE_RETENTION_MIGRATION,
            OWNERSHIP_TRANSFER_MIGRATION,
            IDENTITY_TOMBSTONE_MIGRATION,
            EXECUTOR_HARDENING_MIGRATION,
            OWNERSHIP_TOMBSTONE_MIGRATION,
            SUBJECT_DIGEST_REPAIR_MIGRATION,
            GOVERNANCE_RETRY_MIGRATION,
            RETENTION_PRECISION_MIGRATION,
            RETENTION_METADATA_MIGRATION,
            FK_ACTION_GATE_MIGRATION,
            REQUEUE_AUDIT_MIGRATION,
            EXPORT_DELETION_MIGRATION,
            DELETION_RPC_AMBIGUITY_MIGRATION,
        ):
            psql(migration.read_text(encoding="utf-8"))
        psql("alter table public.account_deletion_execution_jobs alter column user_id drop not null;")
        psql(f"""
insert into public.profiles(id,account_status) values ('{D}','active');
set request.jwt.claim.role='service_role';
do {dollar_quote}
declare
  v_request record;
  v_gate jsonb;
  v_prepare jsonb;
  v_confirmation jsonb;
begin
  select * into v_request
    from public.create_account_deletion_request_for_actor('{D}'::uuid,'ci-deletion-export-0001');
  if v_request.export_status<>'queued' or v_request.export_job_id is null then
    raise exception 'deletion request did not create its linked export job';
  end if;
  v_gate:=private.account_deletion_export_gate('{D}'::uuid,v_request.export_job_id);
  if coalesce((v_gate->>'ready')::boolean,true) or v_gate->>'code'<>'ACCOUNT_EXPORT_PENDING' then
    raise exception 'queued export was not a hard deletion gate: %',v_gate;
  end if;
  v_prepare:=public.prepare_account_deletion_execution(v_request.id);
  if v_prepare->>'outcome'<>'blocked_dependency'
     or v_prepare->'export_gate'->>'code'<>'ACCOUNT_EXPORT_PENDING' then
    raise exception 'deletion executor did not stop before Storage/DB cleanup for pending export: %',v_prepare;
  end if;
  update public.account_export_jobs
     set status='succeeded',storage_bucket='account-exports',
         storage_path='{D}/ci-deletion-export-0001.json.gz',
         file_sha256=repeat('a',64),file_size_bytes=128,manifest='{{}}'::jsonb,
         completed_at=clock_timestamp()
   where id=v_request.export_job_id and user_id='{D}';
  if not found then raise exception 'isolated export artifact receipt was not persisted'; end if;
  perform set_config('request.jwt.claim.sub','{D}',true);
  perform set_config('request.jwt.claim.role','authenticated',true);
  v_confirmation:=public.confirm_account_deletion_export_download(v_request.id);
  if v_confirmation->>'status'<>'confirmed' then
    raise exception 'authenticated owner could not confirm export download: %',v_confirmation;
  end if;
  perform set_config('request.jwt.claim.role','service_role',true);
  v_gate:=private.account_deletion_export_gate('{D}'::uuid,v_request.export_job_id);
  if coalesce((v_gate->>'ready')::boolean,false)=false
     or v_gate->>'code'<>'ACCOUNT_EXPORT_DOWNLOAD_CONFIRMED' then
    raise exception 'confirmed export did not release only the export gate: %',v_gate;
  end if;
  if not exists(select 1 from public.account_lifecycle_events
    where request_id=v_request.id and event_type='deletion_unblocked'
      and metadata->>'reason_code'='EXPORT_DOWNLOAD_CONFIRMED_REEVALUATION_REQUIRED') then
    raise exception 'export confirmation audit event missing';
  end if;
  if (select status from public.account_deletion_requests where id=v_request.id)<>'awaiting_policy' then
    raise exception 'export confirmation did not return request to policy reevaluation';
  end if;
end {dollar_quote};
""")
        print("PASS: ENG-P03 legal hold, shared-source deletion, export-before-deletion and owner download confirmation verified on isolated PostgreSQL 17.")

    finally:
        run(["docker","rm","--force",CONTAINER],check=False)

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print(f"FAIL: ENG-P03 deletion governance PostgreSQL 17 verification: {exc}",file=sys.stderr)
        raise SystemExit(1)
