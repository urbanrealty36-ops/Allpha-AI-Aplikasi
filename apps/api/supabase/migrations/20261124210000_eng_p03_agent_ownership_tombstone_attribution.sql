-- ENG-P03: provision pseudonymous identity subjects on every Auth signup and
-- make Agent ownership transfers request-scoped, active-owner validated and bulk-safe.

create or replace function private.ensure_account_identity_subject_from_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare v_subject_ref text;
begin
  v_subject_ref := encode(extensions.digest(new.id::text,'sha256'),'hex');
  insert into private.account_identity_subjects(subject_id,subject_ref,status)
  values(new.id,v_subject_ref,'active')
  on conflict(subject_id) do nothing;

  if not exists (
    select 1 from private.account_identity_subjects s
     where s.subject_id=new.id and s.subject_ref=v_subject_ref and s.status='active'
  ) then
    raise exception 'account_identity_subject_not_active' using errcode='23514';
  end if;
  return new;
end;
$$;
revoke all on function private.ensure_account_identity_subject_from_auth_user() from public,anon,authenticated,service_role;

drop trigger if exists on_auth_user_created_account_identity_subject on auth.users;
create trigger on_auth_user_created_account_identity_subject
after insert on auth.users
for each row execute function private.ensure_account_identity_subject_from_auth_user();

insert into private.account_identity_subjects(subject_id,subject_ref,status)
select u.id,encode(extensions.digest(u.id::text,'sha256'),'hex'),'active'
from auth.users u
on conflict(subject_id) do nothing;

do $$
begin
  if exists (
    select 1 from auth.users u
    left join private.account_identity_subjects s on s.subject_id=u.id
    where s.subject_id is null or s.status<>'active'
      or s.subject_ref<>encode(extensions.digest(u.id::text,'sha256'),'hex')
  ) then
    raise exception 'account_identity_subject_backfill_incomplete';
  end if;
end;
$$;

do $$
declare
  v_definition text;
  v_old text;
  v_new text;
begin
  -- Per-resource Agent transfer only accepts a current owner, not an editor/revoked row.
  v_definition:=pg_get_functiondef('public.set_my_account_deletion_ownership_transfer(uuid,text,uuid,uuid)'::regprocedure);
  v_old:='where ao.agent_id=p_resource_id and ao.owner_user_id=v_actor';
  v_new:=v_old||' and ao.ownership_role=''owner'' and ao.status=''active''';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_rpc_validation_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  v_definition:=replace(v_definition,'encode(digest(u.id::text,','encode(extensions.digest(u.id::text,');
  execute v_definition;

  -- Governance requires transfer instructions for every active Agent owner row.
  v_definition:=pg_get_functiondef('public.prepare_account_deletion_execution(uuid)'::regprocedure);
  v_old:='where ao.owner_user_id=v_request.user_id';
  v_new:=v_old||' and ao.ownership_role=''owner'' and ao.status=''active''';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_prepare_validation_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  execute v_definition;

  -- The executor transfers only verified active owner rows and fences stale/conflicting targets.
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  v_old:='and t.status=''requested'' and ao.owner_user_id=v_job.user_id';
  v_new:=v_old||' and ao.ownership_role=''owner'' and ao.status=''active''';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_executor_update_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;

  v_old:='where ao.agent_id=t.resource_id and ao.owner_user_id=t.successor_user_id';
  v_new:=v_old||' and ao.ownership_role=''owner'' and ao.status=''active''';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_executor_fence_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;

  v_old:=$old$
          update public.agent_ownerships ao
             set owner_user_id=t.successor_user_id
            from public.account_deletion_ownership_transfers t
$old$;
  v_new:=$new$
          if exists(
            select 1 from public.account_deletion_ownership_transfers t
            join public.agent_ownerships target
              on target.agent_id=t.resource_id and target.owner_user_id=t.successor_user_id
            where t.request_id=v_job.request_id and t.user_id=v_job.user_id
              and t.resource_type='agent' and t.status='requested'
          ) then
            raise exception 'account_deletion_agent_successor_conflict' using errcode='23505';
          end if;
          update public.agent_ownerships ao
             set owner_user_id=t.successor_user_id
            from public.account_deletion_ownership_transfers t
$new$;
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_executor_conflict_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  execute v_definition;
end;
$$;

create or replace function public.set_my_account_deletion_agent_ownership_transfers(
  p_request_id uuid,
  p_successor_user_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_actor uuid:=auth.uid();
  v_request public.account_deletion_requests%rowtype;
  v_count integer;
begin
  if v_actor is null or coalesce(auth.role(),'')<>'authenticated' then
    raise exception 'authenticated_account_owner_required' using errcode='42501';
  end if;
  if p_request_id is null or p_successor_user_id is null or p_successor_user_id=v_actor then
    raise exception 'account_deletion_transfer_arguments_invalid' using errcode='22023';
  end if;

  select * into v_request from public.account_deletion_requests r
   where r.id=p_request_id and r.user_id=v_actor for update;
  if not found or v_request.status not in ('awaiting_policy','scheduled','blocked_dependency') then
    raise exception 'account_deletion_transfer_request_unavailable' using errcode='42501';
  end if;
  if not exists(select 1 from public.profiles p
    where p.id=p_successor_user_id and p.account_status='active') then
    raise exception 'account_deletion_transfer_successor_not_active' using errcode='23514';
  end if;

  insert into private.account_identity_subjects(subject_id,subject_ref,status)
  select u.id,encode(extensions.digest(u.id::text,'sha256'),'hex'),'active'
    from auth.users u where u.id in (v_actor,p_successor_user_id)
  on conflict(subject_id) do nothing;
  if (select count(*) from private.account_identity_subjects s
      where s.subject_id in (v_actor,p_successor_user_id) and s.status='active')<>2 then
    raise exception 'account_deletion_transfer_identity_subject_unavailable' using errcode='23514';
  end if;

  select count(*) into v_count
    from public.agent_ownerships ao
   where ao.owner_user_id=v_actor and ao.ownership_role='owner' and ao.status='active';

  if exists(
    select 1 from public.agent_ownerships actor_row
    join public.agent_ownerships successor_row
      on successor_row.agent_id=actor_row.agent_id
     and successor_row.owner_user_id=p_successor_user_id
   where actor_row.owner_user_id=v_actor
     and actor_row.ownership_role='owner' and actor_row.status='active'
  ) then
    raise exception 'account_deletion_agent_successor_conflict' using errcode='23505';
  end if;

  insert into public.account_deletion_ownership_transfers(
    request_id,user_id,resource_type,resource_id,successor_user_id,status
  )
  select p_request_id,v_actor,'agent',ao.agent_id,p_successor_user_id,'requested'
    from public.agent_ownerships ao
   where ao.owner_user_id=v_actor and ao.ownership_role='owner' and ao.status='active'
  on conflict(request_id,resource_type,resource_id)
  do update set successor_user_id=excluded.successor_user_id,status='requested',applied_at=null;

  return jsonb_build_object(
    'request_id',p_request_id,'resource_type','agent',
    'successor_user_id',p_successor_user_id,'status','requested',
    'transferred_count',v_count
  );
end;
$$;
revoke all on function public.set_my_account_deletion_agent_ownership_transfers(uuid,uuid) from public,anon,service_role;
grant execute on function public.set_my_account_deletion_agent_ownership_transfers(uuid,uuid) to authenticated;
