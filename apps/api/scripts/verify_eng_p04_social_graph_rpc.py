"""ENG-P04 disposable PostgreSQL 17 verification for Social Graph RPCs and grants."""
from __future__ import annotations
from pathlib import Path
import subprocess, sys, time, uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps/api/supabase/migrations/20261122170000_eng_p04_social_graph_server_command_boundary.sql"
NAME = "allpha-p04-" + uuid.uuid4().hex[:8]

def run(args, sql=None, check=True):
    result = subprocess.run(args, input=sql, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout + "\\n" + result.stderr)
    return result

def psql(sql):
    return run(["docker","exec","-i",NAME,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres"], sql)

def main():
    run(["docker","run","-d","--rm","--name",NAME,"-e","POSTGRES_PASSWORD=ci-only","postgres:17-alpine"])
    try:
        # Avoid the temporary initdb postmaster false-positive from pg_isready.
        time.sleep(1)
        ready = False
        for i in range(60):
            probe = run(["docker","exec",NAME,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False)
            if probe.returncode == 0:
                time.sleep(1)
                stable = run(["docker","exec",NAME,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False)
                if stable.returncode == 0:
                    ready = True
                    break
            time.sleep(1)
        if not ready: raise RuntimeError("PostgreSQL 17 did not reach stable SQL readiness")
        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create extension if not exists pgcrypto;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
grant usage on schema auth to public;
grant execute on function auth.uid() to public;
create table public.profiles(id uuid primary key references auth.users(id),visibility text not null,account_status text not null);
create table public.ai_agents(id uuid primary key,status text not null,visibility text not null);
create table public.agent_ownerships(agent_id uuid references public.ai_agents(id),owner_user_id uuid references auth.users(id),ownership_role text,status text,primary key(agent_id,owner_user_id));
create table public.social_edges(
 id uuid primary key default gen_random_uuid(),actor_user_id uuid not null references auth.users(id),
 target_user_id uuid not null references auth.users(id),actor_node_type text not null default 'human',
 target_node_type text not null default 'human',actor_agent_id uuid references public.ai_agents(id),
 target_agent_id uuid references public.ai_agents(id),edge_type text not null,status text not null default 'active',
 idempotency_key text,created_at timestamptz default now());
create unique index social_edges_unique on public.social_edges(actor_node_type,coalesce(actor_agent_id,actor_user_id),target_node_type,coalesce(target_agent_id,target_user_id),edge_type);
create unique index social_edges_actor_idempotency_idx on public.social_edges(actor_user_id,idempotency_key) where idempotency_key is not null;
create table public.social_graph_events(id uuid primary key default gen_random_uuid(),event_type text,actor_user_id uuid,target_user_id uuid);
create function public.enforce_social_edge_policy() returns trigger language plpgsql security definer set search_path='' as $$
declare v_visibility text;
begin
 if tg_op='INSERT' then
  if new.actor_user_id is distinct from auth.uid() then raise exception using errcode='42501',message='actor mismatch'; end if;
  if new.actor_node_type='agent' and not exists(select 1 from public.agent_ownerships o join public.ai_agents a on a.id=o.agent_id where o.agent_id=new.actor_agent_id and o.owner_user_id=new.actor_user_id and o.status='active' and o.ownership_role in ('owner','operator') and a.status='active') then raise exception using errcode='42501',message='agent ownership required'; end if;
  if new.target_node_type='human' then select p.visibility into v_visibility from public.profiles p where p.id=new.target_user_id and p.account_status='active';
  else select a.visibility into v_visibility from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id and o.owner_user_id=new.target_user_id and o.ownership_role='owner' and o.status='active' where a.id=new.target_agent_id and a.status='active'; end if;
  if v_visibility is null then raise exception using errcode='42501',message='target unavailable'; end if;
  if new.edge_type='follow' and v_visibility='private' then new.status='requested'; else new.status='active'; end if;
  return new;
 elsif tg_op='UPDATE' then
  if old.status<>'requested' or new.status<>'active' or new.target_user_id is distinct from auth.uid() then raise exception using errcode='42501',message='target owner required'; end if;
  return new;
 end if;
 return old;
end $$;
create trigger social_edges_policy before insert or update on public.social_edges for each row execute function public.enforce_social_edge_policy();
create function public.capture_social_graph_event() returns trigger language plpgsql security definer set search_path='' as $$
begin
 insert into public.social_graph_events(event_type,actor_user_id,target_user_id)
 values(case when tg_op='INSERT' then 'created' when tg_op='UPDATE' then 'updated' else 'removed' end,
 coalesce(new.actor_user_id,old.actor_user_id),coalesce(new.target_user_id,old.target_user_id));
 return coalesce(new,old);
end $$;
create trigger social_edges_events after insert or update or delete on public.social_edges for each row execute function public.capture_social_graph_event();
alter table public.social_edges enable row level security;
create policy social_edges_read on public.social_edges for select to authenticated using(actor_user_id=auth.uid() or target_user_id=auth.uid());
grant select,delete,truncate,references,trigger on public.social_edges to authenticated;
grant insert(actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,edge_type,status,idempotency_key) on public.social_edges to authenticated;
grant update(status) on public.social_edges to authenticated;
""")
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(migration)
        psql(migration)  # forward migration must be safely repeatable
        psql("""
insert into auth.users(id) values
 ('11111111-1111-4111-8111-111111111111'),
 ('22222222-2222-4222-8222-222222222222'),
 ('33333333-3333-4333-8333-333333333333');
insert into public.profiles values
 ('11111111-1111-4111-8111-111111111111','public','active'),
 ('22222222-2222-4222-8222-222222222222','private','active'),
 ('33333333-3333-4333-8333-333333333333','public','active');
insert into public.ai_agents values ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','active','public');
insert into public.agent_ownerships values ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','11111111-1111-4111-8111-111111111111','owner','active');
""")
        psql("""
set role service_role;
select id as follow_id from public.create_social_edge_for_actor('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','human','human',null,null,'follow','follow-key-001') \\gset
select * from public.accept_social_follow_for_actor('22222222-2222-4222-8222-222222222222',:'follow_id');
select id as reject_id from public.create_social_edge_for_actor('33333333-3333-4333-8333-333333333333','22222222-2222-4222-8222-222222222222','human','human',null,null,'follow','reject-key-001') \\gset
select * from public.reject_social_follow_for_actor('22222222-2222-4222-8222-222222222222',:'reject_id');
select id as agent_edge_id from public.create_social_edge_for_actor('11111111-1111-4111-8111-111111111111','33333333-3333-4333-8333-333333333333','agent','human','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',null,'follow','agent-key-001') \\gset
select * from public.remove_social_edge_for_actor('11111111-1111-4111-8111-111111111111',:'agent_edge_id');
reset role;
do $$
begin
 if has_table_privilege('authenticated','public.social_edges','INSERT') or has_table_privilege('authenticated','public.social_edges','UPDATE') or has_table_privilege('authenticated','public.social_edges','DELETE') then raise exception 'authenticated table-level DML remains'; end if;
 if has_column_privilege('authenticated','public.social_edges','actor_user_id','INSERT') or has_column_privilege('authenticated','public.social_edges','status','UPDATE') then raise exception 'authenticated column-level DML remains'; end if;
 if has_function_privilege('authenticated','public.create_social_edge_for_actor(uuid,uuid,text,text,uuid,uuid,text,text)','EXECUTE') then raise exception 'authenticated can execute server RPC'; end if;
 if not has_function_privilege('service_role','public.create_social_edge_for_actor(uuid,uuid,text,text,uuid,uuid,text,text)','EXECUTE') then raise exception 'service_role RPC grant missing'; end if;
 if (select count(*) from public.social_graph_events)<6 then raise exception 'event capture missing'; end if;
end $$;
""")
        print("PASS: ENG-P04 migration apply-twice, server-only DML grants, Human/Agent ownership, private follow accept/reject/remove and event capture.")
    finally:
        run(["docker","rm","--force",NAME],check=False)

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"FAIL: ENG-P04 PostgreSQL 17 verification: {exc}",file=sys.stderr)
        raise SystemExit(1)
