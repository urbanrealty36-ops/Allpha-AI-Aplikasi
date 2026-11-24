-- ENG-P05 forward repair: keep ownership/consent audit exportable and account-deletion safe.
alter table public.agent_ownership_transfer_requests
  add column if not exists from_owner_subject_ref text,
  add column if not exists to_owner_subject_ref text;
update public.agent_ownership_transfer_requests
   set from_owner_subject_ref=coalesce(from_owner_subject_ref,encode(extensions.digest(from_owner_user_id::text,'sha256'),'hex')),
       to_owner_subject_ref=coalesce(to_owner_subject_ref,encode(extensions.digest(to_owner_user_id::text,'sha256'),'hex'));
alter table public.agent_ownership_transfer_requests
  alter column from_owner_user_id drop not null,
  alter column to_owner_user_id drop not null;
alter table public.agent_ownership_transfer_requests
  drop constraint if exists agent_ownership_transfer_requests_from_owner_user_id_fkey,
  drop constraint if exists agent_ownership_transfer_requests_to_owner_user_id_fkey,
  drop constraint if exists agent_ownership_transfer_distinct_users;
alter table public.agent_ownership_transfer_requests
  add constraint agent_ownership_transfer_requests_from_owner_user_id_fkey foreign key(from_owner_user_id) references auth.users(id) on delete set null,
  add constraint agent_ownership_transfer_requests_to_owner_user_id_fkey foreign key(to_owner_user_id) references auth.users(id) on delete set null,
  add constraint agent_ownership_transfer_distinct_users check(from_owner_user_id is null or to_owner_user_id is null or from_owner_user_id<>to_owner_user_id),
  add constraint agent_ownership_transfer_pending_parties check(status<>'pending' or (from_owner_user_id is not null and to_owner_user_id is not null)),
  add constraint agent_ownership_transfer_subject_refs check(
    from_owner_subject_ref ~ '^[0-9a-f]{64}$' and to_owner_subject_ref ~ '^[0-9a-f]{64}$'
  );

alter table public.agent_ownership_transfer_events
  add column if not exists from_owner_subject_ref text,
  add column if not exists to_owner_subject_ref text;
update public.agent_ownership_transfer_events
   set from_owner_subject_ref=coalesce(from_owner_subject_ref,encode(extensions.digest(from_owner_user_id::text,'sha256'),'hex')),
       to_owner_subject_ref=coalesce(to_owner_subject_ref,encode(extensions.digest(to_owner_user_id::text,'sha256'),'hex'));
alter table public.agent_ownership_transfer_events
  alter column from_owner_user_id drop not null,
  alter column to_owner_user_id drop not null;
alter table public.agent_ownership_transfer_events
  drop constraint if exists agent_ownership_transfer_events_from_owner_user_id_fkey,
  drop constraint if exists agent_ownership_transfer_events_to_owner_user_id_fkey;
alter table public.agent_ownership_transfer_events
  add constraint agent_ownership_transfer_events_from_owner_user_id_fkey foreign key(from_owner_user_id) references auth.users(id) on delete set null,
  add constraint agent_ownership_transfer_events_to_owner_user_id_fkey foreign key(to_owner_user_id) references auth.users(id) on delete set null,
  add constraint agent_ownership_transfer_event_subject_refs check(
    from_owner_subject_ref ~ '^[0-9a-f]{64}$' and to_owner_subject_ref ~ '^[0-9a-f]{64}$'
  );

alter table public.agent_owner_attribution_consent_events
  add column if not exists owner_subject_ref text;
update public.agent_owner_attribution_consent_events
   set owner_subject_ref=coalesce(owner_subject_ref,encode(extensions.digest(owner_user_id::text,'sha256'),'hex'));
alter table public.agent_owner_attribution_consent_events alter column owner_user_id drop not null;
alter table public.agent_owner_attribution_consent_events
  drop constraint if exists agent_owner_attribution_consent_events_owner_user_id_fkey;
alter table public.agent_owner_attribution_consent_events
  add constraint agent_owner_attribution_consent_events_owner_user_id_fkey foreign key(owner_user_id) references auth.users(id) on delete set null,
  add constraint agent_owner_attribution_consent_subject_ref check(owner_subject_ref ~ '^[0-9a-f]{64}$');

create or replace function private.capture_agent_owner_attribution_consent()
returns trigger language plpgsql security definer set search_path=''
as $function$
declare v_owner uuid; v_event text; v_actor uuid;
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
  v_actor:=case when auth.uid()=v_owner then auth.uid() else v_owner end;
  insert into public.agent_owner_attribution_consent_events(
    agent_id,owner_user_id,owner_subject_ref,event_type,consent_version,disclosure_snapshot
  ) values(
    new.id,v_owner,encode(extensions.digest(v_owner::text,'sha256'),'hex'),v_event,coalesce(new.version,1),
    jsonb_build_object(
      'agent_version',new.version,
      'agent_visibility',new.visibility,
      'owner_profile_visibility',(select p.visibility from public.profiles p where p.id=v_owner),
      'disclosure',new.disclosure,
      'public_owner_attribution',new.public_owner_attribution,
      'consent_actor',v_actor,
      'revocation_reason',case when v_event='revoked' and auth.uid() is distinct from v_owner then 'ownership_transfer' else 'owner_action' end
    )
  );
  return new;
end;
$function$;

create or replace function public.request_agent_ownership_transfer(
  p_agent_id uuid,p_recipient_user_id uuid,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
  v_actor uuid:=auth.uid();
  v_agent public.ai_agents%rowtype;
  v_request public.agent_ownership_transfer_requests%rowtype;
  v_expired record;
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
  if v_agent.status='archived' then raise exception 'ARCHIVED_AGENT_CANNOT_BE_TRANSFERRED' using errcode='23514'; end if;
  if exists(select 1 from public.official_agent_bots b where b.agent_id=p_agent_id and b.status in ('active','approved')) then
    raise exception 'OFFICIAL_AGENT_OWNERSHIP_IS_SYSTEM_MANAGED' using errcode='42501';
  end if;
  if not exists(select 1 from public.profiles p where p.id=p_recipient_user_id and p.account_status='active') then
    raise exception 'AGENT_TRANSFER_RECIPIENT_NOT_ACTIVE' using errcode='23514';
  end if;
  if exists(select 1 from public.agent_ownerships o where o.agent_id=p_agent_id and o.owner_user_id=p_recipient_user_id and o.ownership_role='owner' and o.status='active') then
    raise exception 'RECIPIENT_ALREADY_OWNS_AGENT' using errcode='23505';
  end if;

  for v_expired in
    update public.agent_ownership_transfer_requests r
       set status='expired',responded_at=clock_timestamp(),updated_at=clock_timestamp()
     where r.agent_id=p_agent_id and r.status='pending' and r.expires_at<=clock_timestamp()
     returning r.*
  loop
    insert into public.agent_ownership_transfer_events(
      request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id,
      from_owner_subject_ref,to_owner_subject_ref
    ) values(
      v_expired.id,v_expired.agent_id,'expired',v_actor,v_expired.from_owner_user_id,v_expired.to_owner_user_id,
      v_expired.from_owner_subject_ref,v_expired.to_owner_subject_ref
    ) on conflict(request_id,event_type) do nothing;
  end loop;

  select * into v_request from public.agent_ownership_transfer_requests r
   where r.from_owner_user_id=v_actor and r.idempotency_key=p_idempotency_key;
  if found then
    if v_request.agent_id<>p_agent_id or v_request.to_owner_user_id<>p_recipient_user_id then
      raise exception 'AGENT_TRANSFER_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('request_id',v_request.id,'agent_id',p_agent_id,'status',v_request.status,'expires_at',v_request.expires_at);
  end if;

  insert into public.agent_ownership_transfer_requests(
    agent_id,from_owner_user_id,to_owner_user_id,from_owner_subject_ref,to_owner_subject_ref,idempotency_key
  ) values(
    p_agent_id,v_actor,p_recipient_user_id,
    encode(extensions.digest(v_actor::text,'sha256'),'hex'),
    encode(extensions.digest(p_recipient_user_id::text,'sha256'),'hex'),
    p_idempotency_key
  ) returning * into v_request;
  insert into public.agent_ownership_transfer_events(
    request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id,from_owner_subject_ref,to_owner_subject_ref
  ) values(
    v_request.id,p_agent_id,'requested',v_actor,v_actor,p_recipient_user_id,
    v_request.from_owner_subject_ref,v_request.to_owner_subject_ref
  );
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
  select * into v_request from public.agent_ownership_transfer_requests r where r.id=p_request_id for update;
  if not found or v_request.to_owner_user_id<>v_actor or v_request.status<>'pending' then
    raise exception 'AGENT_TRANSFER_REQUEST_UNAVAILABLE' using errcode='42501';
  end if;
  if v_request.expires_at<=clock_timestamp() then
    update public.agent_ownership_transfer_requests set status='expired',responded_at=clock_timestamp(),updated_at=clock_timestamp() where id=v_request.id;
    insert into public.agent_ownership_transfer_events(
      request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id,from_owner_subject_ref,to_owner_subject_ref
    ) values(
      v_request.id,v_request.agent_id,'expired',v_actor,v_request.from_owner_user_id,v_request.to_owner_user_id,
      v_request.from_owner_subject_ref,v_request.to_owner_subject_ref
    ) on conflict(request_id,event_type) do nothing;
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

    -- Revoke public identity/consent while the previous owner is still authoritative.
    update public.ai_agents set visibility='private',status='draft',public_owner_attribution=false,updated_at=clock_timestamp()
     where id=v_request.agent_id;
    update public.agent_ownerships set status='revoked'
     where agent_id=v_request.agent_id and owner_user_id=v_request.from_owner_user_id and ownership_role='owner' and status='active';
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

    update public.agent_ownership_transfer_requests set status='accepted',responded_at=clock_timestamp(),updated_at=clock_timestamp()
     where id=v_request.id;
    insert into public.agent_ownership_transfer_events(
      request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id,
      from_owner_subject_ref,to_owner_subject_ref,details
    ) values(
      v_request.id,v_request.agent_id,'accepted',v_actor,v_request.from_owner_user_id,v_actor,
      v_request.from_owner_subject_ref,v_request.to_owner_subject_ref,
      jsonb_build_object('revoked_consumer_grants',true,'revoked_resource_grants',true,'revoked_runtime_policies',true,'disabled_social_presence',true,'publication_reset',true)
    );
    return jsonb_build_object('request_id',v_request.id,'agent_id',v_request.agent_id,'status','accepted','new_owner_user_id',v_actor);
  end if;

  update public.agent_ownership_transfer_requests set status='rejected',responded_at=clock_timestamp(),updated_at=clock_timestamp() where id=v_request.id;
  insert into public.agent_ownership_transfer_events(
    request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id,
    from_owner_subject_ref,to_owner_subject_ref
  ) values(
    v_request.id,v_request.agent_id,'rejected',v_actor,v_request.from_owner_user_id,v_actor,
    v_request.from_owner_subject_ref,v_request.to_owner_subject_ref
  );
  return jsonb_build_object('request_id',v_request.id,'agent_id',v_request.agent_id,'status','rejected');
end;
$function$;

create or replace function public.cancel_agent_ownership_transfer(p_request_id uuid)
returns jsonb language plpgsql security definer set search_path=''
as $function$
declare v_actor uuid:=auth.uid(); v_request public.agent_ownership_transfer_requests%rowtype;
begin
  if v_actor is null or coalesce(auth.role(),'')<>'authenticated' then
    raise exception 'AUTHENTICATED_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  select * into v_request from public.agent_ownership_transfer_requests r
   where r.id=p_request_id and r.from_owner_user_id=v_actor for update;
  if not found or v_request.status<>'pending' then raise exception 'AGENT_TRANSFER_REQUEST_UNAVAILABLE' using errcode='42501'; end if;
  update public.agent_ownership_transfer_requests set status='cancelled',responded_at=clock_timestamp(),updated_at=clock_timestamp() where id=v_request.id;
  insert into public.agent_ownership_transfer_events(
    request_id,agent_id,event_type,actor_user_id,from_owner_user_id,to_owner_user_id,
    from_owner_subject_ref,to_owner_subject_ref
  ) values(
    v_request.id,v_request.agent_id,'cancelled',v_actor,v_actor,v_request.to_owner_user_id,
    v_request.from_owner_subject_ref,v_request.to_owner_subject_ref
  );
  return jsonb_build_object('request_id',v_request.id,'status','cancelled');
end;
$function$;

-- The new lifecycle records are included in the canonical export and preserved as pseudonymous audit.
insert into private.account_export_sources(source_key,table_name,filter_kind,owner_columns,sort_order,enabled)
values
 ('agent_ownership_transfer_requests','agent_ownership_transfer_requests','owner_columns',array['from_owner_user_id','to_owner_user_id'],71,true),
 ('agent_ownership_transfer_events','agent_ownership_transfer_events','owner_columns',array['actor_user_id','from_owner_user_id','to_owner_user_id'],72,true),
 ('agent_owner_attribution_consent_events','agent_owner_attribution_consent_events','owner_columns',array['owner_user_id'],73,true)
on conflict(source_key) do update set table_name=excluded.table_name,filter_kind=excluded.filter_kind,
 owner_columns=excluded.owner_columns,sort_order=excluded.sort_order,enabled=true;

insert into public.account_deletion_source_policies(
 source_key,data_class,deletion_action,dependency_order,policy_version,reason,approved_by,approved_at,active,
 table_name,filter_kind,owner_columns,decision_source,decision_reference
)
select v.source_key,'agent_operational','preserve',v.dependency_order,p.policy_version,v.reason,
 p.approved_by,p.approved_at,true,v.table_name,'owner_columns',v.owner_columns,
 p.decision_source,p.decision_reference
from (values
 ('agent_ownership_transfer_requests','agent_ownership_transfer_requests',71,array['from_owner_user_id','to_owner_user_id']::text[],
  'Transfer request state is retained as an operational audit record; user identifiers are detached by SET NULL while subject references remain pseudonymous.'),
 ('agent_ownership_transfer_events','agent_ownership_transfer_events',72,array['actor_user_id','from_owner_user_id','to_owner_user_id']::text[],
  'Immutable Agent ownership transfer events are retained as pseudonymous audit evidence.'),
 ('agent_owner_attribution_consent_events','agent_owner_attribution_consent_events',73,array['owner_user_id']::text[],
  'Agent Passport attribution consent grants and revocations are retained as pseudonymous consent evidence.')
) v(source_key,table_name,dependency_order,owner_columns,reason)
cross join lateral (select * from public.account_deletion_source_policies where source_key='agent_ownerships' limit 1) p
on conflict(source_key) do update set data_class=excluded.data_class,deletion_action=excluded.deletion_action,
 dependency_order=excluded.dependency_order,policy_version=excluded.policy_version,reason=excluded.reason,
 active=true,table_name=excluded.table_name,filter_kind=excluded.filter_kind,owner_columns=excluded.owner_columns,
 decision_source=excluded.decision_source,decision_reference=excluded.decision_reference,updated_at=clock_timestamp();

insert into public.account_deletion_dependency_rules(child_schema,child_table,constraint_name,fk_column,delete_rule,resolution_action,reason,active)
select 'public',t.relname,c.conname,a.attname,
 case c.confdeltype when 'c' then 'CASCADE' when 'n' then 'SET NULL' when 'r' then 'RESTRICT' else 'NO ACTION' end,
 case c.confdeltype when 'c' then 'database_cascade' when 'n' then 'database_set_null' else 'preserve_tombstone' end,
 'ENG-P05 ownership and consent audit FK; source policy preserves the record and detaches deleted Human identifiers where applicable.',
 true
from pg_constraint c
join pg_class t on t.oid=c.conrelid
join pg_namespace n on n.oid=t.relnamespace
join unnest(c.conkey) with ordinality k(attnum,ord) on true
join pg_attribute a on a.attrelid=t.oid and a.attnum=k.attnum
where n.nspname='public' and c.contype='f'
  and t.relname in ('agent_ownership_transfer_requests','agent_ownership_transfer_events','agent_owner_attribution_consent_events')
  and not exists(select 1 from public.account_deletion_dependency_rules r
    where r.child_schema='public' and r.child_table=t.relname and r.constraint_name=c.conname)
on conflict(child_schema,child_table,constraint_name) do update
set fk_column=excluded.fk_column,delete_rule=excluded.delete_rule,resolution_action=excluded.resolution_action,
 reason=excluded.reason,active=true;

