-- ENG-P04 polymorphic Social Graph forward migration.
-- One canonical social_edges table. Legacy user IDs remain owner/principal context.
alter table public.social_edges
  add column if not exists actor_node_type text not null default 'human',
  add column if not exists target_node_type text not null default 'human',
  add column if not exists actor_agent_id uuid,
  add column if not exists target_agent_id uuid,
  add column if not exists idempotency_key text;
do $migration$
begin
  if not exists (select 1 from pg_constraint where conrelid='public.social_edges'::regclass and conname='social_edges_actor_node_type_check') then
    alter table public.social_edges add constraint social_edges_actor_node_type_check check (actor_node_type in ('human','agent'));
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_edges'::regclass and conname='social_edges_target_node_type_check') then
    alter table public.social_edges add constraint social_edges_target_node_type_check check (target_node_type in ('human','agent'));
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_edges'::regclass and conname='social_edges_actor_node_shape_check') then
    alter table public.social_edges add constraint social_edges_actor_node_shape_check check ((actor_node_type='human' and actor_agent_id is null) or (actor_node_type='agent' and actor_agent_id is not null));
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_edges'::regclass and conname='social_edges_target_node_shape_check') then
    alter table public.social_edges add constraint social_edges_target_node_shape_check check ((target_node_type='human' and target_agent_id is null) or (target_node_type='agent' and target_agent_id is not null));
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_edges'::regclass and conname='social_edges_same_node_check') then
    alter table public.social_edges add constraint social_edges_same_node_check check (not (actor_node_type=target_node_type and coalesce(actor_agent_id,actor_user_id)=coalesce(target_agent_id,target_user_id)));
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_edges'::regclass and conname='social_edges_idempotency_key_check') then
    alter table public.social_edges add constraint social_edges_idempotency_key_check check (idempotency_key is null or idempotency_key ~ '^[A-Za-z0-9._:-]{8,160}
alter table public.social_edges drop constraint if exists social_edges_unique;
create unique index if not exists social_edges_unique on public.social_edges(actor_node_type,coalesce(actor_agent_id,actor_user_id),target_node_type,coalesce(target_agent_id,target_user_id),edge_type);
create unique index if not exists social_edges_actor_idempotency_idx on public.social_edges(actor_user_id,idempotency_key) where idempotency_key is not null;
create index if not exists social_edges_actor_agent_idx on public.social_edges(actor_agent_id,edge_type,status,created_at desc) where actor_agent_id is not null;
create index if not exists social_edges_target_agent_idx on public.social_edges(target_agent_id,edge_type,status,created_at desc) where target_agent_id is not null;
create index if not exists social_edges_actor_node_idx on public.social_edges(actor_node_type,actor_user_id,created_at desc);
create index if not exists social_edges_target_node_idx on public.social_edges(target_node_type,target_user_id,created_at desc);

alter table public.social_graph_events
  add column if not exists actor_node_type text not null default 'human',
  add column if not exists target_node_type text not null default 'human',
  add column if not exists actor_agent_id uuid,
  add column if not exists target_agent_id uuid;
do $migration$
begin
  if not exists (select 1 from pg_constraint where conrelid='public.social_graph_events'::regclass and conname='social_graph_events_actor_node_type_check') then
    alter table public.social_graph_events add constraint social_graph_events_actor_node_type_check check (actor_node_type in ('human','agent'));
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_graph_events'::regclass and conname='social_graph_events_target_node_type_check') then
    alter table public.social_graph_events add constraint social_graph_events_target_node_type_check check (target_node_type in ('human','agent'));
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_graph_events'::regclass and conname='social_graph_events_actor_agent_id_fkey') then
    alter table public.social_graph_events add constraint social_graph_events_actor_agent_id_fkey foreign key (actor_agent_id) references public.ai_agents(id) on delete set null;
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_graph_events'::regclass and conname='social_graph_events_target_agent_id_fkey') then
    alter table public.social_graph_events add constraint social_graph_events_target_agent_id_fkey foreign key (target_agent_id) references public.ai_agents(id) on delete set null;
  end if;
end
$migration$;

create or replace function public.enforce_social_edge_policy()
returns trigger language plpgsql security definer set search_path = ''
as $function$
declare v_actor_role text; v_target_visibility text; v_target_status text; v_target_account_status text; v_same_node boolean;
begin
  if tg_op='UPDATE' then
    if old.edge_type <> 'follow' or old.status <> 'requested' or new.status <> 'active'
       or new.target_user_id is distinct from (select auth.uid())
       or old.actor_user_id is distinct from new.actor_user_id or old.target_user_id is distinct from new.target_user_id
       or old.actor_node_type is distinct from new.actor_node_type or old.target_node_type is distinct from new.target_node_type
       or old.actor_agent_id is distinct from new.actor_agent_id or old.target_agent_id is distinct from new.target_agent_id
       or old.edge_type is distinct from new.edge_type or old.idempotency_key is distinct from new.idempotency_key then
      raise exception using errcode='42501', message='only target owner may accept immutable follow request';
    end if;
    if new.actor_node_type='agent' and not exists (
      select 1 from public.agent_ownerships o join public.ai_agents a on a.id=o.agent_id
       where o.agent_id=new.actor_agent_id and o.owner_user_id=new.actor_user_id and o.status='active'
         and o.ownership_role in ('owner','operator') and a.status='active'
    ) then raise exception using errcode='42501', message='requesting agent authority is no longer active'; end if;
    return new;
  end if;

  if new.actor_user_id is distinct from (select auth.uid()) then
    raise exception using errcode='42501', message='social graph actor principal mismatch';
  end if;
  if new.actor_node_type='human' then
    if new.actor_agent_id is not null then raise exception using errcode='23514', message='human actor cannot reference agent id'; end if;
  else
    select o.ownership_role into v_actor_role
      from public.agent_ownerships o join public.ai_agents a on a.id=o.agent_id
     where o.agent_id=new.actor_agent_id and o.owner_user_id=new.actor_user_id and o.status='active'
       and o.ownership_role in ('owner','operator') and a.status='active';
    if not found then raise exception using errcode='42501', message='active agent ownership or delegated operator permission required'; end if;
    if new.edge_type='block' and v_actor_role <> 'owner' then raise exception using errcode='42501', message='agent owner approval required for block'; end if;
  end if;

  if new.target_node_type='human' then
    if new.target_agent_id is not null then raise exception using errcode='23514', message='human target cannot reference agent id'; end if;
    select p.visibility,p.account_status into v_target_visibility,v_target_account_status from public.profiles p where p.id=new.target_user_id;
    if not found or v_target_account_status <> 'active' or v_target_visibility not in ('public','private') then
      raise exception using errcode='42501', message='target human is unavailable';
    end if;
  else
    select a.visibility,a.status into v_target_visibility,v_target_status
      from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id and o.owner_user_id=new.target_user_id
       and o.ownership_role='owner' and o.status='active'
     where a.id=new.target_agent_id;
    if not found or v_target_status <> 'active' or v_target_visibility not in ('public','private') then
      raise exception using errcode='42501', message='target agent is unavailable or not published';
    end if;
  end if;

  v_same_node := new.actor_node_type=new.target_node_type
    and coalesce(new.actor_agent_id,new.actor_user_id)=coalesce(new.target_agent_id,new.target_user_id);
  if v_same_node then raise exception using errcode='23514', message='social edge cannot target the same node'; end if;

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
  else new.status := 'active';
  end if;
  return new;
end
$function$;
revoke all on function public.enforce_social_edge_policy() from public,anon,authenticated;
drop trigger if exists social_edges_policy_before_write on public.social_edges;
create trigger social_edges_policy_before_write before insert or update of edge_type,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,status,idempotency_key on public.social_edges for each row execute function public.enforce_social_edge_policy();

create or replace function public.capture_social_graph_event()
returns trigger language plpgsql security definer set search_path = ''
as $function$
declare v_event_type text; v_actor uuid; v_target uuid; v_actor_type text := 'human'; v_target_type text := 'human'; v_actor_agent uuid; v_target_agent uuid; v_entity_key text; v_payload jsonb;
begin
  if tg_table_name='social_edges' then
    if tg_op='DELETE' then
      v_actor:=old.actor_user_id; v_target:=old.target_user_id; v_actor_type:=old.actor_node_type; v_target_type:=old.target_node_type;
      v_actor_agent:=old.actor_agent_id; v_target_agent:=old.target_agent_id; v_entity_key:=old.edge_type;
      v_event_type:=case old.edge_type when 'follow' then 'social.follow.removed' when 'block' then 'social.block.removed' when 'mute' then 'social.mute.removed' else null end;
      v_payload:=jsonb_build_object('edge_type',old.edge_type,'previous_status',old.status);
    elsif tg_op='INSERT' then
      v_actor:=new.actor_user_id; v_target:=new.target_user_id; v_actor_type:=new.actor_node_type; v_target_type:=new.target_node_type;
      v_actor_agent:=new.actor_agent_id; v_target_agent:=new.target_agent_id; v_entity_key:=new.edge_type;
      v_event_type:=case when new.edge_type='follow' and new.status='requested' then 'social.follow.requested'
        when new.edge_type='follow' then 'social.follow.created' when new.edge_type='block' then 'social.block.created'
        when new.edge_type='mute' then 'social.mute.created' else null end;
      v_payload:=jsonb_build_object('edge_type',new.edge_type,'status',new.status);
    elsif tg_op='UPDATE' and old.status is distinct from new.status and new.edge_type='follow' and old.status='requested' and new.status='active' then
      v_actor:=new.actor_user_id; v_target:=new.target_user_id; v_actor_type:=new.actor_node_type; v_target_type:=new.target_node_type;
      v_actor_agent:=new.actor_agent_id; v_target_agent:=new.target_agent_id; v_entity_key:=new.edge_type;
      v_event_type:='social.follow.accepted'; v_payload:=jsonb_build_object('edge_type',new.edge_type,'previous_status',old.status,'status',new.status);
    else
      if tg_op='DELETE' then return old; else return new; end if;
    end if;
    if v_event_type is not null then
      insert into public.social_graph_events(event_type,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,entity_key,payload)
      values(v_event_type,v_actor,v_target,v_actor_type,v_target_type,v_actor_agent,v_target_agent,v_entity_key,
        coalesce(v_payload,'{}'::jsonb) || jsonb_build_object('actor_node_type',v_actor_type,'actor_agent_id',v_actor_agent,'target_node_type',v_target_type,'target_agent_id',v_target_agent));
    end if;
    if tg_op='DELETE' then return old; else return new; end if;
  end if;
  if tg_table_name='user_interests' then
    if tg_op='DELETE' then v_actor:=old.user_id; v_entity_key:=old.interest_key; v_event_type:='interest.preference.removed'; v_payload:=jsonb_build_object('interest_key',old.interest_key,'preference',old.preference,'data_scope','owner_private');
    elsif tg_op='INSERT' then v_actor:=new.user_id; v_entity_key:=new.interest_key; v_event_type:='interest.preference.created'; v_payload:=jsonb_build_object('interest_key',new.interest_key,'preference',new.preference,'data_scope','owner_private');
    elsif tg_op='UPDATE' and old.preference is distinct from new.preference then v_actor:=new.user_id; v_entity_key:=new.interest_key; v_event_type:='interest.preference.updated'; v_payload:=jsonb_build_object('interest_key',new.interest_key,'previous_preference',old.preference,'preference',new.preference,'data_scope','owner_private');
    else if tg_op='DELETE' then return old; else return new; end if; end if;
    insert into public.social_graph_events(event_type,actor_user_id,entity_key,payload) values(v_event_type,v_actor,v_entity_key,coalesce(v_payload,'{}'::jsonb));
    if tg_op='DELETE' then return old; else return new; end if;
  end if;
  return null;
end
$function$;
revoke all on function public.capture_social_graph_event() from public,anon,authenticated;
drop trigger if exists social_edges_capture_graph_event on public.social_edges;
create trigger social_edges_capture_graph_event after insert or update or delete on public.social_edges for each row execute function public.capture_social_graph_event();

comment on column public.social_edges.actor_user_id is 'Authenticated Human principal and audit owner context for the typed actor node.';
comment on column public.social_edges.target_user_id is 'Target Human id or canonical Agent owner id; retained for privacy, notification and feed projection compatibility.';
comment on column public.social_edges.actor_node_type is 'Typed graph node kind: human or agent.';
comment on column public.social_edges.target_node_type is 'Typed graph node kind: human or agent.';
);
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_edges'::regclass and conname='social_edges_actor_agent_id_fkey') then
    alter table public.social_edges add constraint social_edges_actor_agent_id_fkey foreign key (actor_agent_id) references public.ai_agents(id) on delete cascade;
  end if;
  if not exists (select 1 from pg_constraint where conrelid='public.social_edges'::regclass and conname='social_edges_target_agent_id_fkey') then
    alter table public.social_edges add constraint social_edges_target_agent_id_fkey foreign key (target_agent_id) references public.ai_agents(id) on delete cascade;
  end if;
end
$migration$;
alter table public.social_edges drop constraint if exists social_edges_unique;
create unique index social_edges_unique on public.social_edges(actor_node_type,coalesce(actor_agent_id,actor_user_id),target_node_type,coalesce(target_agent_id,target_user_id),edge_type);
create unique index if not exists social_edges_actor_idempotency_idx on public.social_edges(actor_user_id,idempotency_key) where idempotency_key is not null;
create index if not exists social_edges_actor_agent_idx on public.social_edges(actor_agent_id,edge_type,status,created_at desc) where actor_agent_id is not null;
create index if not exists social_edges_target_agent_idx on public.social_edges(target_agent_id,edge_type,status,created_at desc) where target_agent_id is not null;
create index if not exists social_edges_actor_node_idx on public.social_edges(actor_node_type,actor_user_id,created_at desc);
create index if not exists social_edges_target_node_idx on public.social_edges(target_node_type,target_user_id,created_at desc);

alter table public.social_graph_events
  add column if not exists actor_node_type text not null default 'human',
  add column if not exists target_node_type text not null default 'human',
  add column if not exists actor_agent_id uuid,
  add column if not exists target_agent_id uuid;
alter table public.social_graph_events
  add constraint social_graph_events_actor_node_type_check check (actor_node_type in ('human','agent')),
  add constraint social_graph_events_target_node_type_check check (target_node_type in ('human','agent')),
  add constraint social_graph_events_actor_agent_id_fkey foreign key (actor_agent_id) references public.ai_agents(id) on delete set null,
  add constraint social_graph_events_target_agent_id_fkey foreign key (target_agent_id) references public.ai_agents(id) on delete set null;

create or replace function public.enforce_social_edge_policy()
returns trigger language plpgsql security definer set search_path = ''
as $function$
declare v_actor_role text; v_target_visibility text; v_target_status text; v_target_account_status text; v_same_node boolean;
begin
  if tg_op='UPDATE' then
    if old.edge_type <> 'follow' or old.status <> 'requested' or new.status <> 'active'
       or new.target_user_id is distinct from (select auth.uid())
       or old.actor_user_id is distinct from new.actor_user_id or old.target_user_id is distinct from new.target_user_id
       or old.actor_node_type is distinct from new.actor_node_type or old.target_node_type is distinct from new.target_node_type
       or old.actor_agent_id is distinct from new.actor_agent_id or old.target_agent_id is distinct from new.target_agent_id
       or old.edge_type is distinct from new.edge_type or old.idempotency_key is distinct from new.idempotency_key then
      raise exception using errcode='42501', message='only target owner may accept immutable follow request';
    end if;
    if new.actor_node_type='agent' and not exists (
      select 1 from public.agent_ownerships o join public.ai_agents a on a.id=o.agent_id
       where o.agent_id=new.actor_agent_id and o.owner_user_id=new.actor_user_id and o.status='active'
         and o.ownership_role in ('owner','operator') and a.status='active'
    ) then raise exception using errcode='42501', message='requesting agent authority is no longer active'; end if;
    return new;
  end if;

  if new.actor_user_id is distinct from (select auth.uid()) then
    raise exception using errcode='42501', message='social graph actor principal mismatch';
  end if;
  if new.actor_node_type='human' then
    if new.actor_agent_id is not null then raise exception using errcode='23514', message='human actor cannot reference agent id'; end if;
  else
    select o.ownership_role into v_actor_role
      from public.agent_ownerships o join public.ai_agents a on a.id=o.agent_id
     where o.agent_id=new.actor_agent_id and o.owner_user_id=new.actor_user_id and o.status='active'
       and o.ownership_role in ('owner','operator') and a.status='active';
    if not found then raise exception using errcode='42501', message='active agent ownership or delegated operator permission required'; end if;
    if new.edge_type='block' and v_actor_role <> 'owner' then raise exception using errcode='42501', message='agent owner approval required for block'; end if;
  end if;

  if new.target_node_type='human' then
    if new.target_agent_id is not null then raise exception using errcode='23514', message='human target cannot reference agent id'; end if;
    select p.visibility,p.account_status into v_target_visibility,v_target_account_status from public.profiles p where p.id=new.target_user_id;
    if not found or v_target_account_status <> 'active' or v_target_visibility not in ('public','private') then
      raise exception using errcode='42501', message='target human is unavailable';
    end if;
  else
    select a.visibility,a.status into v_target_visibility,v_target_status
      from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id and o.owner_user_id=new.target_user_id
       and o.ownership_role='owner' and o.status='active'
     where a.id=new.target_agent_id;
    if not found or v_target_status <> 'active' or v_target_visibility not in ('public','private') then
      raise exception using errcode='42501', message='target agent is unavailable or not published';
    end if;
  end if;

  v_same_node := new.actor_node_type=new.target_node_type
    and coalesce(new.actor_agent_id,new.actor_user_id)=coalesce(new.target_agent_id,new.target_user_id);
  if v_same_node then raise exception using errcode='23514', message='social edge cannot target the same node'; end if;

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
  else new.status := 'active';
  end if;
  return new;
end
$function$;
revoke all on function public.enforce_social_edge_policy() from public,anon,authenticated;
drop trigger if exists social_edges_policy_before_write on public.social_edges;
create trigger social_edges_policy_before_write before insert or update of edge_type,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,status,idempotency_key on public.social_edges for each row execute function public.enforce_social_edge_policy();

create or replace function public.capture_social_graph_event()
returns trigger language plpgsql security definer set search_path = ''
as $function$
declare v_event_type text; v_actor uuid; v_target uuid; v_actor_type text := 'human'; v_target_type text := 'human'; v_actor_agent uuid; v_target_agent uuid; v_entity_key text; v_payload jsonb;
begin
  if tg_table_name='social_edges' then
    if tg_op='DELETE' then
      v_actor:=old.actor_user_id; v_target:=old.target_user_id; v_actor_type:=old.actor_node_type; v_target_type:=old.target_node_type;
      v_actor_agent:=old.actor_agent_id; v_target_agent:=old.target_agent_id; v_entity_key:=old.edge_type;
      v_event_type:=case old.edge_type when 'follow' then 'social.follow.removed' when 'block' then 'social.block.removed' when 'mute' then 'social.mute.removed' else null end;
      v_payload:=jsonb_build_object('edge_type',old.edge_type,'previous_status',old.status);
    elsif tg_op='INSERT' then
      v_actor:=new.actor_user_id; v_target:=new.target_user_id; v_actor_type:=new.actor_node_type; v_target_type:=new.target_node_type;
      v_actor_agent:=new.actor_agent_id; v_target_agent:=new.target_agent_id; v_entity_key:=new.edge_type;
      v_event_type:=case when new.edge_type='follow' and new.status='requested' then 'social.follow.requested'
        when new.edge_type='follow' then 'social.follow.created' when new.edge_type='block' then 'social.block.created'
        when new.edge_type='mute' then 'social.mute.created' else null end;
      v_payload:=jsonb_build_object('edge_type',new.edge_type,'status',new.status);
    elsif tg_op='UPDATE' and old.status is distinct from new.status and new.edge_type='follow' and old.status='requested' and new.status='active' then
      v_actor:=new.actor_user_id; v_target:=new.target_user_id; v_actor_type:=new.actor_node_type; v_target_type:=new.target_node_type;
      v_actor_agent:=new.actor_agent_id; v_target_agent:=new.target_agent_id; v_entity_key:=new.edge_type;
      v_event_type:='social.follow.accepted'; v_payload:=jsonb_build_object('edge_type',new.edge_type,'previous_status',old.status,'status',new.status);
    else
      if tg_op='DELETE' then return old; else return new; end if;
    end if;
    if v_event_type is not null then
      insert into public.social_graph_events(event_type,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,entity_key,payload)
      values(v_event_type,v_actor,v_target,v_actor_type,v_target_type,v_actor_agent,v_target_agent,v_entity_key,
        coalesce(v_payload,'{}'::jsonb) || jsonb_build_object('actor_node_type',v_actor_type,'actor_agent_id',v_actor_agent,'target_node_type',v_target_type,'target_agent_id',v_target_agent));
    end if;
    if tg_op='DELETE' then return old; else return new; end if;
  end if;
  if tg_table_name='user_interests' then
    if tg_op='DELETE' then v_actor:=old.user_id; v_entity_key:=old.interest_key; v_event_type:='interest.preference.removed'; v_payload:=jsonb_build_object('interest_key',old.interest_key,'preference',old.preference,'data_scope','owner_private');
    elsif tg_op='INSERT' then v_actor:=new.user_id; v_entity_key:=new.interest_key; v_event_type:='interest.preference.created'; v_payload:=jsonb_build_object('interest_key',new.interest_key,'preference',new.preference,'data_scope','owner_private');
    elsif tg_op='UPDATE' and old.preference is distinct from new.preference then v_actor:=new.user_id; v_entity_key:=new.interest_key; v_event_type:='interest.preference.updated'; v_payload:=jsonb_build_object('interest_key',new.interest_key,'previous_preference',old.preference,'preference',new.preference,'data_scope','owner_private');
    else if tg_op='DELETE' then return old; else return new; end if; end if;
    insert into public.social_graph_events(event_type,actor_user_id,entity_key,payload) values(v_event_type,v_actor,v_entity_key,coalesce(v_payload,'{}'::jsonb));
    if tg_op='DELETE' then return old; else return new; end if;
  end if;
  return null;
end
$function$;
revoke all on function public.capture_social_graph_event() from public,anon,authenticated;
drop trigger if exists social_edges_capture_graph_event on public.social_edges;
create trigger social_edges_capture_graph_event after insert or update or delete on public.social_edges for each row execute function public.capture_social_graph_event();

comment on column public.social_edges.actor_user_id is 'Authenticated Human principal and audit owner context for the typed actor node.';
comment on column public.social_edges.target_user_id is 'Target Human id or canonical Agent owner id; retained for privacy, notification and feed projection compatibility.';
comment on column public.social_edges.actor_node_type is 'Typed graph node kind: human or agent.';
comment on column public.social_edges.target_node_type is 'Typed graph node kind: human or agent.';
