"""ENG-P09 PostgreSQL 17 verifier for model policy approval, moderation governance and usage summary."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[3]
MIGRATION=ROOT/"apps/api/supabase/migrations/20261124064458_eng_p09_model_policy_approval_metadata.sql"
CAPABILITY_SCOPE_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124082219_eng_p09_model_cost_capability_scope.sql"
CAPABILITY_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124080255_eng_p09_model_capability_contract.sql"
METERING_CAPABILITY_MIGRATION=ROOT/"apps/api/supabase/migrations/20261124081303_eng_p09_usage_metering_capability.sql"
TOKEN_DETAIL_MIGRATION=ROOT/"apps/api/supabase/source-only-migrations/20261126110000_eng_p09_usage_token_details.sql"
NAME="allpha-p09-policy-"+uuid.uuid4().hex[:8]
OWNER="11111111-1111-4111-8111-111111111111"


def run(args:list[str],sql:str|None=None,check:bool=True)->subprocess.CompletedProcess[str]:
    result=subprocess.run(args,input=sql,text=True,capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout+"\n"+result.stderr)
    return result


def psql(sql:str,check:bool=True)->subprocess.CompletedProcess[str]:
    result=run(["docker","exec","-i",NAME,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres"],sql,check=False)
    if check and result.returncode:
        logs=run(["docker","logs",NAME],check=False)
        raise RuntimeError(result.stdout+"\n"+result.stderr+"\nPostgreSQL logs:\n"+logs.stdout+logs.stderr)
    return result


def main()->None:
    if not MIGRATION.is_file():
        raise RuntimeError(f"Missing P09 migration: {MIGRATION}")
    if not CAPABILITY_SCOPE_MIGRATION.is_file():
        raise RuntimeError(f"Missing P09 capability-scope migration: {CAPABILITY_SCOPE_MIGRATION}")
    if not CAPABILITY_MIGRATION.is_file():
        raise RuntimeError(f"Missing P09 capability migration: {CAPABILITY_MIGRATION}")
    if not METERING_CAPABILITY_MIGRATION.is_file():
        raise RuntimeError(f"Missing P09 metering-capability migration: {METERING_CAPABILITY_MIGRATION}")
    if not TOKEN_DETAIL_MIGRATION.is_file():
        raise RuntimeError(f"Missing P09 token-detail migration: {TOKEN_DETAIL_MIGRATION}")
    run(["docker","run","-d","--rm","--name",NAME,"-e","POSTGRES_PASSWORD=ci-only","postgres:17-alpine"])
    try:
        ready=False
        readiness_sql=["docker","exec",NAME,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"]
        for _ in range(60):
            probe=run(readiness_sql,check=False)
            if probe.returncode==0 and probe.stdout.strip()=="1":
                time.sleep(1)
                stable=run(readiness_sql,check=False)
                if stable.returncode==0 and stable.stdout.strip()=="1":
                    ready=True
                    break
            time.sleep(1)
        if not ready:
            raise RuntimeError("PostgreSQL 17 did not reach stable SQL readiness")

        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create table auth.users(id uuid primary key);
create table public.ai_model_cost_configs(
 id uuid primary key default gen_random_uuid(),
 provider_id text not null,model_id text not null,model_version text not null,
 pricing_version text not null,cost_unit text not null,
 input_micro_cost_per_token bigint not null,output_micro_cost_per_token bigint not null,
 max_cost_microunits bigint not null,max_prompt_bytes integer not null default 16384,
 max_output_tokens integer not null default 1024,max_latency_ms integer not null default 30000,
 status text not null default 'draft',policy_approved boolean not null default false,
 effective_at timestamptz,created_by uuid references auth.users(id) on delete set null,
 updated_by uuid references auth.users(id) on delete set null,created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),unique(provider_id,model_id,pricing_version)
);
create unique index ai_model_cost_one_active_version
 on public.ai_model_cost_configs(provider_id,model_id) where status='active';
create table public.generation_output_moderation_policies(
 policy_version text primary key,approval_reference text not null,configuration jsonb not null,
 status text not null default 'draft',effective_at timestamptz not null,expires_at timestamptz,
 approved_by uuid references auth.users(id) on delete set null,created_at timestamptz not null default now(),
 check(char_length(policy_version) between 1 and 80),
 check(char_length(approval_reference) between 3 and 160),
 check(jsonb_typeof(configuration)='object'),
 check(status in ('draft','approved','retired')),
 check(expires_at is null or expires_at>effective_at),
 check(status<>'approved' or approved_by is not null)
);
create table public.agent_model_usage_metering(
 id uuid primary key default gen_random_uuid(),idempotency_key text not null unique,
 task_id text not null,trace_id text not null,owner_id text not null,billing_account_id text not null,agent_id text not null,
 source_id text not null,source_version integer not null,sensitivity text not null,
 provider_id text not null,model_id text not null,model_version text not null,
 usage_units bigint not null,usage_unit text not null,cost_microunits bigint not null,
 cost_unit text not null,pricing_version text not null,completed_at timestamptz not null,
 payload_fingerprint text not null,created_at timestamptz not null default now()
);
grant usage on schema public to anon,authenticated,service_role;
grant select,insert,update,delete on public.ai_model_cost_configs to service_role;
grant select,insert,update,delete on public.generation_output_moderation_policies to service_role;
grant select,insert on public.agent_model_usage_metering to service_role;
""")
        # Model-cost capability was already part of the API contract, but the
        # production table lacked the column. Seed the exact observed legacy
        # Qwen text-generation row before running the forward backfill.
        psql("""
insert into public.ai_model_cost_configs(
 provider_id,model_id,model_version,pricing_version,cost_unit,
 input_micro_cost_per_token,output_micro_cost_per_token,max_cost_microunits,
 status,effective_at
) values(
 'nvidia-nim','qwen/qwen2.5-coder-32b-instruct','qwen/qwen2.5-coder-32b-instruct',
 'legacy-test-v1','USD',0,0,1000,'active',clock_timestamp()
);
""")
        psql(MIGRATION.read_text(encoding="utf-8"))
        psql(CAPABILITY_SCOPE_MIGRATION.read_text(encoding="utf-8"))
        psql(CAPABILITY_MIGRATION.read_text(encoding="utf-8"))
        psql(METERING_CAPABILITY_MIGRATION.read_text(encoding="utf-8"))
        psql(TOKEN_DETAIL_MIGRATION.read_text(encoding="utf-8"))
        psql("""
do $do$
begin
 if not exists (
  select 1 from public.ai_model_cost_configs
  where provider_id='nvidia-nim'
    and model_id='qwen/qwen2.5-coder-32b-instruct'
    and capability='text_generation'
 ) then
  raise exception 'existing model capability was not backfilled';
 end if;
end $do$;
""")

        psql(f"""
insert into auth.users(id) values('{OWNER}');
insert into public.ai_model_cost_configs(
 id,capability,provider_id,model_id,model_version,pricing_version,cost_unit,
 input_micro_cost_per_token,output_micro_cost_per_token,max_cost_microunits,
 status,effective_at
) values(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','text_generation','provider-x','model-x','v1','price-v1','USD',
 2,4,1000,'active',clock_timestamp()
);
do $do$
begin
 if (select policy_approved from public.ai_model_cost_configs where id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa') then
  raise exception 'tariff activation unexpectedly approved execution policy';
 end if;
end $do$;
update public.ai_model_cost_configs set policy_approved=true,
 policy_approval_reference='MODEL-APPROVAL-REF-01',policy_approved_by='{OWNER}',
 policy_approved_at=clock_timestamp()
 where id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
do $do$
begin
 if not exists(select 1 from public.ai_model_cost_configs where id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
   and policy_approved and policy_approved_by='{OWNER}' and policy_approved_at is not null
   and policy_approval_reference='MODEL-APPROVAL-REF-01') then
  raise exception 'auditable model policy approval was not persisted';
 end if;
end $do$;
update public.ai_model_cost_configs set policy_approved=false,policy_approval_reference=null,
 policy_approved_by=null,policy_approved_at=null where id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
insert into public.ai_model_cost_configs(
 id,capability,provider_id,model_id,model_version,pricing_version,cost_unit,
 input_micro_cost_per_token,output_micro_cost_per_token,max_cost_microunits,status,effective_at
) values(
 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','embedding','provider-x','model-x','v1','price-embedding-v1','USD',
 2,0,1000,'active',clock_timestamp()
);
""")

        invalid=psql(f"""
update public.ai_model_cost_configs set policy_approved=true
 where id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
""",check=False)
        if invalid.returncode==0:
            raise RuntimeError("model policy approval without immutable approval evidence was accepted")

        draft=psql(f"""
insert into public.ai_model_cost_configs(
 provider_id,model_id,model_version,pricing_version,cost_unit,input_micro_cost_per_token,
 output_micro_cost_per_token,max_cost_microunits,status,policy_approved
) values('provider-x','model-draft','v1','price-draft','USD',1,1,100,'draft',false);
update public.ai_model_cost_configs set policy_approved=true,
 policy_approval_reference='MODEL-APPROVAL-REF-02',policy_approved_by='{OWNER}',
 policy_approved_at=clock_timestamp()
 where model_id='model-draft';
""",check=False)
        if draft.returncode==0:
            raise RuntimeError("draft tariff was allowed to hold an approved execution policy")

        psql("""
insert into public.generation_output_moderation_policies(
 policy_version,approval_reference,configuration,status,effective_at,approved_by
) values('manual-v1','MODERATION-APPROVAL-01',
 '{"mode":"manual_review_only","manual_review_only":true}'::jsonb,'approved',clock_timestamp(),
 '11111111-1111-4111-8111-111111111111');
""")
        duplicate=psql("""
insert into public.generation_output_moderation_policies(
 policy_version,approval_reference,configuration,status,effective_at,approved_by
) values('manual-v2','MODERATION-APPROVAL-02',
 '{"mode":"manual_review_only","manual_review_only":true}'::jsonb,'approved',clock_timestamp(),
 '11111111-1111-4111-8111-111111111111');
""",check=False)
        if duplicate.returncode==0:
            raise RuntimeError("multiple active generation-output moderation policies were accepted")

        psql("""
insert into public.agent_model_usage_metering(
 idempotency_key,task_id,trace_id,owner_id,billing_account_id,agent_id,source_id,source_version,sensitivity,capability,
 provider_id,model_id,model_version,usage_units,usage_unit,input_tokens,output_tokens,cost_microunits,cost_unit,
 pricing_version,completed_at,payload_fingerprint
) values
 ('key-1','task-1','trace-1','owner-1','payer-1','agent-1','skill-1',1,'internal','text_generation','provider-x','model-x','v1',10,'tokens',6,4,20,'USD','price-v1',clock_timestamp(),repeat('a',64)),
 ('key-2','task-2','trace-2','owner-1','payer-1','agent-1','skill-1',1,'internal','embedding','provider-x','model-x','v1',12,'input_tokens',12,0,30,'EUR','price-v2',clock_timestamp(),repeat('b',64));
do $do$
declare v jsonb;
begin
 v:=public.get_agent_model_usage_summary(clock_timestamp()-interval '1 day',clock_timestamp()+interval '1 second');
 if (v->'totals'->>'runs')::integer<>2 then raise exception 'usage summary total run count incorrect'; end if;
 if (v->'totals'->>'input_tokens')::bigint<>18 then raise exception 'usage summary input-token total incorrect'; end if;
 if (v->'totals'->>'output_tokens')::bigint<>4 then raise exception 'usage summary output-token total incorrect'; end if;
 if jsonb_array_length(v->'by_provider_model')<>2 then raise exception 'usage summary incorrectly mixed currencies/pricing versions'; end if;
 if jsonb_array_length(v->'by_capability')<>2 then raise exception 'usage summary did not separate model capabilities'; end if;
end $do$;
""")

        psql("""
set role service_role;
select public.record_agent_model_usage_metering('{
 "idempotency_key":"rpc-embedding-1","task_id":"embedding-task-1","trace_id":"embedding-trace-1",
 "owner_id":"owner-1","billing_account_id":"payer-1","agent_id":"agent-1","source_id":"source-1",
 "source_version":1,"sensitivity":"internal","capability":"embedding","provider_id":"provider-x",
 "model_id":"model-x","model_version":"v1","usage_units":4,"usage_unit":"input_tokens",
 "input_tokens":4,"output_tokens":0,"cost_microunits":8,"cost_unit":"USD","pricing_version":"price-v1",
 "completed_at":"2026-11-24T00:00:00+00:00","payload_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
}'::jsonb);
select public.record_agent_model_usage_metering('{
 "idempotency_key":"rpc-embedding-1","task_id":"embedding-task-1","trace_id":"embedding-trace-1",
 "owner_id":"owner-1","billing_account_id":"payer-1","agent_id":"agent-1","source_id":"source-1",
 "source_version":1,"sensitivity":"internal","capability":"embedding","provider_id":"provider-x",
 "model_id":"model-x","model_version":"v1","usage_units":4,"usage_unit":"input_tokens",
 "cost_microunits":8,"cost_unit":"USD","pricing_version":"price-v1",
 "completed_at":"2026-11-24T00:00:00+00:00","payload_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
}'::jsonb);
reset role;
""")
        conflict=psql("""
set role service_role;
select public.record_agent_model_usage_metering('{
 "idempotency_key":"rpc-embedding-1","task_id":"embedding-task-1","trace_id":"embedding-trace-1",
 "owner_id":"owner-1","billing_account_id":"payer-1","agent_id":"agent-1","source_id":"source-1",
 "source_version":1,"sensitivity":"internal","capability":"embedding","provider_id":"provider-x",
 "model_id":"model-x","model_version":"v1","usage_units":4,"usage_unit":"input_tokens",
 "input_tokens":4,"output_tokens":0,"cost_microunits":9,"cost_unit":"USD","pricing_version":"price-v1",
 "completed_at":"2026-11-24T00:00:00+00:00","payload_fingerprint":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
}'::jsonb);
reset role;
""",check=False)
        if conflict.returncode==0:
            raise RuntimeError("metering RPC accepted conflicting reuse of an idempotency key")

        psql("""
set role service_role;
select public.record_agent_model_usage_metering(jsonb_build_object(
 'idempotency_key','rpc-textgen-1','task_id','textgen-task-1','trace_id','textgen-trace-1',
 'owner_id','owner-1','billing_account_id','payer-1','agent_id','agent-1','source_id','skill-1',
 'source_version',1,'sensitivity','internal','capability','text_generation',
 'provider_id','provider-x','model_id','model-x','model_version','v1',
 'usage_units',1,'usage_unit','request','input_tokens',7,'output_tokens',3,
 'cost_microunits',50,'cost_unit','USD','pricing_version','price-v1',
 'completed_at',clock_timestamp()::text,'payload_fingerprint',repeat('e',64)
));
reset role;
do $do$
declare v jsonb;
begin
 if not exists(select 1 from public.agent_model_usage_metering
   where idempotency_key='rpc-textgen-1' and input_tokens=7 and output_tokens=3) then
  raise exception 'text-generation token detail was not persisted';
 end if;
 v:=public.get_agent_model_usage_summary(clock_timestamp()-interval '1 day',clock_timestamp()+interval '1 second');
 if (v->'totals'->>'input_tokens')::bigint<>25 then raise exception 'summary input-token total after RPC incorrect'; end if;
 if (v->'totals'->>'output_tokens')::bigint<>7 then raise exception 'summary output-token total after RPC incorrect'; end if;
end $do$;
""")
        missing_tokens=psql("""
set role service_role;
select public.record_agent_model_usage_metering(jsonb_build_object(
 'idempotency_key','rpc-textgen-missing-tokens','task_id','textgen-task-2','trace_id','textgen-trace-2',
 'owner_id','owner-1','billing_account_id','payer-1','agent_id','agent-1','source_id','skill-1',
 'source_version',1,'sensitivity','internal','capability','text_generation',
 'provider_id','provider-x','model_id','model-x','model_version','v1',
 'usage_units',1,'usage_unit','request','cost_microunits',10,'cost_unit','USD',
 'pricing_version','price-v1','completed_at',clock_timestamp()::text,'payload_fingerprint',repeat('f',64)
));
reset role;
""",check=False)
        if missing_tokens.returncode==0:
            raise RuntimeError("text-generation metering accepted missing input/output token counts")

        psql(f"""
do $do$
begin
 if has_function_privilege('anon','public.get_agent_model_usage_summary(timestamptz,timestamptz)','EXECUTE') then raise exception 'anon can execute model usage summary'; end if;
 if has_function_privilege('authenticated','public.get_agent_model_usage_summary(timestamptz,timestamptz)','EXECUTE') then raise exception 'authenticated can execute model usage summary'; end if;
 if not has_function_privilege('service_role','public.get_agent_model_usage_summary(timestamptz,timestamptz)','EXECUTE') then raise exception 'service_role cannot execute model usage summary'; end if;
 if has_function_privilege('anon','public.get_agent_model_usage_summary(timestamptz,timestamptz)','EXECUTE') then raise exception 'anon can execute usage summary'; end if;
 if has_function_privilege('anon','public.record_agent_model_usage_metering(jsonb)','EXECUTE') then raise exception 'anon can write model usage metering'; end if;
 if has_function_privilege('authenticated','public.record_agent_model_usage_metering(jsonb)','EXECUTE') then raise exception 'authenticated can write model usage metering'; end if;
 if not has_function_privilege('service_role','public.record_agent_model_usage_metering(jsonb)','EXECUTE') then raise exception 'service_role cannot write model usage metering'; end if;
end $do$;
""")
        print("PASS: ENG-P09 PostgreSQL 17 model tariff/policy separation, immutable approval evidence, token-detail persistence, unit-safe usage summary, idempotency and service-only grants.")
    finally:
        run(["docker","rm","--force",NAME],check=False)


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: ENG-P09 model policy verification: {exc}",file=sys.stderr)
        raise SystemExit(1)
