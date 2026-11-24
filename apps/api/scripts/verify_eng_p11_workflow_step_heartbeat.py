"""ENG-P11 PostgreSQL 17 verifier for owner-scoped workflow lease heartbeats."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps/api/supabase/migrations/20261124071319_eng_p11_workflow_step_lease_heartbeat.sql"
CONTAINER = "allpha-p11-heartbeat-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
RUN = "33333333-3333-4333-8333-333333333333"
STEP = "44444444-4444-4444-8444-444444444444"
LEASE = "55555555-5555-4555-8555-555555555555"
OTHER_LEASE = "66666666-6666-4666-8666-666666666666"


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
        raise RuntimeError(f"Missing P11 migration: {MIGRATION}")
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
 status text not null,
 cancel_requested boolean not null default false,
 started_at timestamptz,
 created_at timestamptz not null default now(),
 max_runtime_seconds integer not null default 60
);
create table public.workflow_steps(
 id uuid primary key,
 run_id uuid not null references public.workflow_runs(id),
 owner_user_id uuid not null references auth.users(id),
 status text not null,
 lease_token uuid,
 lease_expires_at timestamptz,
 updated_at timestamptz not null default now()
);
""")
        psql(MIGRATION.read_text(encoding="utf-8"))
        psql(f"""
insert into public.workflow_runs(id,owner_user_id,status,cancel_requested,started_at,created_at,max_runtime_seconds)
values('{RUN}','{OWNER}','running',false,now()-interval '30 seconds',now()-interval '30 seconds',120);
insert into public.workflow_steps(id,run_id,owner_user_id,status,lease_token,lease_expires_at)
values('{STEP}','{RUN}','{OWNER}','running','{LEASE}',now()+interval '5 seconds');
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
select * from public.heartbeat_workflow_step('{RUN}','{OWNER}','{STEP}','{LEASE}',30);
reset role;
""")
        psql(f"""
do $assert$
declare
  expiry timestamptz;
  deadline timestamptz;
begin
 select lease_expires_at into expiry from public.workflow_steps where id='{STEP}';
 select started_at + make_interval(secs => max_runtime_seconds) into deadline
   from public.workflow_runs where id='{RUN}';
 if expiry <= now() then raise exception 'heartbeat did not extend the active lease'; end if;
 if expiry > deadline then raise exception 'heartbeat extended lease beyond workflow deadline'; end if;
end
$assert$;
""")
        # Wrong token, wrong owner, expired lease, cancelled run and expired run cannot be revived.
        psql(f"""
insert into public.workflow_runs(id,owner_user_id,status,cancel_requested,started_at,created_at,max_runtime_seconds)
values
 ('77777777-7777-4777-8777-777777777777','{OWNER}','running',true,now(),now(),120),
 ('88888888-8888-4888-8888-888888888888','{OWNER}','running',false,now()-interval '5 minutes',now()-interval '5 minutes',60);
insert into public.workflow_steps(id,run_id,owner_user_id,status,lease_token,lease_expires_at)
values
 ('99999999-9999-4999-8999-999999999999','{RUN}','{OWNER}','running','{LEASE}',now()+interval '5 seconds'),
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','{RUN}','{OWNER}','running','{LEASE}',now()-interval '1 second'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','77777777-7777-4777-8777-777777777777','{OWNER}','running','{LEASE}',now()+interval '5 seconds'),
 ('cccccccc-cccc-4ccc-8ccc-cccccccccccc','88888888-8888-4888-8888-888888888888','{OWNER}','running','{LEASE}',now()+interval '5 seconds');
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
do $checks$
declare n integer;
begin
 select count(*) into n from public.heartbeat_workflow_step('{RUN}','{OWNER}','99999999-9999-4999-8999-999999999999','{OTHER_LEASE}',30);
 if n<>0 then raise exception 'wrong lease token renewed a workflow step'; end if;
 select count(*) into n from public.heartbeat_workflow_step('{RUN}','{OTHER}','{STEP}','{LEASE}',30);
 if n<>0 then raise exception 'wrong owner renewed a workflow step'; end if;
 select count(*) into n from public.heartbeat_workflow_step('{RUN}','{OWNER}','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','{LEASE}',30);
 if n<>0 then raise exception 'expired lease was revived'; end if;
 select count(*) into n from public.heartbeat_workflow_step('77777777-7777-4777-8777-777777777777','{OWNER}','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','{LEASE}',30);
 if n<>0 then raise exception 'cancelled run lease was renewed'; end if;
 select count(*) into n from public.heartbeat_workflow_step('88888888-8888-4888-8888-888888888888','{OWNER}','cccccccc-cccc-4ccc-8ccc-cccccccccccc','{LEASE}',30);
 if n<>0 then raise exception 'expired run lease was renewed'; end if;
end
$checks$;
reset role;
""")
        psql("""
do $privileges$
begin
 if not has_function_privilege('anon','public.heartbeat_workflow_step(uuid,uuid,uuid,uuid,integer)','EXECUTE')
    and not has_function_privilege('authenticated','public.heartbeat_workflow_step(uuid,uuid,uuid,uuid,integer)','EXECUTE')
    and has_function_privilege('service_role','public.heartbeat_workflow_step(uuid,uuid,uuid,uuid,integer)','EXECUTE') then
   return;
 end if;
 raise exception 'workflow heartbeat function grants are not least-privilege';
end
$privileges$;
""")
        expect_denied(f"""
set role authenticated;
select * from public.heartbeat_workflow_step('{RUN}','{OWNER}','{STEP}','{LEASE}',30);
""", "permission denied")
        expect_denied(f"""
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
select * from public.heartbeat_workflow_step('{RUN}','{OWNER}','{STEP}','{LEASE}',121);
""", "workflow lease outside allowed bounds")
        print("PASS: ENG-P11 PostgreSQL 17 heartbeat verifier proves lease extension, owner/token/run-state fencing, run-deadline cap and service_role-only execution.")
    finally:
        run(["docker", "rm", "--force", CONTAINER], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: ENG-P11 workflow lease heartbeat verification: {exc}", file=sys.stderr)
        raise SystemExit(1)
