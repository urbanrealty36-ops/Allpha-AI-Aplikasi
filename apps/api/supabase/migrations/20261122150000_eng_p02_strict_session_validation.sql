-- ENG-P02: validate every bearer session against the canonical Supabase Auth session registry.
-- The caller identity comes from auth.uid(); clients cannot validate another user's session.
create or replace function public.is_auth_session_active(p_session_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
      from auth.sessions s
     where s.id = p_session_id
       and s.user_id = (select auth.uid())
       and (s.not_after is null or s.not_after > pg_catalog.now())
  );
$$;

revoke all on function public.is_auth_session_active(uuid) from public, anon;
grant execute on function public.is_auth_session_active(uuid) to authenticated;
comment on function public.is_auth_session_active(uuid) is
  'ENG-P02 strict session fence. Validates JWT session_id against auth.sessions for auth.uid(); revoked/expired sessions fail closed.';
