-- ENG-P04: commit relationship notifications as an idempotent side effect of the durable graph outbox.
create or replace function public.apply_social_graph_event_effect(p_event_id uuid, p_lease_token uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_event public.social_graph_events%rowtype;
  v_inserted integer;
  v_recipient uuid;
  v_title text;
  v_body text;
  v_social_enabled boolean := true;
begin
  select * into v_event
    from public.social_graph_events
   where id = p_event_id
     and delivery_state = 'processing'
     and lease_token = p_lease_token
     and lease_expires_at > pg_catalog.now()
   for update;
  if not found then return false; end if;

  insert into public.social_graph_event_effects(event_id,effect_key,affected_viewer_id,details)
  values (
    v_event.id,
    'invalidate_viewer_feed_snapshots',
    v_event.actor_user_id,
    pg_catalog.jsonb_build_object('event_type',v_event.event_type,'target_user_id',v_event.target_user_id)
  )
  on conflict(event_id) do nothing;
  get diagnostics v_inserted = row_count;
  if v_inserted = 1 then
    update public.feed_snapshots
       set invalidated_at = coalesce(invalidated_at,pg_catalog.now())
     where invalidated_at is null
       and viewer_user_id in (v_event.actor_user_id,v_event.target_user_id);
  end if;

  if v_event.event_type = 'social.follow.created' then
    v_recipient := v_event.target_user_id;
    v_title := 'Pengikut baru';
    v_body := 'Seseorang mulai mengikuti profil Anda.';
  elsif v_event.event_type = 'social.follow.requested' then
    v_recipient := v_event.target_user_id;
    v_title := 'Permintaan mengikuti';
    v_body := 'Seseorang meminta mengikuti profil privat Anda.';
  elsif v_event.event_type = 'social.follow.accepted' then
    v_recipient := v_event.actor_user_id;
    v_title := 'Permintaan diterima';
    v_body := 'Permintaan mengikuti Anda telah diterima.';
  else
    v_recipient := null;
  end if;

  if v_recipient is not null then
    select coalesce((s.notification_preferences ->> 'social_activity')::boolean,true)
      into v_social_enabled
      from public.user_settings s
     where s.user_id = v_recipient;
    v_social_enabled := coalesce(v_social_enabled,true);
    insert into public.notifications(
      user_id,category,event_key,title,body,payload,delivery_state,attempt_count
    ) values (
      v_recipient,
      'social_activity',
      'social_graph:' || v_event.id::text,
      v_title,
      v_body,
      pg_catalog.jsonb_build_object(
        'event_id',v_event.id,
        'event_type',v_event.event_type,
        'actor_user_id',v_event.actor_user_id,
        'target_user_id',v_event.target_user_id,
        'entity_key',v_event.entity_key
      ),
      case when v_social_enabled then 'queued' else 'suppressed' end,
      0
    )
    on conflict(user_id,event_key) do nothing;
  end if;

  update public.social_graph_events
     set delivery_state='processed',
         processed_at=pg_catalog.now(),
         lease_token=null,
         lease_expires_at=null,
         last_error_code=null
   where id=v_event.id
     and delivery_state='processing'
     and lease_token=p_lease_token;
  return found;
end
$function$;

revoke all on function public.apply_social_graph_event_effect(uuid,uuid) from public, anon, authenticated;
grant execute on function public.apply_social_graph_event_effect(uuid,uuid) to service_role;
comment on function public.apply_social_graph_event_effect(uuid,uuid) is
  'ENG-P04: idempotently invalidates affected feed snapshots and enqueues privacy-aware follow notifications from graph outbox events.';
