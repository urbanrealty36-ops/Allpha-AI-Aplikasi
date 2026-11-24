-- ENG-P03: make owner-directive policy governance executable without administrative acceptance.
-- Legal holds, retention rules, source handlers, FK coverage and ownership transfers remain hard gates.

do $$
declare
  v_definition text;
  v_old_decl text := $old$
declare v_request public.account_deletion_requests%rowtype; v_job public.account_deletion_execution_jobs%rowtype;
        v_missing_classes text[]; v_missing_sources integer; v_blocked_fks integer; v_policy_snapshot jsonb; v_retention_days integer; v_retention_until timestamptz;
$old$;
  v_new_decl text := $new$
declare v_request public.account_deletion_requests%rowtype; v_job public.account_deletion_execution_jobs%rowtype;
        v_missing_classes text[]; v_missing_sources integer; v_blocked_fks integer;
        v_missing_fk_rules integer; v_missing_transfers integer;
        v_policy_snapshot jsonb; v_retention_days integer; v_retention_until timestamptz;
$new$;
  v_old_status text := $old$if v_request.status not in ('awaiting_policy','blocked_dependency') then$old$;
  v_new_status text := $new$if v_request.status not in ('awaiting_policy','blocked_dependency','scheduled') then$new$;
  v_old_status_end text := $old$
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_request.subject_ref,0));
$old$;
  v_new_status_end text := $new$
  end if;
  if v_request.status='scheduled' and v_request.scheduled_for>pg_catalog.clock_timestamp() then
    return jsonb_build_object('outcome','scheduled','scheduled_for',v_request.scheduled_for);
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_request.subject_ref,0));
$new$;
  v_old_classes text := $old$
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true);
$old$;
  v_new_classes text := $new$
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true and p.retention_days>=0
      and nullif(p.policy_version,'') is not null and nullif(p.legal_basis,'') is not null
      and ((p.decision_source='product_owner_directive' and nullif(p.decision_reference,'') is not null)
        or (p.decision_source='operator_approval' and p.approved_by is not null and p.approved_at is not null)));
$new$;
  v_old_sources text := $old$
  select count(*) into v_missing_sources from private.account_export_sources s
  left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
  where s.enabled=true and (p.source_key is null or p.data_class is null
    or p.deletion_action is null
    or (p.deletion_action='block' and private.account_deletion_source_has_user_rows(s.source_key,v_request.user_id)));
$old$;
  v_new_sources text := $new$
  select count(*) into v_missing_sources from private.account_export_sources s
  left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
  where s.enabled=true and (p.source_key is null or p.data_class is null
    or p.deletion_action is null or nullif(p.reason,'') is null
    or (p.deletion_action='delete_rows' and not private.account_deletion_source_handler_available(
      s.source_key,s.table_name,s.filter_kind,s.owner_columns))
    or (p.deletion_action='anonymize' and p.source_key not in ('spatial_theme_versions','spatial_themes_created'))
    or (p.deletion_action='block' and private.account_deletion_source_has_user_rows(s.source_key,v_request.user_id)));
$new$;
  v_old_fk text := $old$
  select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action='block'
      and private.account_deletion_fk_has_unresolved_user_rows(r.id,v_request.user_id);
$old$;
  v_new_fk text := $new$
  select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action='block'
      and private.account_deletion_fk_has_unresolved_user_rows(r.id,v_request.user_id);

  select count(*) into v_missing_fk_rules
    from pg_constraint c
    join pg_class t on t.oid=c.conrelid
    join pg_namespace n on n.oid=t.relnamespace
   where c.contype='f' and c.confrelid='auth.users'::regclass and n.nspname='public'
     and not exists(select 1 from public.account_deletion_dependency_rules r
       where r.active=true and r.child_schema=n.nspname and r.child_table=t.relname
         and r.constraint_name=c.conname);

  select
    (select count(*) from public.agent_ownerships ao
      where ao.owner_user_id=v_request.user_id 
        and not exists(select 1 from public.account_deletion_ownership_transfers tr
          join public.profiles sp on sp.id=tr.successor_user_id and sp.account_status='active'
         where tr.request_id=p_request_id and tr.user_id=v_request.user_id
           and tr.resource_type='agent' and tr.resource_id=ao.agent_id and tr.status='requested'))
    +
    (select count(*) from public.organizations o
      where o.owner_id=v_request.user_id
        and not exists(select 1 from public.account_deletion_ownership_transfers tr
          join public.profiles sp on sp.id=tr.successor_user_id and sp.account_status='active'
          join public.organization_memberships m on m.organization_id=o.id and m.user_id=tr.successor_user_id
         where tr.request_id=p_request_id and tr.user_id=v_request.user_id
           and tr.resource_type='organization' and tr.resource_id=o.id and tr.status='requested'))
    into v_missing_transfers;
$new$;
  v_old_gate text := $old$
  if coalesce(cardinality(v_missing_classes),0)>0 or v_missing_sources>0 or v_blocked_fks>0 then
$old$;
  v_new_gate text := $new$
  if coalesce(cardinality(v_missing_classes),0)>0 or v_missing_sources>0 or v_blocked_fks>0
     or v_missing_fk_rules>0 or v_missing_transfers>0 then
$new$;
  v_old_error text := $old$error_code='DELETION_POLICY_OR_DEPENDENCY_MAP_INCOMPLETE',$old$;
  v_new_error text := $new$error_code=case when v_missing_transfers>0 then 'OWNERSHIP_TRANSFER_REQUIRED'
        else 'DELETION_POLICY_OR_DEPENDENCY_MAP_INCOMPLETE' end,$new$;
  v_old_meta text := $old$
        'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks,
        'checked_at',clock_timestamp()),updated_at=clock_timestamp() where id=p_request_id;
$old$;
  v_new_meta text := $new$
        'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks,
        'missing_fk_rules',v_missing_fk_rules,'missing_ownership_transfers',v_missing_transfers,
        'checked_at',clock_timestamp()),updated_at=clock_timestamp() where id=p_request_id;
$new$;
  v_old_return text := $old$
      'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks);
$old$;
  v_new_return text := $new$
      'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks,
      'missing_fk_rules',v_missing_fk_rules,'missing_ownership_transfers',v_missing_transfers);
$new$;
begin
  v_definition:=pg_get_functiondef('public.prepare_account_deletion_execution(uuid)'::regprocedure);
  if position(v_new_gate in v_definition)=0 then
    if position(v_old_gate in v_definition)=0 then raise exception 'account_deletion_prepare_gate_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_gate,v_new_gate);
  end if;
  if position(v_new_decl in v_definition)=0 then
    if position(v_old_decl in v_definition)=0 then raise exception 'account_deletion_prepare_decl_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_decl,v_new_decl);
  end if;
  if position(v_new_status in v_definition)=0 then
    if position(v_old_status in v_definition)=0 then raise exception 'account_deletion_prepare_status_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_status,v_new_status);
  end if;
  if position(v_new_status_end in v_definition)=0 then
    if position(v_old_status_end in v_definition)=0 then raise exception 'account_deletion_prepare_scheduled_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_status_end,v_new_status_end);
  end if;
  if position(v_new_classes in v_definition)=0 then
    if position(v_old_classes in v_definition)=0 then raise exception 'account_deletion_prepare_retention_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_classes,v_new_classes);
  end if;
  if position(v_new_sources in v_definition)=0 then
    if position(v_old_sources in v_definition)=0 then raise exception 'account_deletion_prepare_source_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_sources,v_new_sources);
  end if;
  if position(v_new_fk in v_definition)=0 then
    if position(v_old_fk in v_definition)=0 then raise exception 'account_deletion_prepare_fk_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_fk,v_new_fk);
  end if;
  if position(v_new_error in v_definition)=0 then
    if position(v_old_error in v_definition)=0 then raise exception 'account_deletion_prepare_error_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_error,v_new_error);
  end if;
  if position(v_new_meta in v_definition)=0 then
    if position(v_old_meta in v_definition)=0 then raise exception 'account_deletion_prepare_metadata_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_meta,v_new_meta);
  end if;
  if position(v_new_return in v_definition)=0 then
    if position(v_old_return in v_definition)=0 then raise exception 'account_deletion_prepare_return_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old_return,v_new_return);
  end if;
  execute v_definition;
end;
$$;

create or replace function public.prepare_account_deletion_execution_batch(p_limit integer default 20)
returns table(processed_count integer,queued_count integer,blocked_count integer)
language plpgsql
security definer
set search_path = ''
as $$
declare v_id uuid; v_result jsonb; v_processed integer:=0; v_queued integer:=0; v_blocked integer:=0;
begin
  if coalesce(auth.role(),'')<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_limit is null or p_limit not between 1 and 100 then
    raise exception 'invalid_deletion_prepare_limit' using errcode='22023';
  end if;
  for v_id in
    select id from public.account_deletion_requests
     where status in ('awaiting_policy','scheduled','blocked_dependency')
       and (status<>'scheduled' or coalesce(scheduled_for,clock_timestamp())<=clock_timestamp())
     order by requested_at,id limit p_limit for update skip locked
  loop
    v_result:=public.prepare_account_deletion_execution(v_id);
    v_processed:=v_processed+1;
    if v_result->>'outcome'='queued' then v_queued:=v_queued+1;
    elsif v_result->>'outcome' in ('blocked_dependency','blocked_legal_hold') then v_blocked:=v_blocked+1;
    end if;
  end loop;
  return query select v_processed,v_queued,v_blocked;
end;
$$;
revoke all on function public.prepare_account_deletion_execution_batch(integer) from public,anon,authenticated;
grant execute on function public.prepare_account_deletion_execution_batch(integer) to service_role;

create or replace function public.evaluate_account_deletion_governance(p_limit integer default 100)
returns table(processed_count integer,blocked_count integer,unblocked_count integer,policy_pending_count integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_request public.account_deletion_requests%rowtype;
  v_hold_ids uuid[];
  v_missing_classes text[];
  v_missing_sources integer;
  v_blocked_fks integer;
  v_missing_fk_rules integer;
  v_missing_transfers integer;
  v_retention_days integer;
  v_retention_until timestamptz;
  v_policy_version text;
  v_processed integer:=0;
  v_blocked integer:=0;
  v_unblocked integer:=0;
  v_pending integer:=0;
  v_policy_state text;
begin
  if coalesce(auth.role(),'')<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_limit is null or p_limit not between 1 and 500 then
    raise exception 'invalid_deletion_governance_batch_size' using errcode='22023';
  end if;

  for v_request in
    select r.* from public.account_deletion_requests r
     where r.status in ('awaiting_policy','scheduled','blocked_legal_hold','blocked_dependency')
     order by r.requested_at,r.id limit p_limit for update skip locked
  loop
    v_processed:=v_processed+1;
    select coalesce(array_agg(h.id order by h.created_at,h.id),'{}'::uuid[])
      into v_hold_ids
      from public.account_legal_holds h
     where h.subject_ref=v_request.subject_ref and h.active=true;

    if cardinality(v_hold_ids)>0 then
      if v_request.status<>'blocked_legal_hold' then
        update public.account_deletion_requests
           set status='blocked_legal_hold',scheduled_for=null,error_code='LEGAL_HOLD_ACTIVE',
               request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
                 'legal_hold_active',true,'active_legal_hold_ids',to_jsonb(v_hold_ids),
                 'deletion_policy_state','legal_hold_blocked','governance_checked_at',clock_timestamp()),
               updated_at=clock_timestamp()
         where id=v_request.id;
        insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
        values(v_request.id,v_request.user_id,v_request.subject_ref,'deletion_blocked',
          jsonb_build_object('reason_code','LEGAL_HOLD_ACTIVE','legal_hold_ids',to_jsonb(v_hold_ids)));
      end if;
      v_blocked:=v_blocked+1;
      continue;
    end if;

    if v_request.status='blocked_legal_hold' then
      update public.account_deletion_requests
         set status='awaiting_policy',scheduled_for=null,error_code=null,
             request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
               'legal_hold_active',false,'active_legal_hold_ids','[]'::jsonb,
               'governance_checked_at',clock_timestamp()),
             updated_at=clock_timestamp()
       where id=v_request.id;
      insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
      values(v_request.id,v_request.user_id,v_request.subject_ref,'deletion_unblocked',
        jsonb_build_object('reason_code','LEGAL_HOLD_RELEASED'));
      v_request.status:='awaiting_policy';
    end if;

    select array_agg(required.data_class order by required.data_class) into v_missing_classes
    from (values ('owner_private'),('agent_operational'),('tenant_shared'),
      ('published_knowledge'),('session_scoped'),('public_catalog')) required(data_class)
    where not exists(select 1 from public.account_data_retention_policies p
      where p.data_class=required.data_class and p.active=true and p.retention_days>=0
        and nullif(p.policy_version,'') is not null and nullif(p.legal_basis,'') is not null
        and ((p.decision_source='product_owner_directive' and nullif(p.decision_reference,'') is not null)
          or (p.decision_source='operator_approval' and p.approved_by is not null and p.approved_at is not null)));

    select count(*) into v_missing_sources
      from private.account_export_sources s
      left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
     where s.enabled=true and (p.source_key is null or p.data_class is null or p.deletion_action is null
       or nullif(p.reason,'') is null
       or (p.deletion_action='delete_rows' and not private.account_deletion_source_handler_available(
         s.source_key,s.table_name,s.filter_kind,s.owner_columns))
       or (p.deletion_action='anonymize' and p.source_key not in ('spatial_theme_versions','spatial_themes_created'))
       or (p.deletion_action='block' and private.account_deletion_source_has_user_rows(s.source_key,v_request.user_id)));

    select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
     where r.active=true and r.resolution_action='block'
       and private.account_deletion_fk_has_unresolved_user_rows(r.id,v_request.user_id);

    select count(*) into v_missing_fk_rules
      from pg_constraint c join pg_class t on t.oid=c.conrelid
      join pg_namespace n on n.oid=t.relnamespace
     where c.contype='f' and c.confrelid='auth.users'::regclass and n.nspname='public'
       and not exists(select 1 from public.account_deletion_dependency_rules r
         where r.active=true and r.child_schema=n.nspname and r.child_table=t.relname
           and r.constraint_name=c.conname);

    select
      (select count(*) from public.agent_ownerships ao
        where ao.owner_user_id=v_request.user_id 
          and not exists(select 1 from public.account_deletion_ownership_transfers tr
            join public.profiles sp on sp.id=tr.successor_user_id and sp.account_status='active'
           where tr.request_id=v_request.id and tr.user_id=v_request.user_id
             and tr.resource_type='agent' and tr.resource_id=ao.agent_id and tr.status='requested'))
      +
      (select count(*) from public.organizations o
        where o.owner_id=v_request.user_id
          and not exists(select 1 from public.account_deletion_ownership_transfers tr
            join public.profiles sp on sp.id=tr.successor_user_id and sp.account_status='active'
            join public.organization_memberships m on m.organization_id=o.id and m.user_id=tr.successor_user_id
           where tr.request_id=v_request.id and tr.user_id=v_request.user_id
             and tr.resource_type='organization' and tr.resource_id=o.id and tr.status='requested'))
      into v_missing_transfers;

    if coalesce(cardinality(v_missing_classes),0)>0 or v_missing_sources>0 or v_blocked_fks>0
       or v_missing_fk_rules>0 or v_missing_transfers>0 then
      update public.account_deletion_requests
         set status='blocked_dependency',scheduled_for=null,
             error_code=case when v_missing_transfers>0 then 'OWNERSHIP_TRANSFER_REQUIRED'
               else 'DELETION_POLICY_OR_DEPENDENCY_MAP_INCOMPLETE' end,
             request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
               'missing_data_classes',coalesce(to_jsonb(v_missing_classes),'[]'::jsonb),
               'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks,
               'missing_fk_rules',v_missing_fk_rules,'missing_ownership_transfers',v_missing_transfers,
               'deletion_policy_state','blocked','governance_checked_at',clock_timestamp()),
             updated_at=clock_timestamp()
       where id=v_request.id;
      if v_request.status<>'blocked_dependency' then
        insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
        values(v_request.id,v_request.user_id,v_request.subject_ref,'deletion_blocked',
          jsonb_build_object('reason_code',case when v_missing_transfers>0 then 'OWNERSHIP_TRANSFER_REQUIRED'
            else 'DELETION_POLICY_OR_DEPENDENCY_MAP_INCOMPLETE' end,
            'missing_data_classes',coalesce(to_jsonb(v_missing_classes),'[]'::jsonb),
            'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks,
            'missing_fk_rules',v_missing_fk_rules,'missing_ownership_transfers',v_missing_transfers));
      end if;
      v_blocked:=v_blocked+1;
      continue;
    end if;

    select coalesce(max(p.retention_days),0),max(p.policy_version)
      into v_retention_days,v_policy_version
      from public.account_data_retention_policies p where p.active=true;
    v_retention_until:=v_request.requested_at+pg_catalog.make_interval(days=>v_retention_days);
    v_policy_state:='owner_directive_ready:'||coalesce(v_policy_version,'unknown');

    if v_retention_until>pg_catalog.clock_timestamp() then
      update public.account_deletion_requests
         set status='scheduled',scheduled_for=v_retention_until,error_code=null,
             request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
               'retention_days',v_retention_days,'retention_until',v_retention_until,
               'deletion_policy_state',v_policy_state,'legal_hold_active',false,
               'governance_checked_at',clock_timestamp()),
             updated_at=clock_timestamp()
       where id=v_request.id;
      if v_request.status<>'scheduled' then
        insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
        values(v_request.id,v_request.user_id,v_request.subject_ref,'deletion_scheduled',
          jsonb_build_object('reason_code','RETENTION_PERIOD_ACTIVE','retention_days',v_retention_days,
            'scheduled_for',v_retention_until,'policy_version',v_policy_version));
      end if;
      v_pending:=v_pending+1;
    else
      update public.account_deletion_requests
         set status='awaiting_policy',scheduled_for=null,error_code=null,
             request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
               'retention_days',v_retention_days,'retention_until',v_retention_until,
               'deletion_policy_state',v_policy_state,'legal_hold_active',false,
               'governance_checked_at',clock_timestamp()),
             updated_at=clock_timestamp()
       where id=v_request.id;
      if v_request.status in ('blocked_dependency','scheduled') then
        insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
        values(v_request.id,v_request.user_id,v_request.subject_ref,'deletion_unblocked',
          jsonb_build_object('reason_code','POLICY_AND_DEPENDENCY_MAP_READY',
            'policy_version',v_policy_version,'retention_days',v_retention_days));
        v_unblocked:=v_unblocked+1;
      end if;
    end if;
  end loop;
  return query select v_processed,v_blocked,v_unblocked,v_pending;
end;
$$;
revoke all on function public.evaluate_account_deletion_governance(integer) from public,anon,authenticated;
grant execute on function public.evaluate_account_deletion_governance(integer) to service_role;


-- Ownership FK transfer applies to every owner_user_id reference in the ownership registry,
-- including inactive historical rows; role/status are preserved on the transferred row.
do $$
declare
  v_definition text;
  v_old text := $old$and ao.ownership_role='owner' and ao.status='active'$old$;
begin
  v_definition:=pg_get_functiondef('public.set_my_account_deletion_ownership_transfer(uuid,text,uuid,uuid)'::regprocedure);
  if position(v_old in v_definition)>0 then
    execute replace(v_definition,v_old,'');
  end if;
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  if position(v_old in v_definition)>0 then
    execute replace(v_definition,v_old,'');
  end if;
end;
$$;
