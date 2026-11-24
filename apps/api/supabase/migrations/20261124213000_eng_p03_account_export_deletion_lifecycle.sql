-- ENG-P03: enforce export-before-deletion and the export artifact retention window.
-- No retention duration is invented here. Without an active, sourced account_export_artifact
-- policy, the request remains blocked and no account data is deleted.

alter table public.account_deletion_requests
  add column if not exists export_job_id uuid,
  add column if not exists idempotency_key text;
alter table public.account_deletion_requests
  drop constraint if exists account_deletion_requests_idempotency_key_check;
alter table public.account_deletion_requests
  add constraint account_deletion_requests_idempotency_key_check
  check (idempotency_key is null or (
    char_length(idempotency_key) between 8 and 128
    and idempotency_key ~ '^[A-Za-z0-9._:-]+$'
  ));
create unique index if not exists account_deletion_requests_user_id_idempotency_key_uidx
  on public.account_deletion_requests(user_id,idempotency_key)
  where user_id is not null and idempotency_key is not null;

drop function if exists public.create_account_deletion_request_for_actor(uuid);
create or replace function public.create_account_deletion_request_for_actor(
  p_actor_user_id uuid,
  p_idempotency_key text
) returns table(
  id uuid,
  status text,
  requested_at timestamptz,
  subject_ref text,
  export_job_id uuid,
  export_status text
)
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_request public.account_deletion_requests%rowtype;
  v_subject_ref text;
  v_request_id uuid;
  v_export_job_id uuid;
  v_export_status text;
  v_export_key text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null
     or p_idempotency_key is null
     or char_length(p_idempotency_key) not between 8 and 128
     or p_idempotency_key !~ '^[A-Za-z0-9._:-]+$' then
    raise exception 'account_deletion_idempotency_key_invalid' using errcode='22023';
  end if;
  if not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'account_not_found' using errcode='P0002';
  end if;

  select * into v_request
    from public.account_deletion_requests r
   where r.user_id=p_actor_user_id
     and r.status in ('awaiting_policy','scheduled','processing','blocked_legal_hold','blocked_dependency')
   order by r.requested_at desc,r.id desc
   limit 1
   for update;

  if found then
    v_request_id:=v_request.id;
    v_export_job_id:=v_request.export_job_id;
    if v_export_job_id is null then
      v_export_key:='deletion-export:'||v_request_id::text;
      insert into public.account_export_jobs(user_id,idempotency_key)
      values(p_actor_user_id,v_export_key)
      on conflict(user_id,idempotency_key) do nothing;
      select j.id,j.status into v_export_job_id,v_export_status
        from public.account_export_jobs j
       where j.user_id=p_actor_user_id and j.idempotency_key=v_export_key;
      update public.account_deletion_requests
         set export_job_id=v_export_job_id,
             idempotency_key=coalesce(idempotency_key,p_idempotency_key),
             request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
               'export_job_id',v_export_job_id,'export_status',v_export_status,
               'export_requested_for_deletion',true),
             updated_at=clock_timestamp()
       where id=v_request_id;
    else
      select j.status into v_export_status from public.account_export_jobs j
       where j.id=v_export_job_id and j.user_id=p_actor_user_id;
    end if;
    return query
      select r.id,r.status,r.requested_at,r.subject_ref,r.export_job_id,v_export_status
        from public.account_deletion_requests r where r.id=v_request_id;
    return;
  end if;

  if not exists(
    select 1 from public.profiles p
     where p.id=p_actor_user_id and p.account_status='active'
  ) then
    raise exception 'account_not_active' using errcode='42501';
  end if;

  v_subject_ref:=encode(extensions.digest(p_actor_user_id::text,'sha256'),'hex');
  insert into public.account_deletion_requests(user_id,subject_ref,status,idempotency_key)
  values(p_actor_user_id,v_subject_ref,'awaiting_policy',p_idempotency_key)
  returning id into v_request_id;

  v_export_key:='deletion-export:'||v_request_id::text;
  insert into public.account_export_jobs(user_id,idempotency_key)
  values(p_actor_user_id,v_export_key)
  on conflict(user_id,idempotency_key) do nothing;
  select j.id,j.status into v_export_job_id,v_export_status
    from public.account_export_jobs j
   where j.user_id=p_actor_user_id and j.idempotency_key=v_export_key;

  if v_export_job_id is null then
    raise exception 'account_deletion_export_job_not_created' using errcode='40001';
  end if;

  update public.account_deletion_requests
     set export_job_id=v_export_job_id,
         request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
           'export_job_id',v_export_job_id,'export_status',v_export_status,
           'export_requested_for_deletion',true),
         updated_at=clock_timestamp()
   where id=v_request_id;

  update public.profiles p
     set account_status='deactivation_requested'
   where p.id=p_actor_user_id and p.account_status='active';
  if not found then
    raise exception 'account_deletion_request_not_created' using errcode='40001';
  end if;

  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values(v_request_id,p_actor_user_id,v_subject_ref,'export_requested',
    jsonb_build_object('export_job_id',v_export_job_id,'triggered_by','account_deletion_request'));
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values(v_request_id,p_actor_user_id,v_subject_ref,'deletion_requested',
    jsonb_build_object(
      'execution_state','awaiting_policy',
      'export_job_id',v_export_job_id,
      'export_status',v_export_status,
      'export_required_before_deletion',true,
      'retention_policy_configured',
        (select count(distinct p.data_class)=7
           from public.account_data_retention_policies p
          where p.active=true and p.retention_days>=0
            and nullif(p.policy_version,'') is not null
            and nullif(p.legal_basis,'') is not null
            and ((p.decision_source='product_owner_directive' and nullif(p.decision_reference,'') is not null)
              or (p.decision_source='operator_approval' and p.approved_by is not null and p.approved_at is not null)))
    ));

  return query
    select r.id,r.status,r.requested_at,r.subject_ref,r.export_job_id,v_export_status
      from public.account_deletion_requests r where r.id=v_request_id;
end;
$function$;
revoke all on function public.create_account_deletion_request_for_actor(uuid,text) from public,anon,authenticated;
grant execute on function public.create_account_deletion_request_for_actor(uuid,text) to service_role;

create or replace function private.account_deletion_export_gate(
  p_user_id uuid,
  p_export_job_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_linked_status text;
  v_pending integer;
  v_missing_expiry integer;
  v_expiry timestamptz;
  v_policy_version text;
begin
  if p_user_id is null or p_export_job_id is null then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_REQUIRED');
  end if;

  select j.status into v_linked_status
    from public.account_export_jobs j
   where j.id=p_export_job_id and j.user_id=p_user_id;
  if not found then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_REQUIRED','export_job_id',p_export_job_id);
  end if;
  if v_linked_status in ('queued','running') then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_PENDING',
      'export_job_id',p_export_job_id,'export_status',v_linked_status);
  end if;
  if v_linked_status in ('failed','cancelled') then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_FAILED',
      'export_job_id',p_export_job_id,'export_status',v_linked_status);
  end if;
  if v_linked_status not in ('succeeded','expired') then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_PENDING',
      'export_job_id',p_export_job_id,'export_status',v_linked_status);
  end if;

  select p.policy_version into v_policy_version
    from public.account_data_retention_policies p
   where p.data_class='account_export_artifact'
     and p.active=true and p.retention_days>=0
     and nullif(p.policy_version,'') is not null
     and nullif(p.legal_basis,'') is not null
     and ((p.decision_source='product_owner_directive' and nullif(p.decision_reference,'') is not null)
       or (p.decision_source='operator_approval' and p.approved_by is not null and p.approved_at is not null))
   order by p.updated_at desc,p.id desc
   limit 1;
  if v_policy_version is null then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_RETENTION_POLICY_MISSING',
      'export_job_id',p_export_job_id,'export_status',v_linked_status);
  end if;

  select count(*) into v_pending
    from public.account_export_jobs j
   where j.user_id=p_user_id and j.status in ('queued','running');
  if v_pending>0 then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_PENDING',
      'pending_export_jobs',v_pending,'export_job_id',p_export_job_id);
  end if;

  select count(*) into v_missing_expiry
    from public.account_export_jobs j
   where j.user_id=p_user_id and j.status in ('succeeded','expired') and j.expires_at is null;
  if v_missing_expiry>0 then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_RETENTION_POLICY_MISSING',
      'exports_missing_expiry',v_missing_expiry,'export_job_id',p_export_job_id);
  end if;

  select max(j.expires_at) into v_expiry
    from public.account_export_jobs j
   where j.user_id=p_user_id and j.status in ('succeeded','expired');
  if v_expiry is null then
    return jsonb_build_object('ready',false,'code','ACCOUNT_EXPORT_RETENTION_POLICY_MISSING',
      'export_job_id',p_export_job_id);
  end if;

  return jsonb_build_object(
    'ready',true,'code','ACCOUNT_EXPORT_READY',
    'export_job_id',p_export_job_id,'export_status',v_linked_status,
    'retention_policy_version',v_policy_version,'expires_at',v_expiry
  );
end;
$function$;
revoke all on function private.account_deletion_export_gate(uuid,uuid) from public,anon,authenticated;
grant execute on function private.account_deletion_export_gate(uuid,uuid) to service_role;

-- When the export-artifact policy is activated after an export completed, backfill its expiry
-- without inventing a duration; use only the configured, active policy.
create or replace function private.requeue_blocked_account_deletion_requests()
returns trigger
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_export_retention_days integer;
begin
  if tg_table_name='account_data_retention_policies' then
    select p.retention_days into v_export_retention_days
      from public.account_data_retention_policies p
     where p.data_class='account_export_artifact' and p.active=true and p.retention_days>=0
     order by p.updated_at desc,p.id desc limit 1;
    if found then
      update public.account_export_jobs j
         set expires_at=j.completed_at+pg_catalog.make_interval(days=>v_export_retention_days),
             updated_at=clock_timestamp()
       where j.status='succeeded' and j.expires_at is null and j.completed_at is not null;
    end if;
  end if;

  with requeued as (
    update public.account_deletion_requests
       set status='awaiting_policy',
           scheduled_for=null,
           error_code=null,
           request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
             'requeued_at',clock_timestamp(),
             'requeue_reason','DEPENDENCY_POLICY_CHANGED'
           ),
           updated_at=clock_timestamp()
     where status='blocked_dependency'
     returning id,user_id,subject_ref
  )
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  select id,user_id,subject_ref,'deletion_unblocked',
         jsonb_build_object(
           'reason_code','DEPENDENCY_POLICY_CHANGED_REEVALUATION_REQUIRED',
           'source_table',tg_table_name,
           'operation',tg_op
         )
    from requeued;
  return null;
end;
$function$;
revoke all on function private.requeue_blocked_account_deletion_requests() from public,anon,authenticated;
grant execute on function private.requeue_blocked_account_deletion_requests() to service_role;

-- Skip the generic export cleanup queue for exports owned by an active deletion lifecycle;
-- the deletion executor must own their Storage cleanup after the download window.
create or replace function public.enqueue_expired_account_export_artifacts()
returns integer
language plpgsql
security definer
set search_path = ''
as $function$
declare v_count integer;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  insert into public.account_export_artifact_cleanup_jobs(export_job_id,storage_bucket,storage_path)
  select j.id,j.storage_bucket,j.storage_path
    from public.account_export_jobs j
   where j.status='succeeded'
     and j.expires_at is not null
     and j.expires_at <= pg_catalog.clock_timestamp()
     and j.storage_path is not null
     and not exists(
       select 1 from public.account_deletion_requests r
        where r.export_job_id=j.id
          and r.status in ('awaiting_policy','scheduled','processing','blocked_legal_hold','blocked_dependency')
     )
  on conflict(export_job_id) do nothing;
  get diagnostics v_count=row_count;
  return v_count;
end;
$function$;
revoke all on function public.enqueue_expired_account_export_artifacts() from public,anon,authenticated;
grant execute on function public.enqueue_expired_account_export_artifacts() to service_role;

do $patch$
declare
  v_prepare text;
  v_evaluate text;
  v_old_prepare_decl text := $old$
        v_missing_fk_rules integer; v_missing_transfers integer;
        v_policy_snapshot jsonb; v_retention_days integer; v_retention_until timestamptz;
$old$;
  v_new_prepare_decl text := $new$
        v_missing_fk_rules integer; v_missing_transfers integer;
        v_policy_snapshot jsonb; v_retention_days integer; v_retention_until timestamptz;
        v_export_gate jsonb; v_export_until timestamptz;
$new$;
  v_old_prepare_gate text := $old$
  select array_agg(required.data_class order by required.data_class) into v_missing_classes
$old$;
  v_new_prepare_gate text := $new$
  v_export_gate:=private.account_deletion_export_gate(v_request.user_id,v_request.export_job_id);
  if coalesce((v_export_gate->>'ready')::boolean,false)=false then
    update public.account_deletion_requests
       set status='blocked_dependency',scheduled_for=null,
           error_code=coalesce(v_export_gate->>'code','ACCOUNT_EXPORT_PENDING'),
           request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
             'export_gate',v_export_gate,'export_checked_at',clock_timestamp()),
           updated_at=clock_timestamp()
     where id=p_request_id;
    if v_request.status<>'blocked_dependency' or v_request.error_code is distinct from (v_export_gate->>'code') then
      insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
      values(p_request_id,v_request.user_id,v_request.subject_ref,'deletion_blocked',
        jsonb_build_object('reason_code',coalesce(v_export_gate->>'code','ACCOUNT_EXPORT_PENDING'),
          'export_gate',v_export_gate));
    end if;
    return jsonb_build_object('outcome','blocked_dependency','export_gate',v_export_gate);
  end if;
  v_export_until:=nullif(v_export_gate->>'expires_at','')::timestamptz;

  select array_agg(required.data_class order by required.data_class) into v_missing_classes
$new$;
  v_old_classes text := $old$('published_knowledge'),('session_scoped'),('public_catalog')) required(data_class)$old$;
  v_new_classes text := $new$('published_knowledge'),('session_scoped'),('public_catalog'),('account_export_artifact')) required(data_class)$new$;
  v_old_prepare_retention text := $old$v_retention_until := v_request.requested_at + pg_catalog.make_interval(days=>v_retention_days);$old$;
  v_new_prepare_retention text := $new$v_retention_until := greatest(
      v_request.requested_at + pg_catalog.make_interval(days=>v_retention_days),
      coalesce(v_export_until,v_request.requested_at)
    );$new$;
  v_old_storage_export text := $old$
  where j.user_id=v_request.user_id and j.status='succeeded' and j.storage_path is not null
    and j.storage_bucket='account-exports' and j.storage_path<>'' and left(j.storage_path,1)<>'/'
$old$;
  v_new_storage_export text := $new$
  where j.user_id=v_request.user_id and j.status='succeeded' and j.expires_at is not null
    and j.expires_at<=pg_catalog.clock_timestamp() and j.storage_path is not null
    and j.storage_bucket='account-exports' and j.storage_path<>'' and left(j.storage_path,1)<>'/'
$new$;
  v_old_prepare_metadata text := $old$
      'storage_cleanup_queued',true,'prepared_at',clock_timestamp()),updated_at=clock_timestamp()
$new$;
  v_new_prepare_metadata text := $new$
      'storage_cleanup_queued',true,'export_job_id',v_request.export_job_id,
      'export_retention_until',v_export_until,'prepared_at',clock_timestamp()),updated_at=clock_timestamp()
$new$;

  v_old_eval_decl text := $old$
  v_missing_transfers integer;
  v_retention_days integer;
  v_retention_until timestamptz;
  v_policy_version text;
$old$;
  v_new_eval_decl text := $new$
  v_missing_transfers integer;
  v_retention_days integer;
  v_retention_until timestamptz;
  v_policy_version text;
  v_export_gate jsonb;
  v_export_until timestamptz;
$new$;
  v_old_eval_gate text := $old$
    select array_agg(required.data_class order by required.data_class) into v_missing_classes
$old$;
  v_new_eval_gate text := $new$
    v_export_gate:=private.account_deletion_export_gate(v_request.user_id,v_request.export_job_id);
    if coalesce((v_export_gate->>'ready')::boolean,false)=false then
      update public.account_deletion_requests
         set status='blocked_dependency',scheduled_for=null,
             error_code=coalesce(v_export_gate->>'code','ACCOUNT_EXPORT_PENDING'),
             request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
               'export_gate',v_export_gate,'export_checked_at',clock_timestamp(),
               'deletion_policy_state','export_gate_blocked'),
             updated_at=clock_timestamp()
       where id=v_request.id;
      if v_request.status<>'blocked_dependency' or v_request.error_code is distinct from (v_export_gate->>'code') then
        insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
        values(v_request.id,v_request.user_id,v_request.subject_ref,'deletion_blocked',
          jsonb_build_object('reason_code',coalesce(v_export_gate->>'code','ACCOUNT_EXPORT_PENDING'),
            'export_gate',v_export_gate));
      end if;
      v_blocked:=v_blocked+1;
      continue;
    end if;
    v_export_until:=nullif(v_export_gate->>'expires_at','')::timestamptz;

    select array_agg(required.data_class order by required.data_class) into v_missing_classes
$new$;
  v_old_eval_retention text := $old$v_retention_until:=v_request.requested_at+pg_catalog.make_interval(days=>v_retention_days);$old$;
  v_new_eval_retention text := $new$v_retention_until:=greatest(
      v_request.requested_at+pg_catalog.make_interval(days=>v_retention_days),
      coalesce(v_export_until,v_request.requested_at)
    );$new$;
  v_old_eval_event text := $old$
          jsonb_build_object('reason_code','RETENTION_PERIOD_ACTIVE','retention_days',v_retention_days,
            'scheduled_for',v_retention_until,'policy_version',v_policy_version));
$old$;
  v_new_eval_event text := $new$
          jsonb_build_object(
            'reason_code',case when v_export_until>v_request.requested_at+pg_catalog.make_interval(days=>v_retention_days)
              then 'EXPORT_ARTIFACT_RETENTION_ACTIVE' else 'RETENTION_PERIOD_ACTIVE' end,
            'retention_days',v_retention_days,'scheduled_for',v_retention_until,
            'export_job_id',v_request.export_job_id,'export_expires_at',v_export_until,
            'policy_version',v_policy_version));
$new$;
  v_old_eval_meta text := $old$
               'retention_days',v_retention_days,'retention_until',v_retention_until,
               'deletion_policy_state',v_policy_state,'legal_hold_active',false,
$new$;
  v_new_eval_meta text := $new$
               'retention_days',v_retention_days,'retention_until',v_retention_until,
               'export_job_id',v_request.export_job_id,'export_retention_until',v_export_until,
               'deletion_policy_state',v_policy_state,'legal_hold_active',false,
$new$;
begin
  v_prepare:=pg_get_functiondef('public.prepare_account_deletion_execution(uuid)'::regprocedure);
  if position('private.account_deletion_export_gate' in v_prepare)=0 then
    if position(v_old_prepare_decl in v_prepare)=0 then raise exception 'account_deletion_prepare_export_decl_anchor_missing'; end if;
    v_prepare:=replace(v_prepare,v_old_prepare_decl,v_new_prepare_decl);
    if position(v_old_prepare_gate in v_prepare)=0 then raise exception 'account_deletion_prepare_export_gate_anchor_missing'; end if;
    v_prepare:=replace(v_prepare,v_old_prepare_gate,v_new_prepare_gate);
    if position(v_old_classes in v_prepare)=0 then raise exception 'account_deletion_prepare_export_class_anchor_missing'; end if;
    v_prepare:=replace(v_prepare,v_old_classes,v_new_classes);
    if position(v_old_prepare_retention in v_prepare)=0 then raise exception 'account_deletion_prepare_export_retention_anchor_missing'; end if;
    v_prepare:=replace(v_prepare,v_old_prepare_retention,v_new_prepare_retention);
    if position(v_old_storage_export in v_prepare)=0 then raise exception 'account_deletion_prepare_export_storage_anchor_missing'; end if;
    v_prepare:=replace(v_prepare,v_old_storage_export,v_new_storage_export);
    if position(v_old_prepare_metadata in v_prepare)=0 then raise exception 'account_deletion_prepare_export_metadata_anchor_missing'; end if;
    v_prepare:=replace(v_prepare,v_old_prepare_metadata,v_new_prepare_metadata);
    execute v_prepare;
  end if;

  v_evaluate:=pg_get_functiondef('public.evaluate_account_deletion_governance(integer)'::regprocedure);
  if position('private.account_deletion_export_gate' in v_evaluate)=0 then
    if position(v_old_eval_decl in v_evaluate)=0 then raise exception 'account_deletion_governance_export_decl_anchor_missing'; end if;
    v_evaluate:=replace(v_evaluate,v_old_eval_decl,v_new_eval_decl);
    if position(v_old_eval_gate in v_evaluate)=0 then raise exception 'account_deletion_governance_export_gate_anchor_missing'; end if;
    v_evaluate:=replace(v_evaluate,v_old_eval_gate,v_new_eval_gate);
    if position(v_old_classes in v_evaluate)=0 then raise exception 'account_deletion_governance_export_class_anchor_missing'; end if;
    v_evaluate:=replace(v_evaluate,v_old_classes,v_new_classes);
    if position(v_old_eval_retention in v_evaluate)=0 then raise exception 'account_deletion_governance_export_retention_anchor_missing'; end if;
    v_evaluate:=replace(v_evaluate,v_old_eval_retention,v_new_eval_retention);
    if position(v_old_eval_event in v_evaluate)=0 then raise exception 'account_deletion_governance_export_event_anchor_missing'; end if;
    v_evaluate:=replace(v_evaluate,v_old_eval_event,v_new_eval_event);
    if position(v_old_eval_meta in v_evaluate)=0 then raise exception 'account_deletion_governance_export_meta_anchor_missing'; end if;
    v_evaluate:=replace(v_evaluate,v_old_eval_meta,v_new_eval_meta);
    execute v_evaluate;
  end if;
end;
$patch$;

revoke all on function public.create_account_deletion_request_for_actor(uuid,text) from public,anon,authenticated;
