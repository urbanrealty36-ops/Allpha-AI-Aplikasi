-- ENG-P03: validated ownership transfer for Agent and Organization dependencies.
-- Additive/forward-only: no existing ownership is changed by this migration.
create table if not exists public.account_deletion_ownership_transfers (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.account_deletion_requests(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete restrict,
  resource_type text not null check (resource_type in ('agent','organization')),
  resource_id uuid not null,
  successor_user_id uuid not null references auth.users(id) on delete restrict,
  status text not null default 'requested' check (status in ('requested','applied','failed')),
  created_at timestamptz not null default clock_timestamp(),
  applied_at timestamptz,
  unique (request_id, resource_type, resource_id),
  check (user_id <> successor_user_id)
);

create index if not exists account_deletion_ownership_transfers_subject_idx
  on public.account_deletion_ownership_transfers(user_id, request_id, status);

alter table public.account_deletion_ownership_transfers enable row level security;
revoke all on public.account_deletion_ownership_transfers from public, anon, authenticated, service_role;

create or replace function public.set_my_account_deletion_ownership_transfer(
  p_request_id uuid,
  p_resource_type text,
  p_resource_id uuid,
  p_successor_user_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_actor uuid := auth.uid();
  v_request public.account_deletion_requests%rowtype;
begin
  if v_actor is null or coalesce(auth.role(),'') <> 'authenticated' then
    raise exception 'authenticated_account_owner_required' using errcode='42501';
  end if;
  if p_request_id is null or p_resource_id is null or p_successor_user_id is null
     or p_resource_type not in ('agent','organization') then
    raise exception 'account_deletion_transfer_arguments_invalid' using errcode='22023';
  end if;
  if p_successor_user_id = v_actor then
    raise exception 'account_deletion_transfer_successor_must_differ' using errcode='22023';
  end if;

  select * into v_request
    from public.account_deletion_requests r
   where r.id=p_request_id and r.user_id=v_actor
   for update;
  if not found or v_request.status not in ('awaiting_policy','scheduled','blocked_dependency') then
    raise exception 'account_deletion_transfer_request_unavailable' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.profiles p
     where p.id=p_successor_user_id and p.account_status='active'
  ) then
    raise exception 'account_deletion_transfer_successor_not_active' using errcode='23514';
  end if;

  if p_resource_type='agent' then
    if not exists (
      select 1 from public.agent_ownerships ao
      join public.ai_agents a on a.id=ao.agent_id
      where ao.agent_id=p_resource_id and ao.owner_user_id=v_actor
        and ao.ownership_role='owner' and ao.status='active'
    ) then
      raise exception 'account_deletion_agent_ownership_not_found' using errcode='42501';
    end if;
  elsif p_resource_type='organization' then
    if not exists (
      select 1 from public.organizations o
      join public.organization_memberships m
        on m.organization_id=o.id and m.user_id=p_successor_user_id
      where o.id=p_resource_id and o.owner_id=v_actor
    ) then
      raise exception 'account_deletion_organization_successor_must_be_member' using errcode='42501';
    end if;
  end if;

  insert into public.account_deletion_ownership_transfers(
    request_id,user_id,resource_type,resource_id,successor_user_id,status
  ) values (
    p_request_id,v_actor,p_resource_type,p_resource_id,p_successor_user_id,'requested'
  )
  on conflict (request_id,resource_type,resource_id)
  do update set successor_user_id=excluded.successor_user_id,status='requested',applied_at=null;

  return jsonb_build_object(
    'request_id',p_request_id,
    'resource_type',p_resource_type,
    'resource_id',p_resource_id,
    'successor_user_id',p_successor_user_id,
    'status','requested'
  );
end;
$$;

revoke all on function public.set_my_account_deletion_ownership_transfer(uuid,text,uuid,uuid)
  from public,anon,service_role;
grant execute on function public.set_my_account_deletion_ownership_transfer(uuid,text,uuid,uuid)
  to authenticated;

alter table public.account_deletion_dependency_rules
  drop constraint if exists account_deletion_dependency_rules_resolution_action_check;
alter table public.account_deletion_dependency_rules
  add constraint account_deletion_dependency_rules_resolution_action_check
  check (resolution_action = any (array[
    'database_cascade','database_set_null','delete_rows','set_null','block','transfer_owner'
  ]::text[]));

update public.account_deletion_dependency_rules
   set resolution_action='transfer_owner',
       reason='Ownership is transferred only to an active, prevalidated successor recorded for this deletion request; the executor rechecks current ownership and membership inside the deletion transaction.',
       updated_at=clock_timestamp()
 where active=true and constraint_name in (
   'agent_ownerships_owner_user_id_fkey',
   'organizations_owner_id_fkey'
 );

update public.account_deletion_source_policies
   set deletion_action='preserve',
       reason='Shared Agent/Organization ownership is retained and transferred by the explicit ENG-P03 ownership-transfer executor; no shared resource is deleted.',
       updated_at=clock_timestamp()
 where active=true and source_key in ('agent_ownerships','organizations_owned');

do $$
declare
  v_definition text;
  v_old text := $old$
      elsif v_step.action='block' then
        if private.account_deletion_fk_has_unresolved_user_rows(v_rule.id,v_job.user_id) then
          raise exception 'account_deletion_dependency_unresolved:%',v_rule.constraint_name using errcode='55000';
        end if;
        v_rows:=0;
      elsif v_step.action in ('delete_rows','set_null') then
$old$;
  v_new text := $new$
      elsif v_step.action='transfer_owner' then
        if v_rule.child_schema<>'public' then
          raise exception 'account_deletion_transfer_schema_unsupported:%',v_rule.constraint_name using errcode='0A000';
        end if;
        if v_rule.child_table='agent_ownerships' and v_rule.fk_column='owner_user_id' then
          update public.agent_ownerships ao
             set owner_user_id=t.successor_user_id
            from public.account_deletion_ownership_transfers t
           where t.request_id=v_job.request_id and t.user_id=v_job.user_id
             and t.resource_type='agent' and t.resource_id=ao.agent_id
             and t.status='requested' and ao.owner_user_id=v_job.user_id
             and ao.ownership_role='owner' and ao.status='active'
             and exists(select 1 from public.profiles p
               where p.id=t.successor_user_id and p.account_status='active');
          get diagnostics v_rows=row_count;
          if exists(select 1 from public.account_deletion_ownership_transfers t
            where t.request_id=v_job.request_id and t.user_id=v_job.user_id
              and t.resource_type='agent' and t.status='requested'
              and not exists(select 1 from public.agent_ownerships ao
                where ao.agent_id=t.resource_id and ao.owner_user_id=t.successor_user_id
                  and ao.ownership_role='owner' and ao.status='active')) then
            raise exception 'account_deletion_agent_transfer_incomplete' using errcode='55000';
          end if;
        elsif v_rule.child_table='organizations' and v_rule.fk_column='owner_id' then
          update public.organizations o
             set owner_id=t.successor_user_id,updated_at=clock_timestamp()
            from public.account_deletion_ownership_transfers t
           where t.request_id=v_job.request_id and t.user_id=v_job.user_id
             and t.resource_type='organization' and t.resource_id=o.id
             and t.status='requested' and o.owner_id=v_job.user_id
             and exists(select 1 from public.profiles p
               where p.id=t.successor_user_id and p.account_status='active')
             and exists(select 1 from public.organization_memberships m
               where m.organization_id=o.id and m.user_id=t.successor_user_id);
          get diagnostics v_rows=row_count;
          if exists(select 1 from public.account_deletion_ownership_transfers t
            where t.request_id=v_job.request_id and t.user_id=v_job.user_id
              and t.resource_type='organization' and t.status='requested'
              and not exists(select 1 from public.organizations o
                where o.id=t.resource_id and o.owner_id=t.successor_user_id)
              ) then
            raise exception 'account_deletion_organization_transfer_incomplete' using errcode='55000';
          end if;
        else
          raise exception 'account_deletion_transfer_handler_missing:%',v_rule.constraint_name using errcode='0A000';
        end if;
        update public.account_deletion_ownership_transfers t
           set status='applied',applied_at=clock_timestamp()
         where t.request_id=v_job.request_id and t.user_id=v_job.user_id
           and t.status='requested'
           and ((t.resource_type='agent' and not exists(
             select 1 from public.agent_ownerships ao
              where ao.agent_id=t.resource_id and ao.owner_user_id=v_job.user_id))
             or (t.resource_type='organization' and not exists(
             select 1 from public.organizations o
              where o.id=t.resource_id and o.owner_id=v_job.user_id)));
      elsif v_step.action='block' then
        if private.account_deletion_fk_has_unresolved_user_rows(v_rule.id,v_job.user_id) then
          raise exception 'account_deletion_dependency_unresolved:%',v_rule.constraint_name using errcode='55000';
        end if;
        v_rows:=0;
      elsif v_step.action in ('delete_rows','set_null') then
$new$;
begin
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  if position(v_new in v_definition)>0 then return; end if;
  if position(v_old in v_definition)=0 then
    raise exception 'account_deletion_transfer_executor_patch_anchor_missing';
  end if;
  execute replace(v_definition,v_old,v_new);
end;
$$;
