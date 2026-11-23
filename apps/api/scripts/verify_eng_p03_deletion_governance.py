"""ENG-P03 PostgreSQL 17 verification for legal-hold reconciliation and fail-closed deletion policy gates."""
from __future__ import annotations
from pathlib import Path
import subprocess,sys,time,uuid

ROOT=Path(__file__).resolve().parents[3]
MIGRATION=ROOT/"apps/api/supabase/migrations/20261123192200_eng_p03_deletion_legal_hold_governance_worker.sql"
CONTAINER="allpha-p03-deletion-"+uuid.uuid4().hex[:8]
A="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
C="cccccccc-cccc-4ccc-8ccc-cccccccccccc"
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
create extension if not exists pgcrypto;
create table auth.users(id uuid primary key);
create function auth.role() returns text language sql stable as $$
 select nullif(current_setting('request.jwt.claim.role',true),'')
$$;
grant usage on schema auth to public;
grant execute on function auth.role() to public;
create table public.account_deletion_requests(
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id),
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
 created_by uuid not null references auth.users(id),
 created_at timestamptz not null default now(),
 released_by uuid references auth.users(id),
 released_at timestamptz
);
create table public.account_lifecycle_events(
 id uuid primary key default gen_random_uuid(),
 request_id uuid references public.account_deletion_requests(id),
 export_job_id uuid,
 user_id uuid,
 subject_ref text not null,
 event_type text not null check(event_type in ('export_requested','export_started','export_completed','export_failed','deletion_requested','deletion_cancelled','deletion_scheduled','deletion_started','deletion_blocked','deletion_completed','deletion_failed')),
 metadata jsonb not null check(jsonb_typeof(metadata)='object'),
 recorded_at timestamptz not null default now()
);
""")
        psql(MIGRATION.read_text(encoding="utf-8"))
        psql(MIGRATION.read_text(encoding="utf-8")) # repeatable forward migration
        psql(f"""
insert into auth.users(id) values ('{A}'),('{B}'),('{C}');
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
  select * into v from public.evaluate_account_deletion_governance(100);
  if v.unblocked_count<>1 then raise exception 'released legal hold was not reconciled'; end if;
  if (select status from public.account_deletion_requests where subject_ref='{HOLD_A}')<>'awaiting_policy' then
    raise exception 'request did not return to policy gate after hold release';
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
        print("PASS: ENG-P03 legal hold block/release, policy-pending audit, RPC privilege and non-destructive fail-closed behavior.")
    finally:
        run(["docker","rm","--force",CONTAINER],check=False)

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print(f"FAIL: ENG-P03 deletion governance PostgreSQL 17 verification: {exc}",file=sys.stderr)
        raise SystemExit(1)
