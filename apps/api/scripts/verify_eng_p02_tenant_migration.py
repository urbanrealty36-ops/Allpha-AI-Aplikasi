"""Validate ENG-P02 tenant repair and RBAC on disposable PostgreSQL 17 (CI only)."""
from __future__ import annotations
from pathlib import Path
import subprocess, sys, time, uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps/api/supabase/migrations/20261123191500_eng_p02_forward_repair_tenant_and_session_schema.sql"
CONTAINER = f"allpha-eng-p02-migration-{uuid.uuid4().hex[:10]}"

def run(command: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result

def psql(sql: str) -> subprocess.CompletedProcess[str]:
    try:
        return run(["docker","exec","-i",CONTAINER,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres"],input_text=sql)
    except RuntimeError as exc:
        logs = run(["docker","logs",CONTAINER],check=False)
        raise RuntimeError(f"{exc}\ncontainer logs:\n{logs.stdout}\n{logs.stderr}") from exc

def main() -> int:
    if not MIGRATION.is_file(): raise RuntimeError(f"Migration not found: {MIGRATION}")
    migration_sql=MIGRATION.read_text(encoding="utf-8")
    run(["docker","run","--detach","--rm","--name",CONTAINER,"-e","POSTGRES_PASSWORD=allpha-ci-only","postgres:17-alpine"])
    try:
        # The official image briefly starts a temporary postmaster during initdb.
        # pg_isready can report that temporary socket as ready just before it shuts down.
        # Require two successful SQL probes separated by a short stability interval.
        time.sleep(1)
        ready = False
        for attempt in range(60):
            probe = run(["docker","exec",CONTAINER,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False)
            if probe.returncode == 0:
                time.sleep(1)
                stable = run(["docker","exec",CONTAINER,"psql","-X","-A","-t","-U","postgres","-d","postgres","-c","select 1"],check=False)
                if stable.returncode == 0:
                    ready = True
                    break
            time.sleep(1)
        if not ready: raise RuntimeError("Disposable PostgreSQL 17 did not reach stable SQL readiness")
        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create table auth.users(id uuid primary key);
create table auth.sessions(id uuid primary key,user_id uuid not null references auth.users(id) on delete cascade,created_at timestamptz default now(),updated_at timestamptz not null default now(),refreshed_at timestamp,not_after timestamptz,aal text,user_agent text,ip inet);
create or replace function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
grant usage on schema auth to authenticated;
grant execute on function auth.uid() to public;
grant usage on schema public to service_role;
""")
        psql(migration_sql)
        psql(migration_sql)
        psql("""
insert into auth.users(id) values
 ('11111111-1111-4111-8111-111111111111'),
 ('22222222-2222-4222-8222-222222222222'),
 ('33333333-3333-4333-8333-333333333333'),
 ('44444444-4444-4444-8444-444444444444'),
 ('55555555-5555-4555-8555-555555555555');
insert into auth.sessions(id,user_id,aal,user_agent,ip) values
 ('66666666-6666-4666-8666-666666666666','11111111-1111-4111-8111-111111111111','aal1','Allpha Android','192.0.2.10'),
 ('77777777-7777-4777-8777-777777777777','11111111-1111-4111-8111-111111111111','aal1','Allpha Web','192.0.2.11'),
 ('88888888-8888-4888-8888-888888888888','22222222-2222-4222-8222-222222222222','aal1','Other user','192.0.2.12');
set role service_role;
select id as org_id from public.create_organization_for_user('11111111-1111-4111-8111-111111111111','ENG-P02 Repair Check','eng-p02-repair-check') \gset
select set_config('app.test_org_id', :'org_id', false);
select * from public.add_organization_member_for_actor(current_setting('app.test_org_id')::uuid,'11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','admin');
select * from public.add_organization_member_for_actor(current_setting('app.test_org_id')::uuid,'22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333','member');
do $$
begin
 begin
  perform * from public.add_organization_member_for_actor(current_setting('app.test_org_id')::uuid,'22222222-2222-4222-8222-222222222222','44444444-4444-4444-8444-444444444444','admin');
  raise exception using errcode='P0001',message='admin unexpectedly granted admin role';
 exception when insufficient_privilege then null;
 end;
 begin
  perform * from public.update_organization_member_role_for_actor(current_setting('app.test_org_id')::uuid,'22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333','admin');
  raise exception using errcode='P0001',message='admin unexpectedly promoted member';
 exception when insufficient_privilege then null;
 end;
end $$;
select * from public.update_organization_member_role_for_actor(current_setting('app.test_org_id')::uuid,'11111111-1111-4111-8111-111111111111','33333333-3333-4333-8333-333333333333','admin');
do $$
begin
 begin
  perform * from public.update_organization_member_role_for_actor(
   current_setting('app.test_org_id')::uuid,
   '44444444-4444-4444-8444-444444444444','33333333-3333-4333-8333-333333333333','member');
  raise exception using errcode='P0001',message='non-member unexpectedly changed a tenant role';
 exception when insufficient_privilege then null;
 end;
end $$;
do $$
begin
 begin
  perform public.remove_organization_member_for_actor(current_setting('app.test_org_id')::uuid,'22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333');
  raise exception using errcode='P0001',message='admin unexpectedly removed another admin';
 exception when insufficient_privilege then null;
 end;
 begin
  perform public.remove_organization_member_for_actor(current_setting('app.test_org_id')::uuid,'11111111-1111-4111-8111-111111111111','11111111-1111-4111-8111-111111111111');
  raise exception using errcode='P0001',message='owner unexpectedly removed owner membership';
 exception when insufficient_privilege then null;
 end;
end $$;
select * from public.add_organization_member_for_actor(current_setting('app.test_org_id')::uuid,'11111111-1111-4111-8111-111111111111','55555555-5555-4555-8555-555555555555','member');
-- Exercise authenticated RLS as a regular member before removing that member.
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub','55555555-5555-4555-8555-555555555555',false);
do $$
begin
 if (select count(*) from public.organizations where id=current_setting('app.test_org_id')::uuid)<>1 then raise exception 'tenant member cannot read its organization'; end if;
 if (select count(*) from public.organization_memberships where organization_id=current_setting('app.test_org_id')::uuid)<>1 then raise exception 'tenant member must see only its own membership'; end if;
 if (select count(*) from public.audit_events where organization_id=current_setting('app.test_org_id')::uuid)<>0 then raise exception 'tenant member must not read admin audit events'; end if;
end $$;
reset role;
set role service_role;
select public.remove_organization_member_for_actor(current_setting('app.test_org_id')::uuid,'22222222-2222-4222-8222-222222222222','55555555-5555-4555-8555-555555555555');
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub','44444444-4444-4444-8444-444444444444',false);
-- Keep the outsider RLS assertion diagnosable: distinguish stale JWT context,
-- a permissive legacy policy, and an unexpected membership row.
select current_user as effective_role, session_user as session_role,
       auth.uid() as effective_auth_uid,
       private.is_organization_member(current_setting('app.test_org_id')::uuid) as is_member,
       private.is_organization_admin(current_setting('app.test_org_id')::uuid) as is_admin;
select policyname, cmd, qual, roles
  from pg_policies
 where schemaname='public' and tablename='organizations'
 order by policyname;
do $
begin
 if auth.uid() <> '44444444-4444-4444-8444-444444444444'::uuid then
   raise exception 'test harness JWT context mismatch: %', auth.uid();
 end if;
 if private.is_organization_member(current_setting('app.test_org_id')::uuid) then
   raise exception 'outsider unexpectedly remains an organization member';
 end if;
 if (select count(*) from public.organizations where slug='eng-p02-repair-check')<>0 then raise exception 'cross-user organization read leaked'; end if;
 if (select count(*) from public.organization_memberships where user_id='11111111-1111-4111-8111-111111111111')<>0 then raise exception 'cross-user membership read leaked'; end if;
 begin
  insert into public.organizations(slug,name,owner_id) values('client-write-forbidden','Forbidden','44444444-4444-4444-8444-444444444444');
  raise exception using errcode='P0001',message='authenticated direct organization insert unexpectedly succeeded';
 exception when insufficient_privilege then null;
 end;
end $$;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
select id, is_current, user_agent, ip from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666');
do $allpha_session_list_test$
begin
 if (select count(*) from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666'))<>2 then raise exception 'session list must include only the caller active sessions'; end if;
 if not exists(select 1 from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666') where id='66666666-6666-4666-8666-666666666666') then raise exception 'current session row missing'; end if;
 if not exists(select 1 from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666') where id='66666666-6666-4666-8666-666666666666' and is_current) then raise exception 'current session marker missing'; end if;
 if not exists(select 1 from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666') where id='66666666-6666-4666-8666-666666666666' and user_agent='Allpha Android') then raise exception 'current session user-agent metadata missing'; end if;
 if not exists(select 1 from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666') where id='66666666-6666-4666-8666-666666666666' and ip like '192.0.2.10%') then raise exception 'current session IP metadata missing'; end if;
 if exists(select 1 from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666') where id='88888888-8888-4888-8888-888888888888') then raise exception 'foreign user session leaked'; end if;
end $allpha_session_list_test$;
select public.revoke_my_other_auth_sessions('66666666-6666-4666-8666-666666666666');
do $allpha_session_revoke_test$
begin
 if exists(select 1 from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666') where id='77777777-7777-4777-8777-777777777777') then raise exception 'revoked other session remains visible'; end if;
 if (select count(*) from public.list_my_auth_sessions('66666666-6666-4666-8666-666666666666'))<>1 then raise exception 'revoked sessions must disappear from session list'; end if;
end $allpha_session_revoke_test$;
select public.revoke_my_auth_session('66666666-6666-4666-8666-666666666666');
reset role;
do $$
begin
 if not (select not_after is not null from auth.sessions where id='66666666-6666-4666-8666-666666666666') then raise exception 'session revoke failed'; end if;
 if not exists(select 1 from public.audit_events where action='organization.created') then raise exception 'organization audit missing'; end if;
 if not exists(select 1 from public.audit_events where action='organization.member.added') then raise exception 'membership add audit missing'; end if;
 if not exists(select 1 from public.audit_events where action='organization.member.role_changed') then raise exception 'membership role audit missing'; end if;
 if not exists(select 1 from public.audit_events where action='organization.member.removed') then raise exception 'membership removal audit missing'; end if;
 if not exists(select 1 from public.audit_events where action='auth.session.revoked') then raise exception 'session revoke audit missing'; end if;
 if has_function_privilege('authenticated','public.create_organization_for_user(uuid,text,text)','EXECUTE') then raise exception 'authenticated can execute server-only organization creation RPC'; end if;
 if not has_function_privilege('authenticated','private.is_organization_member(uuid)','EXECUTE') then raise exception 'authenticated cannot execute membership RLS predicate'; end if;
 if not has_function_privilege('authenticated','private.is_organization_admin(uuid)','EXECUTE') then raise exception 'authenticated cannot execute admin RLS predicate'; end if;
 if has_function_privilege('anon','private.is_organization_member(uuid)','EXECUTE') or has_function_privilege('anon','private.is_organization_admin(uuid)','EXECUTE') then raise exception 'anon can execute tenant RLS predicates'; end if;
 if not has_function_privilege('authenticated','public.list_my_auth_sessions(uuid)','EXECUTE') then raise exception 'authenticated cannot list own sessions'; end if;
 if has_function_privilege('anon','public.list_my_auth_sessions(uuid)','EXECUTE') then raise exception 'anon can list auth sessions'; end if;

 if not has_function_privilege('service_role','public.create_organization_for_user(uuid,text,text)','EXECUTE') then raise exception 'service_role cannot execute organization creation RPC'; end if;
 if has_table_privilege('authenticated','public.organizations','INSERT') then raise exception 'authenticated can directly insert organizations'; end if;
 if not (select relrowsecurity from pg_class where oid='public.organizations'::regclass) or not (select relrowsecurity from pg_class where oid='public.organization_memberships'::regclass) or not (select relrowsecurity from pg_class where oid='public.audit_events'::regclass) then raise exception 'RLS missing'; end if;
end $$;
select set_config('request.jwt.claim.sub','22222222-2222-4222-8222-222222222222',false);
do $$
begin
 if (select count(*) from public.organizations where id=current_setting('app.test_org_id')::uuid)<>1 then raise exception 'tenant admin cannot read its organization'; end if;
 if (select count(*) from public.organization_memberships where organization_id=current_setting('app.test_org_id')::uuid)<>3 then raise exception 'tenant admin cannot read all organization memberships'; end if;
 if (select count(*) from public.audit_events where organization_id=current_setting('app.test_org_id')::uuid)=0 then raise exception 'tenant admin cannot read organization audit events'; end if;
end $$;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
do $$
begin
 if (select count(*) from public.organizations where id=current_setting('app.test_org_id')::uuid)<>1 then raise exception 'tenant owner cannot read its organization'; end if;
 if (select count(*) from public.organization_memberships where organization_id=current_setting('app.test_org_id')::uuid)<>3 then raise exception 'tenant owner cannot read all organization memberships'; end if;
 if (select count(*) from public.audit_events where organization_id=current_setting('app.test_org_id')::uuid)=0 then raise exception 'tenant owner cannot read organization audit events'; end if;
end $$;
select set_config('request.jwt.claim.sub','44444444-4444-4444-8444-444444444444',false);
do $$
begin
 if (select count(*) from public.organizations where slug='eng-p02-repair-check')<>0 then raise exception 'cross-user organization read leaked'; end if;
 if (select count(*) from public.organization_memberships where user_id='11111111-1111-4111-8111-111111111111')<>0 then raise exception 'cross-user membership read leaked'; end if;
end $$;
""")
        print("PASS: forward repair migration applies twice; tenant member/admin/owner/outsider RLS reads, server-only organization/member commands, role hierarchy, audit and session revocation verified.")
        return 0
    finally:
        run(["docker","rm","--force",CONTAINER],check=False)

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: ENG-P02 forward repair migration verification: {exc}",file=sys.stderr)
        raise SystemExit(1)