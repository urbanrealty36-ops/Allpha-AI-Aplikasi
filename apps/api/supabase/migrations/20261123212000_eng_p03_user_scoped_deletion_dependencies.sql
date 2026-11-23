create or replace function private.account_deletion_source_has_user_rows(
  p_source_key text,
  p_user_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_source private.account_export_sources%rowtype;
  v_column text;
  v_sql text;
  v_exists boolean;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_source_key is null or p_user_id is null then
    raise exception 'account_deletion_source_probe_arguments_required' using errcode='22023';
  end if;
  select * into v_source from private.account_export_sources
   where source_key=p_source_key and enabled=true;
  if not found then return false; end if;
  -- A blocking source with a specialized or unknown filter must fail closed.
  if v_source.filter_kind <> 'owner_columns' or cardinality(v_source.owner_columns)=0 then
    return true;
  end if;
  foreach v_column in array v_source.owner_columns loop
    if not exists (
      select 1 from information_schema.columns c
       where c.table_schema='public' and c.table_name=v_source.table_name
         and c.column_name=v_column
    ) then
      raise exception 'account_deletion_source_column_missing:%.%',v_source.table_name,v_column
        using errcode='55000';
    end if;
    v_sql := format('select exists(select 1 from public.%I where %I::text = $1)',
      v_source.table_name,v_column);
    execute v_sql into v_exists using p_user_id::text;
    if coalesce(v_exists,false) then return true; end if;
  end loop;
  return false;
end;
$function$;

create or replace function private.account_deletion_fk_has_unresolved_user_rows(
  p_rule_id uuid,
  p_user_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_rule public.account_deletion_dependency_rules%rowtype;
  v_exists boolean;
  v_covered boolean;
  v_sql text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  select * into v_rule from public.account_deletion_dependency_rules
   where id=p_rule_id and active=true and resolution_action='block';
  if not found then return false; end if;
  if p_user_id is null or v_rule.fk_column is null then return true; end if;
  if not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conname=v_rule.constraint_name
       and c.conrelid=pg_catalog.to_regclass(pg_catalog.format('%I.%I',v_rule.child_schema,v_rule.child_table))
       and c.contype='f' and c.confrelid='auth.users'::regclass
       and pg_catalog.cardinality(c.conkey)=1 and pg_catalog.cardinality(c.confkey)=1
       and (select a.attname from pg_catalog.pg_attribute a where a.attrelid=c.conrelid and a.attnum=c.conkey[1])=v_rule.fk_column
       and (select a.attname from pg_catalog.pg_attribute a where a.attrelid=c.confrelid and a.attnum=c.confkey[1])='id'
  ) then
    return true;
  end if;
  v_sql := pg_catalog.format('select exists(select 1 from %I.%I where %I::text = $1)',
    v_rule.child_schema,v_rule.child_table,v_rule.fk_column);
  execute v_sql into v_exists using p_user_id::text;
  if not coalesce(v_exists,false) then return false; end if;
  -- A source handler may safely remove this exact user-owned FK column before
  -- the FK step runs. Other rows (preserved/shared/financial) remain blockers.
  select exists (
    select 1
      from private.account_export_sources s
      join public.account_deletion_source_policies p
        on p.source_key=s.source_key and p.active=true
     where s.enabled=true and s.table_name=v_rule.child_table
       and s.filter_kind='owner_columns'
       and v_rule.fk_column=any(s.owner_columns)
       and p.deletion_action='delete_rows'
  ) into v_covered;
  return not coalesce(v_covered,false);
end;
$function$;

revoke all on function private.account_deletion_source_has_user_rows(text,uuid) from public,anon,authenticated;
revoke all on function private.account_deletion_fk_has_unresolved_user_rows(uuid,uuid) from public,anon,authenticated;
grant execute on function private.account_deletion_source_has_user_rows(text,uuid) to service_role;
grant execute on function private.account_deletion_fk_has_unresolved_user_rows(uuid,uuid) to service_role;

CREATE OR REPLACE FUNCTION public.prepare_account_deletion_execution(p_request_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_request public.account_deletion_requests%rowtype; v_job public.account_deletion_execution_jobs%rowtype;
        v_missing_classes text[]; v_missing_sources integer; v_blocked_fks integer; v_policy_snapshot jsonb;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_request from public.account_deletion_requests where id=p_request_id for update;
  if not found then return jsonb_build_object('outcome','not_found'); end if;
  if v_request.status not in ('awaiting_policy','blocked_dependency') then
    select * into v_job from public.account_deletion_execution_jobs where request_id=p_request_id;
    return jsonb_build_object('outcome','already_processed','job_id',v_job.id);
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_request.subject_ref,0));
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_request.subject_ref and h.active) then
    update public.account_deletion_requests set status='blocked_legal_hold',scheduled_for=null,
      error_code='LEGAL_HOLD_ACTIVE',updated_at=clock_timestamp() where id=p_request_id;
    insert into public.account_lifecycle_events(request_id,subject_ref,event_type,metadata)
    values(p_request_id,v_request.subject_ref,'deletion_blocked',jsonb_build_object('reason_code','LEGAL_HOLD_ACTIVE'));
    return jsonb_build_object('outcome','blocked_legal_hold');
  end if;
  select array_agg(required.data_class order by required.data_class) into v_missing_classes
  from (values ('owner_private'),('agent_operational'),('tenant_shared'),
    ('published_knowledge'),('session_scoped'),('public_catalog')) required(data_class)
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true);
  select count(*) into v_missing_sources from private.account_export_sources s
  left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
  where s.enabled=true and (p.source_key is null or p.data_class is null
    or p.deletion_action is null
    or (p.deletion_action='block' and private.account_deletion_source_has_user_rows(s.source_key,v_request.user_id)));
  select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action='block'
      and private.account_deletion_fk_has_unresolved_user_rows(r.id,v_request.user_id);
  if coalesce(cardinality(v_missing_classes),0)>0 or v_missing_sources>0 or v_blocked_fks>0 then
    update public.account_deletion_requests set status='blocked_dependency',scheduled_for=null,
      error_code='DELETION_POLICY_OR_DEPENDENCY_MAP_INCOMPLETE',
      request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
        'missing_data_classes',coalesce(to_jsonb(v_missing_classes),'[]'::jsonb),
        'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks,
        'checked_at',clock_timestamp()),updated_at=clock_timestamp() where id=p_request_id;
    return jsonb_build_object('outcome','blocked_dependency',
      'missing_data_classes',coalesce(to_jsonb(v_missing_classes),'[]'::jsonb),
      'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks);
  end if;
  select coalesce(jsonb_object_agg(p.data_class,p.policy_version),'{}'::jsonb)
    into v_policy_snapshot from public.account_data_retention_policies p where p.active=true;
  insert into public.account_deletion_execution_jobs(request_id,user_id,subject_ref,status,policy_snapshot)
  values(p_request_id,v_request.user_id,v_request.subject_ref,'queued',v_policy_snapshot)
  on conflict(request_id) do update set status='queued',error_code=null,lease_token=null,
    lease_owner=null,lease_expires_at=null,policy_snapshot=excluded.policy_snapshot,updated_at=clock_timestamp()
  returning * into v_job;
  delete from public.account_deletion_execution_steps where job_id=v_job.id;
  insert into public.account_deletion_execution_steps(job_id,step_kind,step_key,action,data_class,dependency_order)
  select v_job.id,'source',p.source_key,p.deletion_action,p.data_class,p.dependency_order
  from public.account_deletion_source_policies p join private.account_export_sources s
    on s.source_key=p.source_key and s.enabled=true where p.active=true;
  insert into public.account_deletion_execution_steps(job_id,step_kind,step_key,action,dependency_order)
  select v_job.id,'foreign_key',r.id::text,r.resolution_action,
    -10000+row_number() over(order by r.child_schema,r.child_table,r.constraint_name)
  from public.account_deletion_dependency_rules r where r.active=true;

  insert into public.account_deletion_storage_jobs(execution_job_id,source_key,storage_bucket,storage_path)
  select v_job.id,'agent_knowledge_sources','agent-knowledge',s.storage_path from public.agent_knowledge_sources s
  where s.owner_id=v_request.user_id and s.storage_path<>'' and left(s.storage_path,1)<>'/'
    and position('..' in s.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,source_key,storage_bucket,storage_path)
  select v_job.id,'content_media',m.bucket_id,m.storage_path from public.content_media m
  where m.owner_id=v_request.user_id and m.storage_path<>'' and left(m.storage_path,1)<>'/'
    and position('..' in m.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,source_key,storage_bucket,storage_path)
  select v_job.id,'content_media',m.bucket_id,d.value->>'storage_path' from public.content_media m
  cross join lateral jsonb_array_elements(case when jsonb_typeof(m.derivatives)='array' then m.derivatives else '[]'::jsonb end) d(value)
  where m.owner_id=v_request.user_id and jsonb_typeof(d.value)='object'
    and coalesce(d.value->>'storage_path','')<>'' and left(d.value->>'storage_path',1)<>'/'
    and position('..' in d.value->>'storage_path')=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,source_key,storage_bucket,storage_path)
  select v_job.id,'generation_artifacts',a.storage_bucket,a.storage_path from public.generation_artifacts a
  where a.owner_user_id=v_request.user_id and a.storage_path<>'' and left(a.storage_path,1)<>'/'
    and position('..' in a.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,source_key,storage_bucket,storage_path)
  select v_job.id,'account_export_jobs',j.storage_bucket,j.storage_path from public.account_export_jobs j
  where j.user_id=v_request.user_id and j.status='succeeded' and j.storage_path is not null
    and j.storage_bucket='account-exports' and j.storage_path<>'' and left(j.storage_path,1)<>'/'
    and position('..' in j.storage_path)=0 on conflict do nothing;
  update public.account_deletion_storage_jobs set status='pending',lease_token=null,lease_expires_at=null,error_code=null
    where execution_job_id=v_job.id and status='failed';

  update public.account_deletion_requests set status='processing',error_code=null,
    policy_version='account-deletion-v1',
    request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
      'execution_job_id',v_job.id,'policy_snapshot',v_policy_snapshot,
      'storage_cleanup_queued',true,'prepared_at',clock_timestamp()),updated_at=clock_timestamp()
  where id=p_request_id;
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values(p_request_id,v_request.user_id,v_request.subject_ref,'deletion_started',
    jsonb_build_object('execution_job_id',v_job.id,'policy_snapshot',v_policy_snapshot));
  return jsonb_build_object('outcome','queued','job_id',v_job.id);
end;
$function$

CREATE OR REPLACE FUNCTION public.execute_account_deletion_execution_job(p_job_id uuid, p_lease_token uuid)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_job public.account_deletion_execution_jobs%rowtype;
        v_request public.account_deletion_requests%rowtype;
        v_step public.account_deletion_execution_steps%rowtype;
        v_source private.account_export_sources%rowtype;
        v_policy public.account_deletion_source_policies%rowtype;
        v_rule public.account_deletion_dependency_rules%rowtype;
        v_column text; v_predicate text; v_sql text; v_rows bigint;
        v_missing_classes integer; v_blocked_fks integer; v_missing_sources integer; v_missing_fk_steps integer;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_job from public.account_deletion_execution_jobs
   where id=p_job_id and status='running' and lease_token=p_lease_token
     and lease_expires_at>clock_timestamp() for update;
  if not found then raise exception 'account_deletion_execution_lease_lost' using errcode='40001'; end if;
  select * into v_request from public.account_deletion_requests where id=v_job.request_id for update;
  if not found or v_request.user_id is distinct from v_job.user_id then
    raise exception 'account_deletion_request_subject_mismatch' using errcode='23514';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_job.subject_ref,0));
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  if exists(select 1 from public.account_deletion_storage_jobs s
            where s.execution_job_id=v_job.id and s.status not in ('completed','preserved')) then
    raise exception 'account_deletion_storage_cleanup_incomplete' using errcode='55000';
  end if;
  select count(*) into v_missing_classes from (values
    ('owner_private'),('agent_operational'),('tenant_shared'),
    ('published_knowledge'),('session_scoped'),('public_catalog')
  ) required(data_class)
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true
      and p.policy_version=v_job.policy_snapshot->>required.data_class);
  select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action='block'
      and private.account_deletion_fk_has_unresolved_user_rows(r.id,v_job.user_id);
  select count(*) into v_missing_sources from private.account_export_sources s
    left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
    where s.enabled=true and (p.source_key is null or p.data_class is null
      or p.deletion_action is null
      or (p.deletion_action='block' and private.account_deletion_source_has_user_rows(s.source_key,v_job.user_id)));
  select count(*) into v_missing_fk_steps from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action not in ('database_cascade','database_set_null')
      and not exists(select 1 from public.account_deletion_execution_steps st
        where st.job_id=v_job.id and st.step_kind='foreign_key' and st.step_key=r.id::text);
  if v_missing_classes>0 or v_blocked_fks>0 or v_missing_sources>0 or v_missing_fk_steps>0 then
    update public.account_deletion_execution_jobs set status='blocked',error_code='DELETION_POLICY_CHANGED',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_dependency',error_code='DELETION_POLICY_CHANGED',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  for v_step in select * from public.account_deletion_execution_steps
    where job_id=v_job.id and status='pending'
    order by dependency_order desc,step_kind desc,step_key for update
  loop
    v_rows:=0;
    if v_step.step_kind='source' then
      select * into v_policy from public.account_deletion_source_policies
       where source_key=v_step.step_key and active=true;
      if not found or v_policy.deletion_action is distinct from v_step.action
         or v_policy.data_class is distinct from v_step.data_class then
        raise exception 'account_deletion_source_policy_changed:%',v_step.step_key using errcode='40001';
      end if;
      if v_step.action='preserve' then
        v_rows:=0;
      elsif v_step.action='delete_rows' then
        select * into v_source from private.account_export_sources
         where source_key=v_step.step_key and enabled=true;
        if not found then
          raise exception 'account_deletion_source_handler_missing:%',v_step.step_key using errcode='0A000';
        end if;
        if v_source.filter_kind='owner_columns' then
          if cardinality(v_source.owner_columns)=0 then
            raise exception 'account_deletion_source_handler_missing:%',v_step.step_key using errcode='0A000';
          end if;
          v_predicate:='';
          foreach v_column in array v_source.owner_columns loop
            if not exists(select 1 from information_schema.columns c
              where c.table_schema='public' and c.table_name=v_source.table_name and c.column_name=v_column) then
              raise exception 'account_deletion_source_column_missing:%.%',v_source.table_name,v_column;
            end if;
            if v_predicate<>'' then v_predicate:=v_predicate||' OR '; end if;
            v_predicate:=v_predicate||format('%I::text = $1',v_column);
          end loop;
          v_sql:=format('DELETE FROM public.%I WHERE %s',v_source.table_name,v_predicate);
          execute v_sql using v_job.user_id::text;
          get diagnostics v_rows=row_count;
        else
          v_rows:=private.delete_account_source_rows(v_step.step_key,v_job.user_id);
        end if;
      else
        raise exception 'account_deletion_source_action_unsupported:%',v_step.action using errcode='0A000';
      end if;
    elsif v_step.step_kind='foreign_key' then
      select * into v_rule from public.account_deletion_dependency_rules
       where id::text=v_step.step_key and active=true;
      if not found or v_rule.resolution_action is distinct from v_step.action then
        raise exception 'account_deletion_dependency_rule_changed:%',v_step.step_key using errcode='40001';
      end if;
      if v_step.action in ('database_cascade','database_set_null') then
        v_rows:=0;
      elsif v_step.action='block' then
        if private.account_deletion_fk_has_unresolved_user_rows(v_rule.id,v_job.user_id) then
          raise exception 'account_deletion_dependency_unresolved:%',v_rule.constraint_name using errcode='55000';
        end if;
        v_rows:=0;
      elsif v_step.action in ('delete_rows','set_null') then
        if v_rule.fk_column is null then raise exception 'composite_foreign_key_requires_manual_handler'; end if;
        if v_step.action='delete_rows' then
          if v_rule.delete_rule not in ('RESTRICT','NO ACTION') then
            raise exception 'account_deletion_fk_action_incompatible:%',v_rule.constraint_name using errcode='55000';
          end if;
          if not exists (
            select 1 from pg_constraint c
             where c.conname=v_rule.constraint_name
               and c.conrelid=to_regclass(format('%I.%I',v_rule.child_schema,v_rule.child_table))
               and c.contype='f' and c.confrelid='auth.users'::regclass
               and cardinality(c.conkey)=1 and cardinality(c.confkey)=1
               and (select a.attname from pg_attribute a where a.attrelid=c.conrelid and a.attnum=c.conkey[1])=v_rule.fk_column
               and (select a.attname from pg_attribute a where a.attrelid=c.confrelid and a.attnum=c.confkey[1])='id'
          ) then
            raise exception 'account_deletion_fk_parent_not_auth_user:%',v_rule.constraint_name using errcode='55000';
          end if;
          v_sql:=format('DELETE FROM %I.%I WHERE %I::text = $1',v_rule.child_schema,v_rule.child_table,v_rule.fk_column);
        else
          if v_rule.delete_rule <> 'SET NULL' then
            raise exception 'account_deletion_fk_action_incompatible:%',v_rule.constraint_name using errcode='55000';
          end if;
          if not exists (
            select 1 from pg_constraint c
             where c.conname=v_rule.constraint_name
               and c.conrelid=to_regclass(format('%I.%I',v_rule.child_schema,v_rule.child_table))
               and c.contype='f' and c.confrelid='auth.users'::regclass
               and cardinality(c.conkey)=1 and cardinality(c.confkey)=1
               and (select a.attname from pg_attribute a where a.attrelid=c.conrelid and a.attnum=c.conkey[1])=v_rule.fk_column
               and (select a.attname from pg_attribute a where a.attrelid=c.confrelid and a.attnum=c.confkey[1])='id'
          ) then
            raise exception 'account_deletion_fk_parent_not_auth_user:%',v_rule.constraint_name using errcode='55000';
          end if;
          v_sql:=format('UPDATE %I.%I SET %I=NULL WHERE %I::text = $1',
            v_rule.child_schema,v_rule.child_table,v_rule.fk_column,v_rule.fk_column);
        end if;
        execute v_sql using v_job.user_id::text;
        get diagnostics v_rows=row_count;
      else
        raise exception 'account_deletion_dependency_unresolved:%',v_rule.constraint_name using errcode='55000';
      end if;
    else
      raise exception 'account_deletion_step_kind_invalid';
    end if;
    update public.account_deletion_execution_steps set status='completed',
      affected_rows=v_rows,completed_at=clock_timestamp() where id=v_step.id;
  end loop;
  if exists(select 1 from public.account_deletion_execution_steps where job_id=v_job.id and status<>'completed') then
    raise exception 'account_deletion_steps_incomplete' using errcode='55000';
  end if;
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  delete from auth.users where id=v_job.user_id;
  if not found then raise exception 'account_deletion_auth_subject_missing' using errcode='P0002'; end if;
  update public.account_deletion_requests set status='completed',user_id=null,completed_at=clock_timestamp(),
    error_code=null,request_metadata=coalesce(request_metadata,'{}'::jsonb)||
      jsonb_build_object('execution_job_id',v_job.id,'completed_at',clock_timestamp()),
    updated_at=clock_timestamp() where id=v_request.id;
  insert into public.account_lifecycle_events(request_id,subject_ref,event_type,metadata)
  values(v_request.id,v_job.subject_ref,'deletion_completed',
    jsonb_build_object('execution_job_id',v_job.id,'steps_completed',
      (select count(*) from public.account_deletion_execution_steps where job_id=v_job.id)));
  update public.account_deletion_execution_jobs set status='completed',completed_at=clock_timestamp(),
    lease_token=null,lease_owner=null,lease_expires_at=null,error_code=null,updated_at=clock_timestamp()
  where id=v_job.id;
  return true;
end;
$function$

