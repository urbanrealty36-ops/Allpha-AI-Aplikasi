"""ENG-P11 PostgreSQL 17 verifier for durable workflow approval lifecycle."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps/api/supabase/migrations/20261124082000_eng_p11_workflow_approval_lifecycle.sql"
CONTAINER = "allpha-p11-approval-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"


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


def main() -> None:
    if not MIGRATION.is_file():
        raise RuntimeError(f"Missing P11 approval migration: {MIGRATION}")
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
create extension if not exists pgcrypto;
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create table auth.users(id uuid primary key);
insert into auth.users(id) values
 ('11111111-1111-4111-8111-111111111111'),
 ('22222222-2222-4222-8222-222222222222');

create table public.workflow_runs(
 id uuid primary key,
 owner_user_id uuid not null references auth.users(id),
 status text not null check(status in ('queued','running','succeeded','failed','cancelled','timed_out')),
 cancel_requested boolean not null default false,
 started_at timestamptz,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 completed_at timestamptz,
 max_runtime_seconds integer not null default 60,
 run_version integer not null default 1
);
create table public.workflow_steps(
 id uuid primary key,
 run_id uuid not null references public.workflow_runs(id),
 owner_user_id uuid not null references auth.users(id),
 node_key text not null,
 node_kind text not null check(node_kind in ('input','constant','pass_through','concat','merge')),
 status text not null check(status in ('pending','running','retrying','succeeded','failed','cancelled','skipped')),
 attempts integer not null default 0,
 max_attempts integer not null default 3,
 lease_token uuid,
 lease_expires_at timestamptz,
 output_payload jsonb,
 checkpoint jsonb,
 error_code text,
 completed_at timestamptz,
 updated_at timestamptz not null default now()
);
create table public.workflow_run_events(
 id bigserial primary key,
 run_id uuid not null references public.workflow_runs(id),
 owner_user_id uuid not null references auth.users(id),
 sequence bigint not null,
 event_type text not null,
 step_key text,
 details jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 unique(run_id,sequence)
);
""")
        psql(MIGRATION.read_text(encoding="utf-8"))

        psql(f"""
insert into public.workflow_runs(id,owner_user_id,status,started_at,created_at,max_runtime_seconds)
values
 ('33333333-3333-4333-8333-333333333333','{OWNER}','running',now(),now(),600),
 ('44444444-4444-4444-8444-444444444444','{OWNER}','running',now(),now(),600),
 ('55555555-5555-4555-8555-555555555555','{OWNER}','running',now(),now(),600),
 ('66666666-6666-4666-8666-666666666666','{OWNER}','running',now()-interval '2 minutes',now()-interval '2 minutes',1);
insert into public.workflow_steps(id,run_id,owner_user_id,node_key,node_kind,status,attempts,max_attempts,lease_token,lease_expires_at)
values
 ('33333333-3333-4333-8333-333333333334','33333333-3333-4333-8333-333333333333','{OWNER}','approve','approval','running',1,3,'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',now()+interval '60 seconds'),
 ('44444444-4444-4444-8444-444444444445','44444444-4444-4444-8444-444444444444','{OWNER}','reject','approval','running',1,3,'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',now()+interval '60 seconds'),
 ('55555555-5555-4555-8555-555555555556','55555555-5555-4555-8555-555555555555','{OWNER}','cancel','approval','running',1,3,'cccccccc-cccc-4ccc-8ccc-cccccccccccc',now()+interval '60 seconds'),
 ('66666666-6666-4666-8666-666666666667','66666666-6666-4666-8666-666666666666','{OWNER}','timeout','approval','running',1,3,'dddddddd-dddd-4ddd-8ddd-dddddddddddd',now()+interval '60 seconds');
insert into public.workflow_runs(id,owner_user_id,status,started_at,created_at,max_runtime_seconds)
values ('77777777-7777-4777-8777-777777777777','{OWNER}','queued',now(),now(),600);
insert into public.workflow_steps(id,run_id,owner_user_id,node_key,node_kind,status)
values ('77777777-7777-4777-8777-777777777778','77777777-7777-4777-8777-777777777777','{OWNER}','agent-task','agent_task','pending');

set role service_role;
select * from public.finalize_workflow_step(
 '33333333-3333-4333-8333-333333333333','{OWNER}','33333333-3333-4333-8333-333333333334',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','waiting_for_approval',null,'APPROVAL_REQUIRED',
 '{{"node_key":"approve","approval_message":"Confirm external action","approval_context":{{"action":"publish"}}}}'::jsonb
);
select * from public.finalize_workflow_step(
 '44444444-4444-4444-8444-444444444444','{OWNER}','44444444-4444-4444-8444-444444444445',
 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','waiting_for_approval',null,'APPROVAL_REQUIRED',
 '{{"node_key":"reject","approval_message":"Confirm external action","approval_context":{{"action":"publish"}}}}'::jsonb
);
select * from public.finalize_workflow_step(
 '55555555-5555-4555-8555-555555555555','{OWNER}','55555555-5555-4555-8555-555555555556',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc','waiting_for_approval',null,'APPROVAL_REQUIRED',
 '{{"node_key":"cancel","approval_message":"Confirm external action","approval_context":{{"action":"publish"}}}}'::jsonb
);
select * from public.finalize_workflow_step(
 '66666666-6666-4666-8666-666666666666','{OWNER}','66666666-6666-4666-8666-666666666667',
 'dddddddd-dddd-4ddd-8ddd-dddddddddddd','waiting_for_approval',null,'APPROVAL_REQUIRED',
 '{{"node_key":"timeout","approval_message":"Confirm external action","approval_context":{{"action":"publish"}}}}'::jsonb
);
reset role;
""")

        psql(f"""
do $assert$
declare
 v_approval uuid;
 v_status text;
begin
 if (select status from public.workflow_runs where id='33333333-3333-4333-8333-333333333333')<>'waiting_for_approval' then
  raise exception 'workflow run did not pause for approval';
 end if;
 if (select status from public.workflow_steps where id='33333333-3333-4333-8333-333333333334')<>'waiting_for_approval' then
  raise exception 'workflow step did not persist approval state';
 end if;
 select id into v_approval from public.workflow_step_approvals where step_id='33333333-3333-4333-8333-333333333334' and status='pending';
 if v_approval is null then raise exception 'pending workflow approval row was not persisted'; end if;
 if (select checkpoint->>'approval_id' from public.workflow_steps where id='33333333-3333-4333-8333-333333333334')<>v_approval::text then
  raise exception 'approval checkpoint does not link to durable approval row';
 end if;
 if (select node_kind from public.workflow_steps where id='77777777-7777-4777-8777-777777777778')<>'agent_task' then
  raise exception 'agent_task node kind constraint was not extended';
 end if;
end
$assert$;
""")

        psql(f"""
set role service_role;
do $owner$
declare v_approval uuid; v_count integer;
begin
 select id into v_approval from public.workflow_step_approvals where step_id='33333333-3333-4333-8333-333333333334';
 select count(*) into v_count from public.approve_workflow_step(
  '33333333-3333-4333-8333-333333333333','{OTHER}','33333333-3333-4333-8333-333333333334',v_approval,'not owner');
 if v_count<>0 then raise exception 'non-owner approved workflow step'; end if;
 select count(*) into v_count from public.approve_workflow_step(
  '33333333-3333-4333-8333-333333333333','{OWNER}','33333333-3333-4333-8333-333333333334',v_approval,'approved by owner');
 if v_count<>1 then raise exception 'owner could not approve workflow step'; end if;
end
$owner$;
reset role;
""")

        psql("""
do $resume$
declare v_status text; v_approval_status text;
begin
 select status into v_status from public.workflow_runs where id='33333333-3333-4333-8333-333333333333';
 if v_status<>'queued' then raise exception 'approved workflow did not return to queued state'; end if;
 select status into v_status from public.workflow_steps where id='33333333-3333-4333-8333-333333333334';
 if v_status<>'pending' then raise exception 'approved workflow step was not re-queued'; end if;
 select status into v_approval_status from public.workflow_step_approvals where step_id='33333333-3333-4333-8333-333333333334';
 if v_approval_status<>'approved' then raise exception 'approval decision was not persisted'; end if;
end
$resume$;
""")

        psql(f"""
set role service_role;
select * from public.reject_workflow_step(
 '44444444-4444-4444-8444-444444444444','{OWNER}','44444444-4444-4444-8444-444444444445',
 (select id from public.workflow_step_approvals where step_id='44444444-4444-4444-8444-444444444445'),
 'owner rejected'
);
select * from public.cancel_workflow_run('55555555-5555-4555-8555-555555555555','{OWNER}');
select * from public.timeout_workflow_run('66666666-6666-4666-8666-666666666666','{OWNER}');
reset role;
""")
        psql("""
do $terminal$
begin
 if (select status from public.workflow_runs where id='44444444-4444-4444-8444-444444444444')<>'failed' then
  raise exception 'rejected workflow did not fail';
 end if;
 if (select status from public.workflow_step_approvals where step_id='44444444-4444-4444-8444-444444444445')<>'rejected' then
  raise exception 'rejected approval decision was not persisted';
 end if;
 if (select status from public.workflow_runs where id='55555555-5555-4555-8555-555555555555')<>'cancelled' then
  raise exception 'workflow cancellation did not complete';
 end if;
 if (select status from public.workflow_step_approvals where step_id='55555555-5555-4555-8555-555555555556')<>'cancelled' then
  raise exception 'cancellation did not close pending approval';
 end if;
 if (select status from public.workflow_runs where id='66666666-6666-4666-8666-666666666666')<>'timed_out' then
  raise exception 'workflow timeout did not complete';
 end if;
 if (select status from public.workflow_step_approvals where step_id='66666666-6666-4666-8666-666666666667')<>'cancelled' then
  raise exception 'timeout did not close pending approval';
 end if;
end
$terminal$;
""")

        psql("""
do $privileges$
begin
 if has_function_privilege('anon','public.approve_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or has_function_privilege('authenticated','public.approve_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or not has_function_privilege('service_role','public.approve_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or has_function_privilege('anon','public.reject_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or has_function_privilege('authenticated','public.reject_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or not has_function_privilege('service_role','public.reject_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE') then
  raise exception 'workflow approval RPC grants are not least-privilege';
 end if;
 if has_table_privilege('anon','public.workflow_step_approvals','SELECT')
    or has_table_privilege('authenticated','public.workflow_step_approvals','SELECT')
    or not has_table_privilege('service_role','public.workflow_step_approvals','SELECT') then
  raise exception 'workflow approval table grants are not least-privilege';
 end if;
end
$privileges$;
""")
        print("PASS: ENG-P11 PostgreSQL 17 verifier proves approval pause, owner-only approve/reject, resume, cancel, timeout, agent_task node support and service_role-only RPC/table access.")
    finally:
        run(["docker", "rm", "--force", CONTAINER], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: ENG-P11 workflow approval verification: {exc}", file=sys.stderr)
        raise SystemExit(1)
