-- ENG-P03: qualify table columns that collide with RETURNS TABLE output parameters.
-- This fixes PL/pgSQL variable ambiguity without changing lifecycle behavior.
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
       where public.account_deletion_requests.id=v_request_id;
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
  returning public.account_deletion_requests.id into v_request_id;

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
   where public.account_deletion_requests.id=v_request_id;

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
        (select count(distinct p.data_class)=6
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
