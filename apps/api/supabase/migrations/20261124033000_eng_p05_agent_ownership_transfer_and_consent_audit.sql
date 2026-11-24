-- ENG-P05: explicit two-party Agent ownership transfer and immutable consent/audit history.
create table if not exists public.agent_ownership_transfer_requests (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  from_owner_user_id uuid not null references auth.users(id) on delete restrict,
  to_owner_user_id uuid not null references auth.users(id) on delete restrict,
  status text not null default 'pending' check (status in ('pending','accepted','rejected','cancelled','expired')),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  expires_at timestamptz not null default (clock_timestamp()+interval '7 days'),
  responded_at timestamptz,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  constraint agent_ownership_transfer_distinct_users check(from_owner_user_id<>to_owner_user_id),
  constraint agent_ownership_transfer_response_state check (
    (status='pending' and responded_at is null) or
    (status<>'pending' and responded_at is not null)
  ),
  constraint agent_ownership_transfer_idempotency unique(from_owner_user_id,idempotency_key)
);
create unique index if not exists agent_ownership_transfer_one_pending_per_agent
  on public.agent_ownership_transfer_requests(agent_id) where status='pending';
create index if not exists agent_ownership_transfer_incoming_idx
  on public.agent_ownership_transfer_requests(to_owner_user_id,status,created_at desc);
create index if not exists agent_ownership_transfer_outgoing_idx
  on public.agent_ownership_transfer_requests(from_owner_user_id,status,created_at desc);

create table if not exists public.agent_ownership_transfer_events (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.agent_ownership_transfer_requests(id) on delete restrict,
  agent_id uuid not null references public.ai_agents(id) on delete restrict,
  event_type text not null check(event_type in ('requested','accepted','rejected','cancelled','expired')),
  actor_user_id uuid references auth.users(id) on delete set null,
  from_owner_user_id uuid not null references auth.users(id) on delete restrict,
  to_owner_user_id uuid not null references auth.users(id) on delete restrict,
  details jsonb not null default '{}'::jsonb check(jsonb_typeof(details)='object'),
  created_at timestamptz not null default clock_timestamp(),
  constraint agent_ownership_transfer_event_once unique(request_id,event_type)
);

create table if not exists public.agent_owner_attribution_consent_events (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete restrict,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  event_type text not null check(event_type in ('granted','revoked')),
  consent_version integer not null check(consent_version>0),
  disclosure_snapshot jsonb not null check(jsonb_typeof(disclosure_snapshot)='object'),
  created_at timestamptz not null default clock_timestamp()
);
create index if not exists agent_owner_attribution_consent_agent_idx
  on public.agent_owner_attribution_consent_events(agent_id,created_at desc);

alter table public.agent_ownership_transfer_requests enable row level security;
alter table public.agent_ownership_transfer_events enable row level security;
alter table public.agent_owner_attribution_consent_events enable row level security;
revoke all on table public.agent_ownership_transfer_requests,public.agent_ownership_transfer_events,public.agent_owner_attribution_consent_events from public,anon,authenticated;
grant select on table public.agent_ownership_transfer_requests,public.agent_ownership_transfer_events,public.agent_owner_attribution_consent_events to authenticated;
grant all on table public.agent_ownership_transfer_requests,public.agent_ownership_transfer_events,public.agent_owner_attribution_consent_events to service_role;

drop policy if exists agent_ownership_transfer_requests_select_parties on public.agent_ownership_transfer_requests;
create policy agent_ownership_transfer_requests_select_parties on public.agent_ownership_transfer_requests
for select to authenticated using ((select auth.uid()) in (from_owner_user_id,to_owner_user_id));
drop policy if exists agent_ownership_transfer_events_select_parties on public.agent_ownership_transfer_events;
create policy agent_ownership_transfer_events_select_parties on public.agent_ownership_transfer_events
for select to authenticated using (
  exists(select 1 from public.agent_ownership_transfer_requests r
    where r.id=request_id and (select auth.uid()) in (r.from_owner_user_id,r.to_owner_user_id))
);
drop policy if exists agent_owner_attribution_consent_select_owner on public.agent_owner_attribution_consent_events;
create policy agent_owner_attribution_consent_select_owner on public.agent_owner_attribution_consent_events
for select to authenticated using (private.has_agent_ownership(agent_id,(select auth.uid()),'owner'));

create or replace function private.capture_agent_owner_attribution_consent()
returns trigger language plpgsql security definer set search_path=''
as $function$
declare v_owner uuid; v_event text;
begin
  if tg_op<>'UPDATE' or old.public_owner_attribution is not distinct from new.public_owner_attribution then
    return new;
  end if;
  select o.owner_user_id into v_owner
    from public.agent_ownerships o
   where o.agent_id=new.id and o.ownership_role='owner' and o.status='active'
   order by o.created_at desc limit 1;
  if v_owner is null then
    raise exception 'AGENT_ACTIVE_OWNER_REQUIRED_FOR_ATTRIBUTION_CONSENT' using errcode='42501';
  end if;
  if new.public_owner_attribution and auth.uid() is distinct from v_owner then
    raise exception 'AGENT_OWNER_CONSENT_MUST_BE_GRANTED_BY_CURRENT_OWNER' using errcode='42501';
  end if;
  v_event:=case when new.public_owner_attribution then 'granted' else 'revoked' end;
  insert into public.agent_owner_attribution_consent_events(
    agent_id,owner_user_id,event_type,consent_version,disclosure_snapshot
  ) values(
    new.id,v_owner,v_event,coalesce(new.version,1),
    jsonb_build_object(
      'agent_version',new.version,
      'agent_visibility',new.visibility,
      'owner_profile_visibility',(select p.visibility from public.profiles p where p.id=v_owner),
      'disclosure',new.disclosure,
      'public_owner_attribution',new.public_owner_attribution,
      'consent_actor',auth.uid()
    )
  );
  return new;
end;
$function$;
revoke all on function private.capture_agent_owner_attribution_consent() from public,anon,authenticated;
drop trigger if exists ai_agents_capture_owner_attribution_consent on public.ai_agents;
create trigger ai_agents_capture_owner_attribution_consent
after update of public_owner_attribution on public.ai_agents
for each row execute function private.capture_agent_owner_attribution_consent();

create or replace function public.request_agent_ownership_transfer(
  p_agent_id uuid,p_recipient_user_id uuid,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
  v_actor uuid:=auth.uid();
  v_agent public.ai_agents%rowtype;
  v_request public.agent_ownership_transfer_requests%rowtype;
begin
  if v_actor is null or coalesce(auth.role(),'')<>'authenticated' then
    raise exception 'AUTHENTICATED_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if p_agent_id is null or p_recipient_user_id is null or p_recipient_user_id=v_actor
     or p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'AGENT_OWNERSHIP_TRANSFER_ARGUMENTS_INVALID' using errcode='22023';
  end if;
  select * into v_agent from public.ai_agents a where a.id=p_agent_id for update;
  if not found or not private.has_agent_ownership(p_agent_id,v_actor,'owner') then
    raise exception 'AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if v_agent.status='archived' then
    raise exception 'ARCHIVED_AGENT_CANNOT_BE_TRANSFERRED' using errcode='23514';
  end if;
  if exists(select 1 from public.official_agent_bots b where b.agent_id=p_agent_id and b.status in ('active','approved')) then
    raise exception 'OFFICIAL_AGENT_OWNERSHIP_IS_SYSTEM_MANAGED' using errcode='42501';
  end if;
  if not exists(select 1 from public.profiles p where p.id=p_recipient_user_id and p.account_status='active') then
    raise exception 'AGENT_TRANSFER_RECIPIENT_NOT_ACTIVE' using errcode='23514';
  end if;
  if exists(select 1 from public.agent_ownerships o where o.agent_id=p_agent_id and o.owner_user_id=p_recipient_user_id and o.ownership_role='owner' and o.status='active') then
    raise exception 'RECIPIENT_ALREADY_OWNS_AGENT' using errcode='23505';
  end if;

  select * into v_request from public.agent_ownership_transfer_requests r
   where r.from_owner_user_id=v_actor and r.idempotency_key=p_idempotency_key;
  if found then
    if v_request.agent_id<>p_agent_id or v_request.to_owner_user_id<>p_recipient_user_id then
      raise exception 'AGENT_TRANSFER_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('request_id',v_request.id,'agent_id',p_agent_id,'status',v_request.status,'expires_at',v_request.expires_at);
  end if;

  insert into public.agent_ownership_transfer_requests(agent_id,from_owner_user_id,to_owner_user_id,idempotency_key)
  values(p_agent_id,v_actor,p_recipient_user_id,p_idempotency_key)
  returning * into v_request;
  insert into public.agent_ownership_transfer_events(request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id)
  values(v_request.id,p_agent_id,'requested',v_actor,v_actor,p_recipient_user_id);
  return jsonb_build_object('request_id',v_request.id,'agent_id',p_agent_id,'status',v_request.status,'expires_at',v_request.expires_at);
end;
$function$;

create or replace function public.respond_agent_ownership_transfer(
  p_request_id uuid,p_accept boolean
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
  v_actor uuid:=auth.uid();
  v_request public.agent_ownership_transfer_requests%rowtype;
  v_agent public.ai_agents%rowtype;
begin
  if v_actor is null or coalesce(auth.role(),'')<>'authenticated' then
    raise exception 'AUTHENTICATED_RECIPIENT_REQUIRED' using errcode='42501';
  end if;
  select * into v_request from public.agent_ownership_transfer_requests r
   where r.id=p_request_id for update;
  if not found or v_request.to_owner_user_id<>v_actor or v_request.status<>'pending' then
    raise exception 'AGENT_TRANSFER_REQUEST_UNAVAILABLE' using errcode='42501';
  end if;
  if v_request.expires_at<=clock_timestamp() then
    update public.agent_ownership_transfer_requests set status='expired',responded_at=clock_timestamp(),updated_at=clock_timestamp() where id=v_request.id;
    insert into public.agent_ownership_transfer_events(request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id)
    values(v_request.id,v_request.agent_id,'expired',v_actor,v_request.from_owner_user_id,v_request.to_owner_user_id)
    on conflict(request_id,event_type) do nothing;
    return jsonb_build_object('request_id',v_request.id,'status','expired');
  end if;
  select * into v_agent from public.ai_agents a where a.id=v_request.agent_id for update;
  if not found or not exists(select 1 from public.profiles p where p.id=v_actor and p.account_status='active') then
    raise exception 'AGENT_TRANSFER_AGENT_OR_RECIPIENT_UNAVAILABLE' using errcode='23514';
  end if;
  if p_accept then
    if not exists(select 1 from public.agent_ownerships o where o.agent_id=v_request.agent_id and o.owner_user_id=v_request.from_owner_user_id and o.ownership_role='owner' and o.status='active') then
      raise exception 'CURRENT_AGENT_OWNER_CHANGED' using errcode='40001';
    end if;
    if exists(select 1 from public.official_agent_bots b where b.agent_id=v_request.agent_id and b.status in ('active','approved')) then
      raise exception 'OFFICIAL_AGENT_OWNERSHIP_IS_SYSTEM_MANAGED' using errcode='42501';
    end if;

    update public.agent_ownerships
       set status='revoked'
     where agent_id=v_request.agent_id and owner_user_id=v_request.from_owner_user_id
       and ownership_role='owner' and status='active';
    insert into public.agent_ownerships(agent_id,owner_user_id,ownership_role,status)
    values(v_request.agent_id,v_actor,'owner','active')
    on conflict(agent_id,owner_user_id) do update set ownership_role='owner',status='active';

    update public.agent_consumer_grants
       set status='revoked',revoked_by=v_request.from_owner_user_id,revoked_at=clock_timestamp(),
           revoke_reason='agent_ownership_transferred',updated_at=clock_timestamp()
     where agent_id=v_request.agent_id and owner_user_id=v_request.from_owner_user_id and status='active';
    update public.agent_resource_grants
       set status='revoked',revoked_by=v_request.from_owner_user_id,revoked_at=clock_timestamp(),
           revocation_reason='agent_ownership_transferred',updated_at=clock_timestamp()
     where agent_id=v_request.agent_id and status='active';
    update public.agent_runtime_policies
       set status='revoked',revoked_by=v_request.from_owner_user_id,revoked_at=clock_timestamp()
     where agent_id=v_request.agent_id and status='approved';
    update public.agent_social_presence_policies
       set is_enabled=false,revoked_at=clock_timestamp(),updated_at=clock_timestamp()
     where agent_id=v_request.agent_id and owner_user_id=v_request.from_owner_user_id and is_enabled=true;

    update public.ai_agents
       set visibility='private',status='draft',public_owner_attribution=false,updated_at=clock_timestamp()
     where id=v_request.agent_id;
    update public.agent_ownership_transfer_requests
       set status='accepted',responded_at=clock_timestamp(),updated_at=clock_timestamp()
     where id=v_request.id;
    insert into public.agent_ownership_transfer_events(request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id,details)
    values(v_request.id,v_request.agent_id,'accepted',v_actor,v_request.from_owner_user_id,v_actor,
      jsonb_build_object('revoked_consumer_grants',true,'revoked_resource_grants',true,'revoked_runtime_policies',true,'disabled_social_presence',true,'publication_reset',true));
    return jsonb_build_object('request_id',v_request.id,'agent_id',v_request.agent_id,'status','accepted','new_owner_user_id',v_actor);
  end if;

  update public.agent_ownership_transfer_requests
     set status='rejected',responded_at=clock_timestamp(),updated_at=clock_timestamp()
   where id=v_request.id;
  insert into public.agent_ownership_transfer_events(request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id)
  values(v_request.id,v_request.agent_id,'rejected',v_actor,v_request.from_owner_user_id,v_actor);
  return jsonb_build_object('request_id',v_request.id,'agent_id',v_request.agent_id,'status','rejected');
end;
$function$;

create or replace function public.cancel_agent_ownership_transfer(
  p_request_id uuid
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
  v_actor uuid:=auth.uid();
  v_request public.agent_ownership_transfer_requests%rowtype;
begin
  if v_actor is null or coalesce(auth.role(),'')<>'authenticated' then
    raise exception 'AUTHENTICATED_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  select * into v_request from public.agent_ownership_transfer_requests r
   where r.id=p_request_id and r.from_owner_user_id=v_actor for update;
  if not found or v_request.status<>'pending' then
    raise exception 'AGENT_TRANSFER_REQUEST_UNAVAILABLE' using errcode='42501';
  end if;
  update public.agent_ownership_transfer_requests set status='cancelled',responded_at=clock_timestamp(),updated_at=clock_timestamp() where id=v_request.id;
  insert into public.agent_ownership_transfer_events(request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id)
  values(v_request.id,v_request.agent_id,'cancelled',v_actor,v_actor,v_request.to_owner_user_id);
  return jsonb_build_object('request_id',v_request.id,'status','cancelled');
end;
$function$;

revoke all on function public.request_agent_ownership_transfer(uuid,uuid,text) from public,anon;
revoke all on function public.respond_agent_ownership_transfer(uuid,boolean) from public,anon;
revoke all on function public.cancel_agent_ownership_transfer(uuid) from public,anon;
grant execute on function public.request_agent_ownership_transfer(uuid,uuid,text) to authenticated;
grant execute on function public.respond_agent_ownership_transfer(uuid,boolean) to authenticated;
grant execute on function public.cancel_agent_ownership_transfer(uuid) to authenticated;

