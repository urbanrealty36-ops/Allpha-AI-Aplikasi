"""Validate the ENG-P02 forward repair on disposable PostgreSQL 17 (CI only)."""
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
    if not MIGRATION.is_file():
        raise RuntimeError(f"Migration not found: {MIGRATION}")
    migration_sql = MIGRATION.read_text(encoding="utf-8")
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
""")
        psql(migration_sql)
        psql(migration_sql)
        psql("""
insert into auth.users(id) values ('11111111-1111-4111-8111-111111111111'),('22222222-2222-4222-8222-222222222222');
insert into auth.sessions(id,user_id) values ('33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111');
set role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
insert into public.organizations(slug,name,owner_id) values ('eng-p02-repair-check','ENG-P02 Repair Check','11111111-1111-4111-8111-111111111111');
do $$
begin
 if (select count(*) from public.organizations where slug='eng-p02-repair-check')<>1 then raise exception 'owner cannot read organization'; end if;
 if (select count(*) from public.organization_memberships where user_id='11111111-1111-4111-8111-111111111111' and role='owner')<>1 then raise exception 'owner membership trigger missing'; end if;
 if (select count(*) from public.audit_events where action='organization.created')<>1 then raise exception 'organization audit missing'; end if;
end $$;
do $$
begin
 begin
  update public.organizations set owner_id='22222222-2222-4222-8222-222222222222' where slug='eng-p02-repair-check';
  raise exception using errcode='P0001',message='owner_id update unexpectedly succeeded';
 exception when insufficient_privilege then null;
 end;
 begin
  insert into public.organization_memberships(organization_id,user_id,role) select id,'22222222-2222-4222-8222-222222222222','admin' from public.organizations where slug='eng-p02-repair-check';
  raise exception using errcode='P0001',message='membership escalation unexpectedly succeeded';
 exception when insufficient_privilege then null;
 end;
end $$;
select set_config('request.jwt.claim.sub','22222222-2222-4222-8222-222222222222',false);
do $$
begin
 if (select count(*) from public.organizations where slug='eng-p02-repair-check')<>0 then raise exception 'cross-user organization read leaked'; end if;
 if (select count(*) from public.organization_memberships where user_id='11111111-1111-4111-8111-111111111111')<>0 then raise exception 'cross-user membership read leaked'; end if;
end $$;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
select public.revoke_my_auth_session('33333333-3333-4333-8333-333333333333');
reset role;
do $$
begin
 if not (select not_after is not null from auth.sessions where id='33333333-3333-4333-8333-333333333333') then raise exception 'session revoke failed'; end if;
 if not exists(select 1 from public.audit_events where action='auth.session.revoked' and resource_id='33333333-3333-4333-8333-333333333333') then raise exception 'session revoke audit missing'; end if;
 if has_column_privilege('authenticated','public.organizations','owner_id','UPDATE') then raise exception 'owner_id remains updateable'; end if;
 if not has_column_privilege('authenticated','public.organizations','slug','UPDATE') or not has_column_privilege('authenticated','public.organizations','name','UPDATE') then raise exception 'editable org columns missing'; end if;
 if has_function_privilege('anon','public.revoke_my_auth_session(uuid)','EXECUTE') then raise exception 'anon can execute revoke function'; end if;
 if not has_function_privilege('authenticated','public.revoke_my_auth_session(uuid)','EXECUTE') then raise exception 'authenticated cannot execute self-scoped revoke function'; end if;
 if not (select relrowsecurity from pg_class where oid='public.organizations'::regclass) or not (select relrowsecurity from pg_class where oid='public.organization_memberships'::regclass) or not (select relrowsecurity from pg_class where oid='public.audit_events'::regclass) then raise exception 'RLS missing'; end if;
end $$;
""")
        print("PASS: migration applies twice; owner bootstrap/audit, session revocation, tenant RLS and owner_id privilege boundary verified.")
        return 0
    finally:
        run(["docker","rm","--force",CONTAINER],check=False)

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: ENG-P02 migration verification: {exc}",file=sys.stderr)
        raise SystemExit(1)
