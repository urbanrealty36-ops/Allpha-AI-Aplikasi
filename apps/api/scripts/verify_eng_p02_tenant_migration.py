"""Validate ENG-P02 tenant repair and RBAC on disposable PostgreSQL 17 (CI only)."""
from __future__ import annotations
from pathlib import Path
import subprocess, sys, time, uuid

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps/api/supabase/migrations/20261122140000_eng_p02_restore_missing_tenant_authorization_schema.sql"
CONTAINER = f"allpha-eng-p02-migration-{uuid.uuid4().hex[:10]}"

def run(command: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result

def psql(sql: str) -> subprocess.CompletedProcess[str]:
    return run(["docker","exec","-i",CONTAINER,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d","postgres"],input_text=sql)

def main() -> int:
    if not MIGRATION.is_file(): raise RuntimeError(f"Migration not found: {MIGRATION}")
    migration_sql=MIGRATION.read_text(encoding="utf-8")
    run(["docker","run","--detach","--rm","--name",CONTAINER,"-e","POSTGRES_PASSWORD=allpha-ci-only","postgres:17-alpine"])
    try:
        for attempt in range(60):
            ready=run(["docker","exec",CONTAINER,"pg_isready","-U","postgres","-d","postgres"],check=False)
            if ready.returncode==0: break
            if attempt==59: raise RuntimeError("Disposable PostgreSQL 17 did not become ready")
            time.sleep(1)
        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create table auth.users(id uuid primary key);
create table auth.sessions(id uuid primary key,user_id uuid not null references auth.users(id) on delete cascade,not_after timestamptz,updated_at timestamptz not null default now());
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
insert into auth.sessions(id,user_id) values ('66666666-6666-4666-8666-666666666666','11111111-1111-4111-8111-111111111111');
set role service_role;
select * from public.create_organization_for_user('11111111-1111-4111-8111-111111111111','ENG-P02 Repair Check','eng-p02-repair-check');
select * from public.add_organization_member_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','admin');
select * from public.add_organization_member_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333','member');
do $$
begin
 begin
  perform * from public.add_organization_member_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'22222222-2222-4222-8222-222222222222','44444444-4444-4444-8444-444444444444','admin');
  raise exception using errcode='P0001',message='admin unexpectedly granted admin role';
 exception when insufficient_privilege then null;
 end;
 begin
  perform * from public.update_organization_member_role_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333','admin');
  raise exception using errcode='P0001',message='admin unexpectedly promoted member';
 exception when insufficient_privilege then null;
 end;
end $$;
select * from public.update_organization_member_role_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'11111111-1111-4111-8111-111111111111','33333333-3333-4333-8333-333333333333','admin');
do $$
begin
 begin
  perform public.remove_organization_member_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333');
  raise exception using errcode='P0001',message='admin unexpectedly removed another admin';
 exception when insufficient_privilege then null;
 end;
 begin
  perform public.remove_organization_member_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'11111111-1111-4111-8111-111111111111','11111111-1111-4111-8111-111111111111');
  raise exception using errcode='P0001',message='owner unexpectedly removed owner membership';
 exception when insufficient_privilege then null;
 end;
end $$;
select * from public.add_organization_member_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'11111111-1111-4111-8111-111111111111','55555555-5555-4555-8555-555555555555','member');
select public.remove_organization_member_for_actor((select id from public.organizations where slug='eng-p02-repair-check'),'22222222-2222-4222-8222-222222222222','55555555-5555-4555-8555-555555555555');
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub','44444444-4444-4444-8444-444444444444',false);
do $$
begin
 if (select count(*) from public.organizations where slug='eng-p02-repair-check')<>0 then raise exception 'cross-user organization read leaked'; end if;
 if (select count(*) from public.organization_memberships where user_id='11111111-1111-4111-8111-111111111111')<>0 then raise exception 'cross-user membership read leaked'; end if;
 begin
  insert into public.organizations(slug,name,owner_id) values('client-write-forbidden','Forbidden','44444444-4444-4444-8444-444444444444');
  raise exception using errcode='P0001',message='authenticated direct organization insert unexpectedly succeeded';
 exception when insufficient_privilege then null;
 end;
end $$;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
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
 if not has_function_privilege('service_role','public.create_organization_for_user(uuid,text,text)','EXECUTE') then raise exception 'service_role cannot execute organization creation RPC'; end if;
 if has_table_privilege('authenticated','public.organizations','INSERT') then raise exception 'authenticated can directly insert organizations'; end if;
 if not (select relrowsecurity from pg_class where oid='public.organizations'::regclass) or not (select relrowsecurity from pg_class where oid='public.organization_memberships'::regclass) or not (select relrowsecurity from pg_class where oid='public.audit_events'::regclass) then raise exception 'RLS missing'; end if;
end $$;
""")
        print("PASS: migration applies twice; server-only organization/member commands, role hierarchy, audit, session revocation and tenant RLS verified.")
        return 0
    finally:
        run(["docker","rm","--force",CONTAINER],check=False)

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: ENG-P02 migration verification: {exc}",file=sys.stderr)
        raise SystemExit(1)
