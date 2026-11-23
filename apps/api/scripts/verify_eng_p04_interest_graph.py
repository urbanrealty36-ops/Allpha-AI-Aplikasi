"""ENG-P04 PostgreSQL 17 integration verifier for ontology, graph, privacy and ranking policy."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "apps/api/supabase/migrations"
MIGRATION_91900 = MIGRATIONS / "20261123191900_eng_p04_interest_ontology_and_discovery_index.sql"
MIGRATION_92000 = MIGRATIONS / "20261123200000_eng_p04_passion_habit_recommendation_engine.sql"
CONTAINER = "allpha-p04-interest-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
AGENT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_AGENT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def run(args: list[str], sql: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, input=sql, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout + "\\n" + result.stderr)
    return result


def psql(sql: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        sql,
        check=check,
    )


def main() -> None:
    run(["docker", "run", "-d", "--rm", "--name", CONTAINER, "-e", "POSTGRES_PASSWORD=ci-only", "postgres:17-alpine"])
    try:
        time.sleep(1)
        ready = False
        for _ in range(60):
            probe = run(["docker", "exec", CONTAINER, "psql", "-X", "-A", "-t", "-U", "postgres", "-d", "postgres", "-c", "select 1"], check=False)
            if probe.returncode == 0:
                time.sleep(1)
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
create schema private;
create extension if not exists pgcrypto;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$$;
create function auth.role() returns text language sql stable as $$
  select nullif(current_setting('request.jwt.claim.role',true),'')
$$;
grant usage on schema auth to public;
grant execute on function auth.uid() to public;
grant execute on function auth.role() to public;
grant usage on schema private to service_role;

create table public.profiles(
  id uuid primary key references auth.users(id) on delete cascade,
  visibility text not null,
  account_status text not null
);
create table public.user_settings(
  user_id uuid primary key references auth.users(id) on delete cascade,
  privacy_settings jsonb not null default '{"discoverable_by_username":true,"allow_interest_matching":false}'::jsonb
);
create table public.feed_preferences(
  user_id uuid primary key references auth.users(id) on delete cascade,
  personalization_enabled boolean not null default false
);
create table public.user_interests(
  user_id uuid not null references auth.users(id) on delete cascade,
  interest_key text not null,
  preference text not null check (preference in ('interested','not_interested')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(user_id,interest_key)
);
create table public.ai_agents(id uuid primary key,status text not null);
create table public.agent_ownerships(
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  ownership_role text not null,
  status text not null,
  primary key(agent_id,owner_user_id)
);
create table private.account_export_sources(
  source_key text primary key,
  table_name text not null,
  filter_kind text not null,
  owner_columns text[] not null,
  sort_order integer not null
);
""")
        migration_919 = MIGRATION_91900.read_text(encoding="utf-8")
        migration_920 = MIGRATION_92000.read_text(encoding="utf-8")
        psql(migration_919)
        psql(migration_920)
        psql(migration_919)  # Both forward migrations must be safely repeatable.
        psql(migration_920)

        psql(f"""
insert into auth.users(id) values ('{OWNER}'),('{OTHER}');
insert into public.profiles(id,visibility,account_status) values
 ('{OWNER}','public','active'),('{OTHER}','private','active');
insert into public.user_settings(user_id,privacy_settings) values
 ('{OWNER}','{{"discoverable_by_username":true,"allow_interest_matching":true}}'::jsonb),
 ('{OTHER}','{{"discoverable_by_username":true,"allow_interest_matching":true}}'::jsonb);
insert into public.feed_preferences(user_id,personalization_enabled) values
 ('{OWNER}',false),('{OTHER}',false);
insert into public.ai_agents(id,status) values ('{AGENT}','active'),('{OTHER_AGENT}','active');
insert into public.agent_ownerships(agent_id,owner_user_id,ownership_role,status) values
 ('{AGENT}','{OWNER}','owner','active'),('{OTHER_AGENT}','{OTHER}','owner','active');
set request.jwt.claim.role='service_role';
select * from public.set_my_interest_preference_for_actor('{OWNER}','technology','interested');
do $$
begin
  if not exists(select 1 from private.user_interest_discovery_index where user_id='{OWNER}' and interest_key='technology') then
    raise exception 'opted-in interest missing from private discovery index';
  end if;
  if has_table_privilege('authenticated','public.user_interests','INSERT') then
    raise exception 'authenticated can write canonical interest preferences directly';
  end if;
  if has_table_privilege('authenticated','private.user_interest_discovery_index','SELECT') then
    raise exception 'authenticated can read private discovery index';
  end if;
end $$;
select * from public.find_interest_discovery_candidates(array['technology'],20);
""")

        psql(f"""
set request.jwt.claim.role='service_role';
select * from public.set_user_interest_graph_signal_for_actor(
 '{OWNER}','technology','passion',0.8,'user_selected','interest-graph-v1',null
);
select * from public.set_user_interest_graph_signal_for_actor(
 '{OWNER}','technology','passion',0.7,'user_selected','interest-graph-v1','{AGENT}'
);
do $$
begin
  begin
    perform * from public.set_user_interest_graph_signal_for_actor(
      '{OWNER}','technology','habit',0.5,'observed_interaction','interest-graph-v1',null
    );
    raise exception 'observed Habit signal unexpectedly succeeded without personalization consent';
  exception when insufficient_privilege then null;
  end;
  begin
    perform * from public.set_user_interest_graph_signal_for_actor(
      '{OWNER}','health','habit',0.5,'observed_interaction','interest-graph-v1',null
    );
    raise exception 'sensitive observed Habit signal unexpectedly succeeded';
  exception when insufficient_privilege then null;
  end;
  begin
    perform * from public.set_user_interest_graph_signal_for_actor(
      '{OWNER}','technology','passion',0.5,'observed_interaction','interest-graph-v1',null
    );
    raise exception 'inferred Passion signal unexpectedly succeeded';
  exception when insufficient_privilege then null;
  end;
  begin
    perform * from public.set_user_interest_graph_signal_for_actor(
      '{OWNER}','technology','passion',0.5,'user_selected','interest-graph-v1','{OTHER_AGENT}'
    );
    raise exception 'unowned Agent signal unexpectedly succeeded';
  exception when insufficient_privilege then null;
  end;
end $$;
update public.feed_preferences set personalization_enabled=true where user_id='{OWNER}';
select * from public.set_user_interest_graph_signal_for_actor(
 '{OWNER}','technology','habit',0.6,'observed_interaction','interest-graph-v1',null
);
do $$
begin
  if (select count(*) from public.user_interest_graph_signals where user_id='{OWNER}') <> 3 then
    raise exception 'expected Human Passion, Agent Passion and observed Habit signals';
  end if;
  if has_table_privilege('authenticated','public.user_interest_graph_signals','INSERT') then
    raise exception 'authenticated can write Passion/Habit signals directly';
  end if;
  if has_function_privilege('authenticated','public.set_user_interest_graph_signal_for_actor(uuid,text,text,numeric,text,text,uuid)','EXECUTE') then
    raise exception 'authenticated can execute service-only signal RPC';
  end if;
  if not has_function_privilege('service_role','public.set_user_interest_graph_signal_for_actor(uuid,text,text,numeric,text,text,uuid)','EXECUTE') then
    raise exception 'service_role signal RPC grant missing';
  end if;
  if not exists(select 1 from public.recommendation_scoring_policies where policy_key='default' and active=true) then
    raise exception 'canonical recommendation policy missing';
  end if;
  if (select count(*) from private.account_export_sources where source_key in ('interest_graph_signals','interest_graph_signal_events')) <> 2 then
    raise exception 'interest graph export sources missing';
  end if;
end $$;
update public.feed_preferences set personalization_enabled=false where user_id='{OWNER}';
do $$
begin
  if exists(select 1 from public.user_interest_graph_signals where user_id='{OWNER}' and signal_source='observed_interaction') then
    raise exception 'observed Habit signal survived personalization opt-out';
  end if;
  if not exists(select 1 from public.user_interest_graph_signal_events where user_id='{OWNER}' and action='delete' and signal_source='observed_interaction') then
    raise exception 'observed Habit opt-out event missing';
  end if;
  if not exists(select 1 from public.user_interest_graph_signals where user_id='{OWNER}' and signal_type='passion') then
    raise exception 'explicit Passion signals must survive Habit opt-out';
  end if;
end $$;
select public.clear_user_interest_graph_signals_for_actor('{OWNER}');
do $$
begin
  if exists(select 1 from public.user_interest_graph_signals where user_id='{OWNER}') then
    raise exception 'signal reset left graph data';
  end if;
  if not exists(select 1 from public.user_interest_graph_signal_events where user_id='{OWNER}' and action='reset') then
    raise exception 'signal reset audit event missing';
  end if;
end $$;
""")

        psql(f"""
update public.user_settings
   set privacy_settings='{{"discoverable_by_username":true,"allow_interest_matching":false}}'::jsonb
 where user_id='{OWNER}';
do $$
begin
  if exists(select 1 from private.user_interest_discovery_index where user_id='{OWNER}') then
    raise exception 'interest matching opt-out left private discovery index rows';
  end if;
end $$;
""")
        print("PASS: ENG-P04 91900/92000 PostgreSQL 17 apply-twice, canonical taxonomy, discovery opt-in, Human/Agent signals, sensitive inference guard, opt-out cleanup, export and server-only permissions.")
    finally:
        run(["docker", "rm", "--force", CONTAINER], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: ENG-P04 Interest Graph PostgreSQL 17 verification: {exc}", file=sys.stderr)
        raise SystemExit(1)
