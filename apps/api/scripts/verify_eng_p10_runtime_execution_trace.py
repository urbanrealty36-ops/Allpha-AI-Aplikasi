"""ENG-P10 PostgreSQL 17 verifier for append-only, owner-scoped, lease-fenced execution traces."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps/api/supabase/source-only-migrations/20261116120000_eng_p10_agent_runtime_execution_trace.sql"
CONTAINER = "allpha-p10-trace-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER_OWNER = "22222222-2222-4222-8222-222222222222"
TASK = "33333333-3333-4333-8333-333333333333"
LEASE = "44444444-4444-4444-8444-444444444444"
STALE_LEASE = "55555555-5555-4555-8555-555555555555"


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


def expect_denied(sql: str, expected: str) -> None:
    result = psql(sql, check=False)
    output = result.stdout + result.stderr
    if result.returncode == 0 or expected not in output:
        raise RuntimeError(f"Expected {expected!r}; got rc={result.returncode}: {output}")


def main() -> None:
    if not MIGRATION.is_file():
        raise RuntimeError(f"Missing source-only migration: {MIGRATION}")
    run(["docker", "run", "-d", "--rm", "--name", CONTAINER, "-e", "POSTGRES_PASSWORD=ci-only", "postgres:17-alpine"])
    try:
        ready = False
        for _ in range(60):
            probe = run(["docker", "exec", CONTAINER, "psql", "-X", "-A", "-t", "-U", "postgres", "-d", "postgres", "-c", "select 1"], check=False)
            if probe.returncode == 0:
                stable = run(["docker", "exec", CONTAINER, "psql", "-X", "-A", "-t", "-U", "postgres", "-d", "postgres", "-c", "select 1"], check=False)
                if stable.returncode == 0:
                    ready = True
                    break
            time.sleep(1)
        if not ready:
            raise RuntimeError("PostgreSQL 17 did not reach stable SQL readiness")

        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create function auth.uid() returns uuid language sql stable as $uid$
 select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$uid$;
create function auth.role() returns text language sql stable as $role$
 select nullif(current_setting('request.jwt.claim.role',true),'')
$role$;
grant usage on schema auth to public;
grant execute on function auth.uid(),auth.role() to public;
create table auth.users(id uuid primary key);
insert into auth.users(id) values ('11111111-1111-4111-8111-111111111111'),('22222222-2222-4222-8222-222222222222');
create table public.agent_runtime_tasks(
 id uuid primary key,
 owner_user_id uuid not null references auth.users(id),
 state text not null,
 execution_lease_token uuid,
 lease_expires_at timestamptz,
 task_version integer not null,
 trace_id text not null,
 execution_event_seq bigint not null default 0,
 updated_at timestamptz not null default now()
);
""")
        psql(MIGRATION.read_text(encoding="utf-8"))
        psql(f"""
insert into public.agent_runtime_tasks(
 id,owner_user_id,state,execution_lease_token,lease_expires_at,task_version,trace_id
) values(
 '{TASK}','{OWNER}','executing','{LEASE}',now()+interval '5 minutes',7,'trace-p10-0001'
);
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
select * from public.append_agent_runtime_execution_event(
 '{TASK}','{OWNER}','{LEASE}',7,'state_transition','executing','tool_plan',
 '{{"reason_code":"approved","tool_key":"text.normalize","attempt":1}}'::jsonb
);
reset role;
""")
        psql(f"""
do $assert$
begin
 if (select count(*) from public.agent_runtime_execution_events where task_id='{TASK}' and owner_user_id='{OWNER}' and sequence=1)<>1 then
  raise exception 'first owner-scoped trace event missing';
 end if;
 if (select execution_event_seq from public.agent_runtime_tasks where id='{TASK}')<>1 then
  raise exception 'task execution event sequence not advanced';
 end if;
 if (select trace_id from public.agent_runtime_execution_events where task_id='{TASK}' and sequence=1)<>'trace-p10-0001' then
  raise exception 'trace id was not preserved';
 end if;
end
$assert$;
""")
        expect_denied(f"""
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
select * from public.append_agent_runtime_execution_event(
 '{TASK}','{OWNER}','{LEASE}',7,'state_transition','executing','tool_plan',
 '{{"prompt":"private owner prompt"}}'::jsonb
);
""", "runtime_execution_event_detail_key_denied")
        expect_denied(f"""
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
select * from public.append_agent_runtime_execution_event(
 '{TASK}','{OWNER}','{STALE_LEASE}',7,'state_transition','executing','tool_plan','{{}}'::jsonb
);
""", "runtime_execution_event_stale_lease")
        expect_denied(f"""
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
select * from public.append_agent_runtime_execution_event(
 '{TASK}','{OTHER_OWNER}','{LEASE}',7,'state_transition','executing','tool_plan','{{}}'::jsonb
);
""", "runtime_execution_event_stale_lease")
        expect_denied(f"""
set role anon;
select count(*) from public.agent_runtime_execution_events;
""", "permission denied")
        expect_denied(f"""
set role authenticated;
select public.append_agent_runtime_execution_event(
 '{TASK}','{OWNER}','{LEASE}',7,'state_transition','executing','tool_plan','{{}}'::jsonb
);
""", "permission denied")
        expect_denied(f"""
update public.agent_runtime_execution_events set step_key='tampered' where task_id='{TASK}';
""", "agent_runtime_execution_events_are_append_only")
        expect_denied(f"""
delete from public.agent_runtime_execution_events where task_id='{TASK}';
""", "agent_runtime_execution_events_are_append_only")
        psql(f"""
update public.agent_runtime_tasks
 set lease_expires_at=now()-interval '1 second'
 where id='{TASK}' and owner_user_id='{OWNER}';
""")
        expect_denied(f"""
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
select * from public.append_agent_runtime_execution_event(
 '{TASK}','{OWNER}','{LEASE}',7,'state_transition','executing','tool_plan','{{}}'::jsonb
);
""", "runtime_execution_event_stale_lease")
        psql(f"""
select count(*) from public.agent_runtime_execution_events where task_id='{TASK}';
select execution_event_seq from public.agent_runtime_tasks where id='{TASK}';
""")
        print("PASS: ENG-P10 PostgreSQL 17 trace verifier proves owner-scoped append-only persistence, lease/token/version fencing, detail allowlist, sequence advancement, and client-role denial.")
    finally:
        run(["docker", "rm", "--force", CONTAINER], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: ENG-P10 execution trace verification: {exc}", file=sys.stderr)
        raise SystemExit(1)
