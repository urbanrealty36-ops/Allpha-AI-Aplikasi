-- ENG-P01 security correction: account lifecycle changes must not require
-- granting direct UPDATE on the server-owned profiles.account_status column.
-- The RPC derives the target identity exclusively from auth.uid() and is idempotent.
create or replace function public.request_account_deactivation()
returns table (id uuid, account_status text, updated_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null then
    raise exception 'authentication_required' using errcode = '28000';
  end if;

  return query
    update public.profiles as p
       set account_status = 'deactivation_requested'
     where p.id = (select auth.uid())
    returning p.id, p.account_status, p.updated_at;
end;
$$;

revoke all on function public.request_account_deactivation() from public, anon, authenticated;
grant execute on function public.request_account_deactivation() to authenticated;
