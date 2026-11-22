-- ENG-P02: explicit per-session revocation for protected API traffic.
create or replace function public.is_auth_session_active(p_session_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from auth.sessions s
     where s.id = p_session_id
       and s.user_id = (select auth.uid())
       and (s.not_after is null or s.not_after > pg_catalog.now())
  );
$$;

create or replace function public.revoke_my_auth_session(p_session_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null then
    raise exception using errcode = '28000', message = 'authentication_required';
  end if;
  update auth.sessions
     set not_after = pg_catalog.now(),
         updated_at = pg_catalog.now()
   where id = p_session_id
     and user_id = (select auth.uid())
     and (not_after is null or not_after > pg_catalog.now());
  return found;
end;
$$;

revoke all on function public.is_auth_session_active(uuid) from public, anon;
revoke all on function public.revoke_my_auth_session(uuid) from public, anon;
grant execute on function public.is_auth_session_active(uuid) to authenticated;
grant execute on function public.revoke_my_auth_session(uuid) to authenticated;
comment on function public.revoke_my_auth_session(uuid) is
  'ENG-P02: immediately fences the caller session in auth.sessions before client-side Supabase sign-out.';
