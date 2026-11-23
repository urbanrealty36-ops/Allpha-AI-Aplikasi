-- ENG-P04: revalidate both typed node owners at request acceptance and edge creation.
create or replace function public.enforce_social_edge_policy()
returns trigger
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_actor_role text;
  v_target_visibility text;
  v_target_status text;
  v_target_account_status text;
  v_same_node boolean;
begin
  if tg_op='UPDATE' then
    if old.edge_type <> 'follow' or old.status <> 'requested' or new.status <> 'active'
       or new.target_user_id is distinct from (select auth.uid())
       or old.actor_user_id is distinct from new.actor_user_id
       or old.target_user_id is distinct from new.target_user_id
       or old.actor_node_type is distinct from new.actor_node_type
       or old.target_node_type is distinct from new.target_node_type
       or old.actor_agent_id is distinct from new.actor_agent_id
       or old.target_agent_id is distinct from new.target_agent_id
       or old.edge_type is distinct from new.edge_type
       or old.idempotency_key is distinct from new.idempotency_key then
      raise exception using errcode='42501', message='only target owner may accept immutable follow request';
    end if;

    if not exists (select 1 from public.profiles p where p.id=new.target_user_id and p.account_status='active') then
      raise exception using errcode='42501', message='target human owner is no longer active';
    end if;
    if new.actor_node_type='agent' and not exists (
      select 1 from public.agent_ownerships o
      join public.ai_agents a on a.id=o.agent_id
      join public.profiles p on p.id=o.owner_user_id and p.account_status='active'
      where o.agent_id=new.actor_agent_id and o.owner_user_id=new.actor_user_id
        and o.status='active' and o.ownership_role in ('owner','operator') and a.status='active'
    ) then
      raise exception using errcode='42501', message='requesting agent authority is no longer active';
    elsif new.actor_node_type='human' and not exists (
      select 1 from public.profiles p where p.id=new.actor_user_id and p.account_status='active'
    ) then
      raise exception using errcode='42501', message='requesting human account is no longer active';
    end if;
    if new.target_node_type='agent' and not exists (
      select 1 from public.agent_ownerships o
      join public.ai_agents a on a.id=o.agent_id
      join public.profiles p on p.id=o.owner_user_id and p.account_status='active'
      where o.agent_id=new.target_agent_id and o.owner_user_id=new.target_user_id
        and o.ownership_role='owner' and o.status='active' and a.status='active'
    ) then
      raise exception using errcode='42501', message='target agent ownership is no longer active';
    end if;
    return new;
  end if;

  if new.actor_user_id is distinct from (select auth.uid()) then
    raise exception using errcode='42501', message='social graph actor principal mismatch';
  end if;
  if new.actor_node_type='human' then
    if new.actor_agent_id is not null then
      raise exception using errcode='23514', message='human actor cannot reference agent id';
    end if;
    if not exists (select 1 from public.profiles p where p.id=new.actor_user_id and p.account_status='active') then
      raise exception using errcode='42501', message='actor human account is not active';
    end if;
  else
    select o.ownership_role into v_actor_role
      from public.agent_ownerships o
      join public.ai_agents a on a.id=o.agent_id
      join public.profiles p on p.id=o.owner_user_id and p.account_status='active'
     where o.agent_id=new.actor_agent_id and o.owner_user_id=new.actor_user_id
       and o.status='active' and o.ownership_role in ('owner','operator') and a.status='active';
    if not found then
      raise exception using errcode='42501', message='active agent ownership or delegated operator permission required';
    end if;
    if new.edge_type='block' and v_actor_role <> 'owner' then
      raise exception using errcode='42501', message='agent owner approval required for block';
    end if;
  end if;

  if new.target_node_type='human' then
    if new.target_agent_id is not null then
      raise exception using errcode='23514', message='human target cannot reference agent id';
    end if;
    select p.visibility,p.account_status into v_target_visibility,v_target_account_status
      from public.profiles p where p.id=new.target_user_id;
    if not found or v_target_account_status <> 'active' or v_target_visibility not in ('public','private') then
      raise exception using errcode='42501', message='target human is unavailable';
    end if;
  else
    select a.visibility,a.status into v_target_visibility,v_target_status
      from public.ai_agents a
      join public.agent_ownerships o on o.agent_id=a.id and o.owner_user_id=new.target_user_id
        and o.ownership_role='owner' and o.status='active'
      join public.profiles p on p.id=o.owner_user_id and p.account_status='active'
     where a.id=new.target_agent_id;
    if not found or v_target_status <> 'active' or v_target_visibility not in ('public','private') then
      raise exception using errcode='42501', message='target agent is unavailable or not published';
    end if;
  end if;

  v_same_node := new.actor_node_type=new.target_node_type
    and coalesce(new.actor_agent_id,new.actor_user_id)=coalesce(new.target_agent_id,new.target_user_id);
  if v_same_node then
    raise exception using errcode='23514', message='social edge cannot target the same node';
  end if;

  if new.edge_type='follow' then
    if exists (select 1 from public.social_edges e where e.edge_type='block' and e.status='active'
      and e.actor_node_type=new.target_node_type and coalesce(e.actor_agent_id,e.actor_user_id)=coalesce(new.target_agent_id,new.target_user_id)
      and e.target_node_type=new.actor_node_type and coalesce(e.target_agent_id,e.target_user_id)=coalesce(new.actor_agent_id,new.actor_user_id))
    or exists (select 1 from public.social_edges e where e.edge_type='block' and e.status='active'
      and e.actor_node_type=new.actor_node_type and coalesce(e.actor_agent_id,e.actor_user_id)=coalesce(new.actor_agent_id,new.actor_user_id)
      and e.target_node_type=new.target_node_type and coalesce(e.target_agent_id,e.target_user_id)=coalesce(new.target_agent_id,new.target_user_id)) then
      raise exception using errcode='42501', message='follow disallowed by block';
    end if;
    new.status := case when v_target_visibility='private' then 'requested' else 'active' end;
  elsif new.edge_type='block' then
    new.status := 'active';
    delete from public.social_edges e where e.edge_type='follow' and (
      (e.actor_node_type=new.actor_node_type and coalesce(e.actor_agent_id,e.actor_user_id)=coalesce(new.actor_agent_id,new.actor_user_id)
       and e.target_node_type=new.target_node_type and coalesce(e.target_agent_id,e.target_user_id)=coalesce(new.target_agent_id,new.target_user_id))
      or
      (e.actor_node_type=new.target_node_type and coalesce(e.actor_agent_id,e.actor_user_id)=coalesce(new.target_agent_id,new.target_user_id)
       and e.target_node_type=new.actor_node_type and coalesce(e.target_agent_id,e.target_user_id)=coalesce(new.actor_agent_id,new.actor_user_id)));
  else
    new.status := 'active';
  end if;
  return new;
end
$function$;

revoke all on function public.enforce_social_edge_policy() from public,anon,authenticated;
comment on function public.enforce_social_edge_policy() is
  'ENG-P04: validates active Human account, Agent owner/operator delegation, target ownership, privacy and typed node identity on insert and follow acceptance.';
