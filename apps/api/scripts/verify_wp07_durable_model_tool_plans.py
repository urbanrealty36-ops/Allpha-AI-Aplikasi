"""WP-07 / ENG-P10 PostgreSQL 17 verifier for durable, owner-scoped tool-plan reservations."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps/api/supabase/source-only-migrations/20261116200000_wp07_durable_model_tool_plans.sql"
CONTAINER = "allpha-tool-plans-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER_OWNER = "22222222-2222-4222-8222-222222222222"
AGENT = "33333333-3333-4333-8333-333333333333"
SESSION = "44444444-4444-4444-8444-444444444444"
SKILL = "55555555-5555-4555-8555-555555555555"
TASK = "66666666-6666-4666-8666-666666666666"
PLAN = "77777777-7777-4777-8777-777777777777"


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
        "PostgreSQL 17 final post-init server did not remain ready.\\n"
        + logs.stdout + logs.stderr
    )


def main() -> None:
    if not MIGRATION.is_file():
        raise RuntimeError(f"Missing source-only migration: {MIGRATION}")
    run(["docker", "run", "-d", "--rm", "--name", CONTAINER, "-e", "POSTGRES_PASSWORD=ci-only", "postgres:17-alpine"])
    try:
        wait_for_postgres()

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
create table public.ai_agents(id uuid primary key, owner_user_id uuid not null references auth.users(id));
create table public.agent_runtime_sessions(
 id uuid primary key, owner_user_id uuid not null references auth.users(id),
 unique(id,owner_user_id)
);
create table public.agent_skills(
 id uuid primary key, agent_id uuid not null references public.ai_agents(id),
 unique(id,agent_id)
);
create table public.agent_runtime_tasks(id uuid primary key);
insert into public.ai_agents(id,owner_user_id)
 values ('33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111');
insert into public.agent_runtime_sessions(id,owner_user_id)
 values ('44444444-4444-4444-8444-444444444444','11111111-1111-4111-8111-111111111111');
insert into public.agent_skills(id,agent_id)
 values ('55555555-5555-4555-8555-555555555555','33333333-3333-4333-8333-333333333333');
insert into public.agent_runtime_tasks(id) values ('66666666-6666-4666-8666-666666666666');
""")
        psql(MIGRATION.read_text(encoding="utf-8"))

        psql(f"""
set role service_role;
insert into public.agent_runtime_tool_plans(
 id,owner_user_id,agent_id,session_id,skill_id,agent_version,skill_version,
 idempotency_key,request_fingerprint,intent_sha256,trace_id,status
) values (
 '{PLAN}','{OWNER}','{AGENT}','{SESSION}','{SKILL}',2,3,
 'tool-plan-idempotency-01','{'a' * 64}','{'b' * 64}','trace-tool-plan-0001','planning'
);
reset role;
""")
        psql(f"""
do $assert$
declare v_expiry timestamptz; v_rls boolean;
begin
 select expires_at into v_expiry from public.agent_runtime_tool_plans where id='{PLAN}';
 if v_expiry < now()+interval '9 minutes' or v_expiry > now()+interval '11 minutes' then
  raise exception 'tool plan reservation expiry default is not bounded to ten minutes';
 end if;
 select c.relrowsecurity into v_rls from pg_class c
  where c.oid='public.agent_runtime_tool_plans'::regclass;
 if not v_rls then raise exception 'tool plan RLS is not enabled'; end if;
 if not has_table_privilege('service_role','public.agent_runtime_tool_plans','SELECT')
  or not has_table_privilege('service_role','public.agent_runtime_tool_plans','INSERT')
  or not has_table_privilege('service_role','public.agent_runtime_tool_plans','UPDATE') then
  raise exception 'service_role tool-plan privileges are incomplete';
 end if;
 if has_table_privilege('anon','public.agent_runtime_tool_plans','SELECT')
  or has_table_privilege('authenticated','public.agent_runtime_tool_plans','INSERT') then
  raise exception 'client role can access backend-only tool-plan reservations';
 end if;
 if exists(select 1 from information_schema.columns where table_schema='public'
   and table_name='agent_runtime_tool_plans' and column_name in ('intent','memory_context_text','knowledge_context_text')) then
  raise exception 'raw intent or private context text must not be persisted';
 end if;
end
$assert$;
""")

        expect_denied(f"""
set role service_role;
insert into public.agent_runtime_tool_plans(
 owner_user_id,agent_id,session_id,skill_id,agent_version,skill_version,
 idempotency_key,request_fingerprint,intent_sha256,trace_id
) values ('{OWNER}','{AGENT}','{SESSION}','{SKILL}',2,3,
 'tool-plan-idempotency-01','{'c' * 64}','{'d' * 64}','trace-duplicate-0001');
""", "duplicate key")

        expect_denied(f"""
set role service_role;
insert into public.agent_runtime_tool_plans(
 owner_user_id,agent_id,session_id,skill_id,agent_version,skill_version,
 idempotency_key,request_fingerprint,intent_sha256,trace_id
) values ('{OWNER}','{AGENT}','{SESSION}','{SKILL}',2,3,
 'tool-plan-invalid-digest','invalid','{'d' * 64}','trace-invalid-0001');
""", "violates check constraint")

        expect_denied(f"""
set role service_role;
insert into public.agent_runtime_tool_plans(
 owner_user_id,agent_id,session_id,skill_id,agent_version,skill_version,
 idempotency_key,request_fingerprint,intent_sha256,trace_id
) values ('{OTHER_OWNER}','{AGENT}','{SESSION}','{SKILL}',2,3,
 'tool-plan-cross-owner','{'e' * 64}','{'f' * 64}','trace-cross-owner-0001');
""", "violates foreign key constraint")

        expect_denied(f"""
set role service_role;
update public.agent_runtime_tool_plans set intent_sha256='{'c' * 64}' where id='{PLAN}';
""", "agent_runtime_tool_plan_reservation_is_immutable")

        psql(f"""
set role service_role;
update public.agent_runtime_tool_plans
 set status='completed',tool_plan='[]'::jsonb,planner_evidence='{{}}'::jsonb,updated_at=now()
 where id='{PLAN}' and owner_user_id='{OWNER}' and status='planning';
update public.agent_runtime_tool_plans
 set status='used',task_id='{TASK}',updated_at=now()
 where id='{PLAN}' and owner_user_id='{OWNER}' and status='completed';
reset role;
""")
        expect_denied(f"""
set role service_role;
update public.agent_runtime_tool_plans set status='planning',updated_at=now()
 where id='{PLAN}' and owner_user_id='{OWNER}';
""", "agent_runtime_tool_plan_terminal_state")
        expect_denied(f"""
set role service_role;
update public.agent_runtime_tool_plans set tool_plan='[{{"tool_key":"tampered"}}]'::jsonb,updated_at=now()
 where id='{PLAN}' and owner_user_id='{OWNER}';
""", "agent_runtime_tool_plan_result_is_immutable")
        expect_denied("""
set role anon;
select * from public.agent_runtime_tool_plans;
""", "permission denied")
        expect_denied("""
set role authenticated;
insert into public.agent_runtime_tool_plans(id,owner_user_id,agent_id,session_id,skill_id,agent_version,skill_version,idempotency_key,request_fingerprint,intent_sha256,trace_id)
values ('88888888-8888-4888-8888-888888888888','11111111-1111-4111-8111-111111111111',
 '33333333-3333-4333-8333-333333333333','44444444-4444-4444-8444-444444444444',
 '55555555-5555-4555-8555-555555555555',2,3,'client-cannot-insert','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','trace-client-denied-0001');
""", "permission denied")

        print("PASS: WP-07 / ENG-P10 PostgreSQL 17 verifier proves durable idempotent reservations, owner/session/Agent/Skill integrity, content-free context persistence, bounded expiry, immutable snapshots, legal status transitions and service_role-only access.")
    finally:
        run(["docker", "rm", "--force", CONTAINER], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: WP-07 durable tool-plan verification: {exc}", file=sys.stderr)
        raise SystemExit(1)
