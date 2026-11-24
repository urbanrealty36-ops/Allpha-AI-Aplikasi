"""ENG-P11 PostgreSQL 17 verifier for durable workflow approval/resume/reject/cancel/timeout."""
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
    result = run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        sql,
        check=False,
    )
    if check and result.returncode:
        logs = run(["docker", "logs", CONTAINER], check=False)
        raise RuntimeError(
            result.stdout + "\n" + result.stderr
            + "\nPostgreSQL container logs:\n" + logs.stdout + logs.stderr
        )
    return result


def wait_for_postgres() -> None:
    """Wait for the final post-init server, not the entrypoint's temporary init server."""
    for _ in range(90):
        logs = run(["docker", "logs", CONTAINER], check=False)
        output = logs.stdout + logs.stderr
        initialized = "PostgreSQL init process complete; ready for start up." in output
        if initialized:
            ready = run(
                ["docker", "exec", CONTAINER, "pg_isready", "-U", "postgres", "-d", "postgres"],
                check=False,
            )
            if ready.returncode == 0:
                first = run(
                    ["docker", "exec", CONTAINER, "psql", "-X", "-A", "-t", "-U", "postgres", "-d", "postgres", "-c", "select pg_postmaster_start_time()"],
                    check=False,
                )
                time.sleep(1)
                second = run(
                    ["docker", "exec", CONTAINER, "psql", "-X", "-A", "-t", "-U", "postgres", "-d", "postgres", "-c", "select pg_postmaster_start_time()"],
                    check=False,
                )
                if (
                    first.returncode == 0
                    and second.returncode == 0
                    and first.stdout.strip()
                    and first.stdout.strip() == second.stdout.strip()
                ):
                    return
        time.sleep(1)
    logs = run(["docker", "logs", CONTAINER], check=False)
    raise RuntimeError(
        "PostgreSQL 17 final post-init server did not remain ready.\n"
        + logs.stdout + logs.stderr
    )


def expect_denied(sql: str, expected: str) -> None:
    result = psql(sql, check=False)
    output = result.stdout + result.stderr
    if result.returncode == 0 or expected not in output:
        raise RuntimeError(f"Expected {expected!r}; got rc={result.returncode}: {output}")


def main() -> None:
    if not MIGRATION.is_file():
        raise RuntimeError(f"Missing P11 approval migration: {MIGRATION}")
    run(["docker", "run", "-d", "--rm", "--name", CONTAINER, "-e", "POSTGRES_PASSWORD=ci-only", "postgres:17-alpine"])
    try:
        wait_for_postgres()

        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create function auth.role() returns text language sql stable as $role$
 select nullif(current_setting('request.jwt.claim.role',true),'')
$role$;
grant usage on schema auth to public;
grant execute on function auth.role() to public;
create table auth.users(id uuid primary key);
insert into auth.users(id) values
 ('11111111-1111-4111-8111-111111111111'),
 ('22222222-2222-4222-8222-222222222222');

create table public.workflow_runs(
 id uuid primary key,
 owner_user_id uuid not null references auth.users(id),
 status text not null constraint workflow_runs_status_check
   check(status in ('created','queued','running','succeeded','failed','cancelled','timed_out')),
 cancel_requested boolean not null default false,
 started_at timestamptz,
 created_at timestamptz not null default now(),
 max_runtime_seconds integer not null default 60,
 completed_at timestamptz,
 updated_at timestamptz not null default now(),
 run_version bigint not null default 1
);
create table public.workflow_steps(
 id uuid primary key,
 run_id uuid not null references public.workflow_runs(id) on delete cascade,
 owner_user_id uuid not null references auth.users(id),
 node_key text not null,
 node_kind text not null constraint workflow_steps_node_kind_check
   check(node_kind in ('input','constant','pass_through','concat','merge')),
 status text not null constraint workflow_steps_status_check
   check(status in ('pending','running','retrying','succeeded','failed','cancelled','skipped')),
 attempts integer not null default 1,
 max_attempts integer not null default 3,
 lease_token uuid,
 lease_expires_at timestamptz,
 checkpoint jsonb,
 output_payload jsonb,
 error_code text,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 completed_at timestamptz
);
create table public.workflow_run_events(
 id bigint generated always as identity primary key,
 run_id uuid not null references public.workflow_runs(id) on delete cascade,
 owner_user_id uuid not null references auth.users(id),
 sequence bigint not null,
 event_type text not null,
 step_key text,
 details jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 unique(run_id,sequence)
);
grant select on public.workflow_runs, public.workflow_steps, public.workflow_run_events to service_role;
""")
        psql(MIGRATION.read_text(encoding="utf-8"))
        psql("update public.workflow_steps set node_kind='approval';")

        psql("""
insert into public.workflow_runs(id,owner_user_id,status,started_at,created_at,max_runtime_seconds)
values
 ('33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111','running',now(),now(),120),
 ('44444444-4444-4444-8444-444444444444','11111111-1111-4111-8111-111111111111','running',now(),now(),120),
 ('55555555-5555-4555-8555-555555555555','11111111-1111-4111-8111-111111111111','running',now(),now(),120),
 ('66666666-6666-4666-8666-666666666666','11111111-1111-4111-8111-111111111111','running',now()-interval '30 seconds',now()-interval '30 seconds',1);
insert into public.workflow_steps(id,run_id,owner_user_id,node_key,node_kind,status,attempts,max_attempts,lease_token,lease_expires_at)
values
 ('77777777-7777-4777-8777-777777777777','33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111','approve','merge','running',1,3,'88888888-8888-4888-8888-888888888888',now()+interval '60 seconds'),
 ('99999999-9999-4999-8999-999999999999','44444444-4444-4444-8444-444444444444','11111111-1111-4111-8111-111111111111','reject','merge','running',1,3,'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',now()+interval '60 seconds'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','55555555-5555-4555-8555-555555555555','11111111-1111-4111-8111-111111111111','cancel','merge','running',1,3,'cccccccc-cccc-4ccc-8ccc-cccccccccccc',now()+interval '60 seconds'),
 ('dddddddd-dddd-4ddd-8ddd-dddddddddddd','66666666-6666-4666-8666-666666666666','11111111-1111-4111-8111-111111111111','timeout','merge','running',1,3,'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',now()+interval '60 seconds');

set role service_role;
select set_config('request.jwt.claim.role','service_role',false);

-- A requested approval is durable, owner-scoped and pauses both step and run.
select * from public.finalize_workflow_step(
 '33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111',
 '77777777-7777-4777-8777-777777777777','88888888-8888-4888-8888-888888888888',
 'waiting_for_approval',null,'APPROVAL_REQUIRED',
 jsonb_build_object('approval_message','Approve publish','approval_context',jsonb_build_object('artifact_id','artifact-1'))
);
do $approval$
declare v_id uuid; n integer;
begin
 select (checkpoint->>'approval_id')::uuid into v_id
 from public.workflow_steps where id='77777777-7777-4777-8777-777777777777';
 if v_id is null then raise exception 'approval ID was not checkpointed'; end if;
 if (select status from public.workflow_runs where id='33333333-3333-4333-8333-333333333333')<>'waiting_for_approval' then
   raise exception 'run did not pause for approval';
 end if;
 if (select status from public.workflow_steps where id='77777777-7777-4777-8777-777777777777')<>'waiting_for_approval' then
   raise exception 'step did not pause for approval';
 end if;
 if (select status from public.workflow_step_approvals where id=v_id)<>'pending' then
   raise exception 'approval record was not persisted pending';
 end if;
 select count(*) into n from public.approve_workflow_step(
   '33333333-3333-4333-8333-333333333333','22222222-2222-4222-8222-222222222222',
   '77777777-7777-4777-8777-777777777777',v_id,'wrong owner');
 if n<>0 then raise exception 'non-owner approved workflow step'; end if;
 select count(*) into n from public.approve_workflow_step(
   '33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111',
   '77777777-7777-4777-8777-777777777777',v_id,'Reviewed');
 if n<>1 then raise exception 'owner approval did not resume exactly one step'; end if;
 if (select status from public.workflow_runs where id='33333333-3333-4333-8333-333333333333')<>'queued' then
   raise exception 'approved run did not return to queue';
 end if;
 if (select status from public.workflow_steps where id='77777777-7777-4777-8777-777777777777')<>'pending' then
   raise exception 'approved step did not return to pending';
 end if;
 if (select checkpoint->>'approval_status' from public.workflow_steps where id='77777777-7777-4777-8777-777777777777')<>'approved' then
   raise exception 'approval checkpoint was not persisted';
 end if;
end
$approval$;

-- Rejection is terminal and records a durable owner decision.
select * from public.finalize_workflow_step(
 '44444444-4444-4444-8444-444444444444','11111111-1111-4111-8111-111111111111',
 '99999999-9999-4999-8999-999999999999','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'waiting_for_approval',null,'APPROVAL_REQUIRED',
 jsonb_build_object('approval_message','Approve deletion','approval_context','{}'::jsonb)
);
do $reject$
declare v_id uuid; n integer;
begin
 select (checkpoint->>'approval_id')::uuid into v_id from public.workflow_steps
  where id='99999999-9999-4999-8999-999999999999';
 select count(*) into n from public.reject_workflow_step(
   '44444444-4444-4444-8444-444444444444','11111111-1111-4111-8111-111111111111',
   '99999999-9999-4999-8999-999999999999',v_id,'Rejected');
 if n<>1 then raise exception 'owner rejection did not affect one step'; end if;
 if (select status from public.workflow_runs where id='44444444-4444-4444-8444-444444444444')<>'failed' then
   raise exception 'rejected workflow did not fail';
 end if;
 if (select status from public.workflow_step_approvals where id=v_id)<>'rejected' then
   raise exception 'rejection decision was not persisted';
 end if;
end
$reject$;

-- Cancellation and timeout both cancel pending approvals and clear step leases.
select * from public.finalize_workflow_step(
 '55555555-5555-4555-8555-555555555555','11111111-1111-4111-8111-111111111111',
 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','cccccccc-cccc-4ccc-8ccc-cccccccccccc',
 'waiting_for_approval',null,'APPROVAL_REQUIRED',
 jsonb_build_object('approval_message','Approve cancellation','approval_context','{}'::jsonb)
);
select * from public.cancel_workflow_run(
 '55555555-5555-4555-8555-555555555555','11111111-1111-4111-8111-111111111111'
);
do $cancel$
declare v_id uuid;
begin
 select (checkpoint->>'approval_id')::uuid into v_id from public.workflow_steps
  where id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
 if (select status from public.workflow_step_approvals where id=v_id)<>'cancelled' then
   raise exception 'run cancellation did not cancel pending approval';
 end if;
 if (select status from public.workflow_steps where id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')<>'cancelled' then
   raise exception 'run cancellation did not cancel waiting step';
 end if;
end
$cancel$;

select * from public.finalize_workflow_step(
 '66666666-6666-4666-8666-666666666666','11111111-1111-4111-8111-111111111111',
 'dddddddd-dddd-4ddd-8ddd-dddddddddddd','eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
 'waiting_for_approval',null,'APPROVAL_REQUIRED',
 jsonb_build_object('approval_message','Approve timeout','approval_context','{}'::jsonb)
);
select * from public.timeout_workflow_run(
 '66666666-6666-4666-8666-666666666666','11111111-1111-4111-8111-111111111111'
);
do $timeout$
declare v_id uuid;
begin
 select (checkpoint->>'approval_id')::uuid into v_id from public.workflow_steps
  where id='dddddddd-dddd-4ddd-8ddd-dddddddddddd';
 if (select status from public.workflow_runs where id='66666666-6666-4666-8666-666666666666')<>'timed_out' then
   raise exception 'workflow deadline did not time out run';
 end if;
 if (select status from public.workflow_step_approvals where id=v_id)<>'cancelled' then
   raise exception 'workflow timeout did not cancel pending approval';
 end if;
end
$timeout$;

-- Least privilege: all approval lifecycle functions are service_role-only.
do $privileges$
begin
 if has_function_privilege('anon','public.approve_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or has_function_privilege('authenticated','public.approve_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or not has_function_privilege('service_role','public.approve_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or has_function_privilege('authenticated','public.reject_workflow_step(uuid,uuid,uuid,uuid,text)','EXECUTE')
    or has_function_privilege('authenticated','public.finalize_workflow_step(uuid,uuid,uuid,uuid,text,jsonb,text,jsonb)','EXECUTE')
 then raise exception 'workflow approval function grants are not least-privilege'; end if;
 if not (select c.relrowsecurity from pg_class c where c.oid='public.workflow_step_approvals'::regclass) then
   raise exception 'workflow approval RLS is not enabled';
 end if;
 if has_table_privilege('authenticated','public.workflow_step_approvals','SELECT')
    or not has_table_privilege('service_role','public.workflow_step_approvals','SELECT') then
   raise exception 'workflow approval table grants are not least-privilege';
 end if;
end
$privileges$;
reset role;
""")
        expect_denied(
            "set role authenticated; select * from public.approve_workflow_step("
            "'33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111',"
            "'77777777-7777-4777-8777-777777777777','00000000-0000-4000-8000-000000000000',null);",
            "permission denied",
        )
        print("PASS: ENG-P11 PostgreSQL 17 approval verifier proves approval checkpoint persistence, owner-only resume/reject, cancellation, timeout and least-privilege grants.")
    finally:
        run(["docker", "rm", "--force", CONTAINER], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: ENG-P11 workflow approval lifecycle verification: {exc}", file=sys.stderr)
        raise SystemExit(1)
