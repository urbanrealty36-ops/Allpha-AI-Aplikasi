-- ENG-P02: self-service session inventory and revocation of other devices.
-- All reads/writes are constrained to auth.uid(); raw auth.sessions is never exposed.
create or replace function public.list_my_auth_sessions(p_current_session_id uuid)
returns table (
  id uuid,
  created_at timestamptz,
  updated_at timestamptz,
  refreshed_at timestamptz,
  not_after timestamptz,
  aal text,
  user_agent text,
  ip inet,
  is_current boolean
)
language sql
stable
security definer
set search_path = ''
as $$
  select s.id, s.created_at, s.updated_at, s.refreshed_at, s.not_after,
         s.aal, s.user_agent, s.ip, (s.id = p_current_session_id)
    from auth.sessions s
   where s.user_id = (select auth.uid())
     and (s.not_after is null or s.not_after > pg_catalog.now())
   order by s.updated_at desc nulls last, s.created_at desc;
$$;

create or replace function public.revoke_my_other_auth_sessions(p_current_session_id uuid)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_revoked integer;
begin
  if (select auth.uid()) is null then
    raise exception using errcode = '28000', message = 'authentication_required';
  end if;

  if not exists (
    select 1 from auth.sessions s
     where s.id = p_current_session_id
       and s.user_id = (select auth.uid())
       and (s.not_after is null or s.not_after > pg_catalog.now())
  ) then
    raise exception using errcode = '28000', message = 'current_session_invalid';
  end if;

  update auth.sessions
     set not_after = pg_catalog.now(),
         updated_at = pg_catalog.now()
   where user_id = (select auth.uid())
     and id <> p_current_session_id
     and (not_after is null or not_after > pg_catalog.now());

  get diagnostics v_revoked = row_count;
  return v_revoked;
end;
$$;

revoke all on function public.list_my_auth_sessions(uuid) from public, anon;
revoke all on function public.revoke_my_other_auth_sessions(uuid) from public, anon;
grant execute on function public.list_my_auth_sessions(uuid) to authenticated;
grant execute on function public.revoke_my_other_auth_sessions(uuid) to authenticated;

comment on function public.list_my_auth_sessions(uuid) is
  'ENG-P02: returns only the authenticated caller sessions and safe device metadata.';
comment on function public.revoke_my_other_auth_sessions(uuid) is
  'ENG-P02: revokes all caller sessions except the verified current session.';
