-- SOURCE ONLY — WP-07 external Consumer generation and atomic dual-account completion.
-- Depends on the WP-07 generation job and external Consumer schema migrations.
-- The migration remains unapplied until an explicitly approved isolated database is available.
begin;

create or replace function public.generation_create_job(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_requester uuid := (p_command->>'owner_user_id')::uuid;
  v_agent_owner uuid := (p_command->>'agent_owner_user_id')::uuid;
  v_payer uuid := (p_command->>'payer_user_id')::uuid;
  v_agent uuid := (p_command->>'agent_id')::uuid;
  v_skill uuid := (p_command->>'skill_id')::uuid;
  v_grant uuid := nullif(p_command->>'consumer_grant_id','')::uuid;
  v_task text := p_command->>'task_id';
  v_key text := p_command->>'idempotency_key';
  v_existing public.generation_jobs;
  v_job public.generation_jobs;
  v_reservation jsonb;
  v_reservation_id uuid;
  v_agent_row public.ai_agents;
  v_skill_row public.agent_skills;
begin
  if v_requester is null or v_agent_owner is null or v_payer is null
    or v_agent is null or v_skill is null
    or coalesce(v_task,'')='' or coalesce(v_key,'')=''
    or coalesce(p_command->>'prompt','')=''
    or coalesce(p_command->>'prompt_sha256','') !~ '^[0-9a-f]{64}$' then
    raise exception 'GENERATION_JOB_COMMAND_INVALID' using errcode='22023';
  end if;

  select * into v_existing from public.generation_jobs
    where owner_user_id=v_requester and idempotency_key=v_key for update;
  if found then
    if v_existing.prompt_sha256 <> p_command->>'prompt_sha256'
      or coalesce(v_existing.knowledge_context_sha256,'') <> coalesce(p_command->>'knowledge_context_sha256','')
      or v_existing.agent_id <> v_agent or v_existing.skill_id <> v_skill
      or v_existing.agent_owner_user_id <> v_agent_owner
      or v_existing.payer_user_id <> v_payer
      or v_existing.consumer_grant_id is distinct from v_grant
      or v_existing.capability_id <> p_command->>'capability_id'
      or v_existing.source_version <> (p_command->>'source_version')::integer
      or v_existing.policy_version <> p_command->>'policy_version'
      or v_existing.tariff_version <> p_command->>'tariff_version'
      or v_existing.entitlement_version <> p_command->>'entitlement_version'
      or v_existing.model_id <> p_command->>'model_id'
      or v_existing.model_version <> p_command->>'model_version' then
      raise exception 'GENERATION_JOB_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('job_id',v_existing.id,'task_id',v_existing.task_id,
      'reservation_id',v_existing.reservation_id,'reserved_credits',v_existing.credits_to_reserve,
      'status',v_existing.status,'idempotent_replay',true);
  end if;

  select * into v_agent_row from public.ai_agents where id=v_agent and status='active' for share;
  select * into v_skill_row from public.agent_skills
    where id=v_skill and agent_id=v_agent and status='published' for share;
  if not found or v_skill_row.version <> (p_command->>'source_version')::integer then
    raise exception 'GENERATION_SKILL_NOT_PUBLISHED_OR_VERSION_CHANGED' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.agent_capabilities c
    where c.agent_id=v_agent and c.capability_key=p_command->>'capability_id' and c.status='approved'
  ) then raise exception 'GENERATION_CAPABILITY_NOT_APPROVED' using errcode='42501'; end if;
  if not exists (
    select 1 from public.agent_ownerships o
    where o.agent_id=v_agent and o.owner_user_id=v_agent_owner
      and o.ownership_role='owner' and o.status='active'
  ) then raise exception 'GENERATION_AGENT_OWNER_REQUIRED' using errcode='42501'; end if;

  if v_requester = v_agent_owner then
    if v_grant is not null or v_payer <> v_agent_owner
      or coalesce(p_command->>'payer_role','') <> 'agent_owner' then
      raise exception 'GENERATION_OWNER_BILLING_CONTEXT_INVALID' using errcode='42501';
    end if;
  else
    if v_grant is null or v_agent_row.visibility <> 'public'
      or coalesce(p_command->>'sensitivity','') <> 'public' then
      raise exception 'GENERATION_EXTERNAL_AGENT_NOT_PUBLIC' using errcode='42501';
    end if;
    if not exists (
      select 1 from public.agent_consumer_grants g
      where g.id=v_grant and g.requester_user_id=v_requester
        and g.owner_user_id=v_agent_owner and g.agent_id=v_agent
        and g.agent_version=v_agent_row.version
        and g.skill_id=v_skill and g.skill_version=v_skill_row.version
        and g.runtime_policy_version=p_command->>'runtime_policy_version'
        and g.status='active' and g.granted_scopes @> array['generation_invoke']::text[]
        and (coalesce(p_command->>'knowledge_context_sha256','')='' or g.granted_scopes @> array['knowledge_public_read']::text[])
        and (g.expires_at is null or g.expires_at > now())
        and g.capability_id=p_command->>'capability_id'
        and g.credit_scheme_version=p_command->>'credit_scheme_version'
        and g.approval_reference=p_command->>'policy_approval_reference'
        and g.tariff_version=p_command->>'tariff_version'
        and g.entitlement_version=p_command->>'entitlement_version'
        and g.max_usage_units >= (p_command->>'estimated_usage_units')::bigint
        and g.max_cost_microunits >= (p_command->>'max_cost_microunits')::bigint
        and g.cost_unit=p_command->>'cost_unit'
        and g.pricing_version=p_command->>'pricing_version'
        and g.payer_role=p_command->>'payer_role'
        and g.allow_success_settlement=(p_command->>'allow_success_settlement')::boolean
        and g.allow_definitive_failure_release=(p_command->>'allow_definitive_failure_release')::boolean
        and g.allow_partial_settlement=(p_command->>'allow_partial_settlement')::boolean
    ) then raise exception 'GENERATION_CONSUMER_GRANT_INVALID_OR_REVOKED' using errcode='42501'; end if;
    if (p_command->>'payer_role'='consumer' and v_payer<>v_requester)
      or (p_command->>'payer_role'='agent_owner' and v_payer<>v_agent_owner)
      or p_command->>'payer_role' not in ('consumer','agent_owner') then
      raise exception 'GENERATION_PAYER_ROLE_INVALID' using errcode='42501';
    end if;
  end if;

  if v_payer <> v_agent_owner and not exists (
    select 1 from public.credit_policy_versions p
    where p.policy_version=p_command->>'policy_version'
      and p.approval_reference=p_command->>'policy_approval_reference'
      and p.status='approved'
      and p.configuration->'generation_owner_reward'->>'enabled'='true'
      and coalesce(p.configuration->'generation_owner_reward'->>'approval_reference','')=p.approval_reference
      and coalesce(p.configuration->'generation_owner_reward'->>'credits_per_usage_unit','') ~ '^[1-9][0-9]*      and s.entitlement_version=p_command->>'entitlement_version'
      and s.current_period_end > now()
  ) then raise exception 'GENERATION_PREMIUM_ENTITLEMENT_REQUIRED' using errcode='42501'; end if;

  v_reservation := public.credit_ledger_reserve(jsonb_build_object(
    'owner_user_id',v_payer,
    'idempotency_key','generation-reserve:'||v_task,
    'task_id',v_task,
    'capability_id',p_command->>'capability_id',
    'credits_to_reserve',(p_command->>'credits_to_reserve')::bigint,
    'estimated_usage_units',(p_command->>'estimated_usage_units')::bigint,
    'usage_unit',p_command->>'usage_unit',
    'estimated_cost_microunits',(p_command->>'estimated_cost_microunits')::bigint,
    'cost_unit',p_command->>'cost_unit',
    'credit_scheme_version',p_command->>'credit_scheme_version',
    'tariff_version',p_command->>'tariff_version',
    'entitlement_version',p_command->>'entitlement_version',
    'policy_version',p_command->>'policy_version',
    'policy_approval_reference',p_command->>'policy_approval_reference'
  ));
  v_reservation_id := (v_reservation->>'reservation_id')::uuid;

  insert into public.generation_jobs(
    owner_user_id,agent_owner_user_id,payer_user_id,consumer_grant_id,
    agent_id,skill_id,source_version,capability_id,sensitivity,task_id,trace_id,idempotency_key,
    prompt,prompt_sha256,knowledge_snapshot,knowledge_context_sha256,max_output_tokens,timeout_ms,
    estimated_usage_units,usage_unit,estimated_cost_microunits,cost_unit,credits_to_reserve,
    credits_per_usage_unit,credit_scheme_version,tariff_version,entitlement_version,policy_version,
    policy_approval_reference,allow_success_settlement,allow_definitive_failure_release,
    allow_partial_settlement,reservation_id,provider_id,model_id,model_version,pricing_version,max_cost_microunits
  ) values (
    v_requester,v_agent_owner,v_payer,v_grant,
    v_agent,v_skill,(p_command->>'source_version')::integer,p_command->>'capability_id',
    p_command->>'sensitivity',v_task,p_command->>'trace_id',v_key,p_command->>'prompt',
    p_command->>'prompt_sha256',coalesce(p_command->'knowledge_snapshot','{}'::jsonb),
    nullif(p_command->>'knowledge_context_sha256',''),(p_command->>'max_output_tokens')::integer,
    (p_command->>'timeout_ms')::integer,(p_command->>'estimated_usage_units')::bigint,
    p_command->>'usage_unit',(p_command->>'estimated_cost_microunits')::bigint,p_command->>'cost_unit',
    (p_command->>'credits_to_reserve')::bigint,(p_command->>'credits_per_usage_unit')::bigint,
    p_command->>'credit_scheme_version',p_command->>'tariff_version',p_command->>'entitlement_version',
    p_command->>'policy_version',p_command->>'policy_approval_reference',
    (p_command->>'allow_success_settlement')::boolean,(p_command->>'allow_definitive_failure_release')::boolean,
    (p_command->>'allow_partial_settlement')::boolean,v_reservation_id,p_command->>'provider_id',
    p_command->>'model_id',p_command->>'model_version',p_command->>'pricing_version',
    (p_command->>'max_cost_microunits')::bigint
  ) returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'task_id',v_job.task_id,
    'reservation_id',v_job.reservation_id,'reserved_credits',v_job.credits_to_reserve,
    'status',v_job.status,'idempotent_replay',false);
end;
$$;

create or replace function public.generation_complete_job(
  p_job_id uuid,p_lease_token uuid,p_result jsonb
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_job public.generation_jobs;
  v_policy public.credit_policy_versions;
  v_reward jsonb;
  v_actual_units bigint;
  v_actual_credits bigint;
  v_reward_credits bigint;
  v_reward_status text := 'pending_policy';
  v_conversation_id uuid;
  v_message_id uuid;
begin
  select * into v_job from public.generation_jobs
    where id=p_job_id and status='running' and lease_token=p_lease_token
      and lease_expires_at > now() for update;
  if not found then raise exception 'GENERATION_JOB_LEASE_LOST' using errcode='40001'; end if;
  if v_job.artifact_bucket <> 'generation-artifacts' or v_job.artifact_path is null
    or v_job.moderation_status <> 'approved' or v_job.moderation_policy_version is null
    or coalesce((p_result->>'input_tokens')::bigint,-1) < 0
    or coalesce((p_result->>'output_tokens')::bigint,-1) < 0
    or coalesce(p_result->>'source_event_id','')='' then
    raise exception 'GENERATION_JOB_RESULT_INVALID' using errcode='22023';
  end if;

  v_actual_units := (p_result->>'input_tokens')::bigint + (p_result->>'output_tokens')::bigint;
  v_actual_credits := v_actual_units * v_job.credits_per_usage_unit;
  if v_actual_units <= 0 or v_actual_credits > v_job.credits_to_reserve then
    raise exception 'GENERATION_ACTUAL_USAGE_EXCEEDS_RESERVATION' using errcode='22023';
  end if;

  -- Re-check external permission immediately before settlement and delivery.
  -- Revocation during a running provider call prevents publication and leaves
  -- the reservation for explicit reconciliation; no output is sent to the consumer.
  if v_job.consumer_grant_id is not null and not exists (
    select 1 from public.agent_consumer_grants g
    where g.id=v_job.consumer_grant_id
      and g.requester_user_id=v_job.owner_user_id
      and g.owner_user_id=v_job.agent_owner_user_id
      and g.agent_id=v_job.agent_id
      and g.status='active'
      and g.granted_scopes @> array['generation_invoke']::text[]
      and (v_job.knowledge_context_sha256 is null or g.granted_scopes @> array['knowledge_public_read']::text[])
      and (g.expires_at is null or g.expires_at > now())
  ) then
    raise exception 'GENERATION_CONSUMER_GRANT_REVOKED' using errcode='42501';
  end if;

  -- The debit/settlement and creator reward credit are in this same PostgreSQL
  -- transaction. No client-supplied payer or reward amount is trusted.
  perform public.credit_ledger_settle(jsonb_build_object(
    'reservation_id',v_job.reservation_id,
    'idempotency_key','generation-settlement:'||v_job.task_id,
    'policy_version',v_job.policy_version,
    'source_event_id',p_result->>'source_event_id',
    'actual_credits',v_actual_credits,
    'actual_usage_units',v_actual_units,
    'usage_unit',v_job.usage_unit,
    'release_unused',v_actual_credits < v_job.credits_to_reserve
  ));

  if v_job.payer_user_id <> v_job.agent_owner_user_id then
    select * into v_policy from public.credit_policy_versions
      where policy_version=v_job.policy_version
        and approval_reference=v_job.policy_approval_reference
        and status in ('approved','retired') for share;
    if not found then raise exception 'GENERATION_REWARD_POLICY_NOT_FOUND' using errcode='42501'; end if;
    v_reward := v_policy.configuration->'generation_owner_reward';
    if coalesce((v_reward->>'enabled')::boolean,false) then
      if coalesce(v_reward->>'approval_reference','') <> v_job.policy_approval_reference
        or coalesce((v_reward->>'credits_per_usage_unit')::bigint,0) <= 0
        or coalesce((v_reward->>'max_credits_per_job')::bigint,0) <= 0 then
        raise exception 'GENERATION_OWNER_REWARD_POLICY_INVALID' using errcode='42501';
      end if;
      v_reward_credits := v_actual_units * (v_reward->>'credits_per_usage_unit')::bigint;
      if v_reward_credits <= 0 or v_reward_credits > (v_reward->>'max_credits_per_job')::bigint then
        raise exception 'GENERATION_OWNER_REWARD_EXCEEDS_APPROVED_POLICY' using errcode='23514';
      end if;
      perform public.credit_ledger_grant(jsonb_build_object(
        'owner_user_id',v_job.agent_owner_user_id,
        'idempotency_key','generation-owner-reward:'||v_job.task_id,
        'entry_type','grant','credits',v_reward_credits,
        'policy_version',v_job.policy_version,
        'policy_approval_reference',v_job.policy_approval_reference,
        'capability_id','agent_owner_generation_reward',
        'source_event_id',p_result->>'source_event_id',
        'metadata',jsonb_build_object('generation_job_id',v_job.id,'payer_user_id',v_job.payer_user_id,
          'requester_user_id',v_job.owner_user_id,'agent_id',v_job.agent_id,'actual_usage_units',v_actual_units)
      ));
      v_reward_status := 'settled';
    end if;
  else
    v_reward_status := 'not_eligible';
  end if;

  insert into public.conversations(kind,title,created_by)
  values ('agent','Hasil Generate AI',v_job.owner_user_id)
  returning id into v_conversation_id;
  insert into public.conversation_participants(conversation_id,user_id,participant_type)
  values (v_conversation_id,v_job.owner_user_id,'human');
  insert into public.conversation_participants(conversation_id,agent_id,participant_type)
  values (v_conversation_id,v_job.agent_id,'agent');
  insert into public.messages(
    conversation_id,sender_type,sender_agent_id,body,client_message_id,delivery_status,generation_job_id
  ) values (
    v_conversation_id,'agent',v_job.agent_id,
    'Hasil Generate AI sudah siap. Artefak privat dapat dibuka melalui tombol hasil di percakapan ini.',
    v_job.id,'sent',v_job.id
  ) returning id into v_message_id;
  update public.conversations set last_message_at=now(),updated_at=now()
    where id=v_conversation_id;

  update public.generation_jobs set status='succeeded',
    input_tokens=(p_result->>'input_tokens')::bigint,
    output_tokens=(p_result->>'output_tokens')::bigint,
    actual_cost_microunits=(p_result->>'cost_microunits')::bigint,
    owner_reward_status=v_reward_status,
    dm_conversation_id=v_conversation_id,dm_message_id=v_message_id,dm_delivered_at=now(),
    completed_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
    where id=p_job_id returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'status',v_job.status,
    'owner_reward_status',v_job.owner_reward_status,
    'dm_conversation_id',v_job.dm_conversation_id,'dm_message_id',v_job.dm_message_id);
end;
$$;

revoke all on function public.generation_create_job(jsonb),
  public.generation_complete_job(uuid,uuid,jsonb)
  from public,anon,authenticated;
grant execute on function public.generation_create_job(jsonb),
  public.generation_complete_job(uuid,uuid,jsonb)
  to service_role;

commit;

      and coalesce(p.configuration->'generation_owner_reward'->>'max_credits_per_job','') ~ '^[1-9][0-9]*      and s.entitlement_version=p_command->>'entitlement_version'
      and s.current_period_end > now()
  ) then raise exception 'GENERATION_PREMIUM_ENTITLEMENT_REQUIRED' using errcode='42501'; end if;

  v_reservation := public.credit_ledger_reserve(jsonb_build_object(
    'owner_user_id',v_payer,
    'idempotency_key','generation-reserve:'||v_task,
    'task_id',v_task,
    'capability_id',p_command->>'capability_id',
    'credits_to_reserve',(p_command->>'credits_to_reserve')::bigint,
    'estimated_usage_units',(p_command->>'estimated_usage_units')::bigint,
    'usage_unit',p_command->>'usage_unit',
    'estimated_cost_microunits',(p_command->>'estimated_cost_microunits')::bigint,
    'cost_unit',p_command->>'cost_unit',
    'credit_scheme_version',p_command->>'credit_scheme_version',
    'tariff_version',p_command->>'tariff_version',
    'entitlement_version',p_command->>'entitlement_version',
    'policy_version',p_command->>'policy_version',
    'policy_approval_reference',p_command->>'policy_approval_reference'
  ));
  v_reservation_id := (v_reservation->>'reservation_id')::uuid;

  insert into public.generation_jobs(
    owner_user_id,agent_owner_user_id,payer_user_id,consumer_grant_id,
    agent_id,skill_id,source_version,capability_id,sensitivity,task_id,trace_id,idempotency_key,
    prompt,prompt_sha256,knowledge_snapshot,knowledge_context_sha256,max_output_tokens,timeout_ms,
    estimated_usage_units,usage_unit,estimated_cost_microunits,cost_unit,credits_to_reserve,
    credits_per_usage_unit,credit_scheme_version,tariff_version,entitlement_version,policy_version,
    policy_approval_reference,allow_success_settlement,allow_definitive_failure_release,
    allow_partial_settlement,reservation_id,provider_id,model_id,model_version,pricing_version,max_cost_microunits
  ) values (
    v_requester,v_agent_owner,v_payer,v_grant,
    v_agent,v_skill,(p_command->>'source_version')::integer,p_command->>'capability_id',
    p_command->>'sensitivity',v_task,p_command->>'trace_id',v_key,p_command->>'prompt',
    p_command->>'prompt_sha256',coalesce(p_command->'knowledge_snapshot','{}'::jsonb),
    nullif(p_command->>'knowledge_context_sha256',''),(p_command->>'max_output_tokens')::integer,
    (p_command->>'timeout_ms')::integer,(p_command->>'estimated_usage_units')::bigint,
    p_command->>'usage_unit',(p_command->>'estimated_cost_microunits')::bigint,p_command->>'cost_unit',
    (p_command->>'credits_to_reserve')::bigint,(p_command->>'credits_per_usage_unit')::bigint,
    p_command->>'credit_scheme_version',p_command->>'tariff_version',p_command->>'entitlement_version',
    p_command->>'policy_version',p_command->>'policy_approval_reference',
    (p_command->>'allow_success_settlement')::boolean,(p_command->>'allow_definitive_failure_release')::boolean,
    (p_command->>'allow_partial_settlement')::boolean,v_reservation_id,p_command->>'provider_id',
    p_command->>'model_id',p_command->>'model_version',p_command->>'pricing_version',
    (p_command->>'max_cost_microunits')::bigint
  ) returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'task_id',v_job.task_id,
    'reservation_id',v_job.reservation_id,'reserved_credits',v_job.credits_to_reserve,
    'status',v_job.status,'idempotent_replay',false);
end;
$$;

create or replace function public.generation_complete_job(
  p_job_id uuid,p_lease_token uuid,p_result jsonb
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_job public.generation_jobs;
  v_policy public.credit_policy_versions;
  v_reward jsonb;
  v_actual_units bigint;
  v_actual_credits bigint;
  v_reward_credits bigint;
  v_reward_status text := 'pending_policy';
  v_conversation_id uuid;
  v_message_id uuid;
begin
  select * into v_job from public.generation_jobs
    where id=p_job_id and status='running' and lease_token=p_lease_token
      and lease_expires_at > now() for update;
  if not found then raise exception 'GENERATION_JOB_LEASE_LOST' using errcode='40001'; end if;
  if v_job.artifact_bucket <> 'generation-artifacts' or v_job.artifact_path is null
    or v_job.moderation_status <> 'approved' or v_job.moderation_policy_version is null
    or coalesce((p_result->>'input_tokens')::bigint,-1) < 0
    or coalesce((p_result->>'output_tokens')::bigint,-1) < 0
    or coalesce(p_result->>'source_event_id','')='' then
    raise exception 'GENERATION_JOB_RESULT_INVALID' using errcode='22023';
  end if;

  v_actual_units := (p_result->>'input_tokens')::bigint + (p_result->>'output_tokens')::bigint;
  v_actual_credits := v_actual_units * v_job.credits_per_usage_unit;
  if v_actual_units <= 0 or v_actual_credits > v_job.credits_to_reserve then
    raise exception 'GENERATION_ACTUAL_USAGE_EXCEEDS_RESERVATION' using errcode='22023';
  end if;

  -- Re-check external permission immediately before settlement and delivery.
  -- Revocation during a running provider call prevents publication and leaves
  -- the reservation for explicit reconciliation; no output is sent to the consumer.
  if v_job.consumer_grant_id is not null and not exists (
    select 1 from public.agent_consumer_grants g
    where g.id=v_job.consumer_grant_id
      and g.requester_user_id=v_job.owner_user_id
      and g.owner_user_id=v_job.agent_owner_user_id
      and g.agent_id=v_job.agent_id
      and g.status='active'
      and g.granted_scopes @> array['generation_invoke']::text[]
      and (v_job.knowledge_context_sha256 is null or g.granted_scopes @> array['knowledge_public_read']::text[])
      and (g.expires_at is null or g.expires_at > now())
  ) then
    raise exception 'GENERATION_CONSUMER_GRANT_REVOKED' using errcode='42501';
  end if;

  -- The debit/settlement and creator reward credit are in this same PostgreSQL
  -- transaction. No client-supplied payer or reward amount is trusted.
  perform public.credit_ledger_settle(jsonb_build_object(
    'reservation_id',v_job.reservation_id,
    'idempotency_key','generation-settlement:'||v_job.task_id,
    'policy_version',v_job.policy_version,
    'source_event_id',p_result->>'source_event_id',
    'actual_credits',v_actual_credits,
    'actual_usage_units',v_actual_units,
    'usage_unit',v_job.usage_unit,
    'release_unused',v_actual_credits < v_job.credits_to_reserve
  ));

  if v_job.payer_user_id <> v_job.agent_owner_user_id then
    select * into v_policy from public.credit_policy_versions
      where policy_version=v_job.policy_version
        and approval_reference=v_job.policy_approval_reference
        and status in ('approved','retired') for share;
    if not found then raise exception 'GENERATION_REWARD_POLICY_NOT_FOUND' using errcode='42501'; end if;
    v_reward := v_policy.configuration->'generation_owner_reward';
    if coalesce((v_reward->>'enabled')::boolean,false) then
      if coalesce(v_reward->>'approval_reference','') <> v_job.policy_approval_reference
        or coalesce((v_reward->>'credits_per_usage_unit')::bigint,0) <= 0
        or coalesce((v_reward->>'max_credits_per_job')::bigint,0) <= 0 then
        raise exception 'GENERATION_OWNER_REWARD_POLICY_INVALID' using errcode='42501';
      end if;
      v_reward_credits := v_actual_units * (v_reward->>'credits_per_usage_unit')::bigint;
      if v_reward_credits <= 0 or v_reward_credits > (v_reward->>'max_credits_per_job')::bigint then
        raise exception 'GENERATION_OWNER_REWARD_EXCEEDS_APPROVED_POLICY' using errcode='23514';
      end if;
      perform public.credit_ledger_grant(jsonb_build_object(
        'owner_user_id',v_job.agent_owner_user_id,
        'idempotency_key','generation-owner-reward:'||v_job.task_id,
        'entry_type','grant','credits',v_reward_credits,
        'policy_version',v_job.policy_version,
        'policy_approval_reference',v_job.policy_approval_reference,
        'capability_id','agent_owner_generation_reward',
        'source_event_id',p_result->>'source_event_id',
        'metadata',jsonb_build_object('generation_job_id',v_job.id,'payer_user_id',v_job.payer_user_id,
          'requester_user_id',v_job.owner_user_id,'agent_id',v_job.agent_id,'actual_usage_units',v_actual_units)
      ));
      v_reward_status := 'settled';
    end if;
  else
    v_reward_status := 'not_eligible';
  end if;

  insert into public.conversations(kind,title,created_by)
  values ('agent','Hasil Generate AI',v_job.owner_user_id)
  returning id into v_conversation_id;
  insert into public.conversation_participants(conversation_id,user_id,participant_type)
  values (v_conversation_id,v_job.owner_user_id,'human');
  insert into public.conversation_participants(conversation_id,agent_id,participant_type)
  values (v_conversation_id,v_job.agent_id,'agent');
  insert into public.messages(
    conversation_id,sender_type,sender_agent_id,body,client_message_id,delivery_status,generation_job_id
  ) values (
    v_conversation_id,'agent',v_job.agent_id,
    'Hasil Generate AI sudah siap. Artefak privat dapat dibuka melalui tombol hasil di percakapan ini.',
    v_job.id,'sent',v_job.id
  ) returning id into v_message_id;
  update public.conversations set last_message_at=now(),updated_at=now()
    where id=v_conversation_id;

  update public.generation_jobs set status='succeeded',
    input_tokens=(p_result->>'input_tokens')::bigint,
    output_tokens=(p_result->>'output_tokens')::bigint,
    actual_cost_microunits=(p_result->>'cost_microunits')::bigint,
    owner_reward_status=v_reward_status,
    dm_conversation_id=v_conversation_id,dm_message_id=v_message_id,dm_delivered_at=now(),
    completed_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
    where id=p_job_id returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'status',v_job.status,
    'owner_reward_status',v_job.owner_reward_status,
    'dm_conversation_id',v_job.dm_conversation_id,'dm_message_id',v_job.dm_message_id);
end;
$$;

revoke all on function public.generation_create_job(jsonb),
  public.generation_complete_job(uuid,uuid,jsonb)
  from public,anon,authenticated;
grant execute on function public.generation_create_job(jsonb),
  public.generation_complete_job(uuid,uuid,jsonb)
  to service_role;

commit;

      and coalesce(p.configuration->>'max_grant_credits','') ~ '^[1-9][0-9]*      and s.entitlement_version=p_command->>'entitlement_version'
      and s.current_period_end > now()
  ) then raise exception 'GENERATION_PREMIUM_ENTITLEMENT_REQUIRED' using errcode='42501'; end if;

  v_reservation := public.credit_ledger_reserve(jsonb_build_object(
    'owner_user_id',v_payer,
    'idempotency_key','generation-reserve:'||v_task,
    'task_id',v_task,
    'capability_id',p_command->>'capability_id',
    'credits_to_reserve',(p_command->>'credits_to_reserve')::bigint,
    'estimated_usage_units',(p_command->>'estimated_usage_units')::bigint,
    'usage_unit',p_command->>'usage_unit',
    'estimated_cost_microunits',(p_command->>'estimated_cost_microunits')::bigint,
    'cost_unit',p_command->>'cost_unit',
    'credit_scheme_version',p_command->>'credit_scheme_version',
    'tariff_version',p_command->>'tariff_version',
    'entitlement_version',p_command->>'entitlement_version',
    'policy_version',p_command->>'policy_version',
    'policy_approval_reference',p_command->>'policy_approval_reference'
  ));
  v_reservation_id := (v_reservation->>'reservation_id')::uuid;

  insert into public.generation_jobs(
    owner_user_id,agent_owner_user_id,payer_user_id,consumer_grant_id,
    agent_id,skill_id,source_version,capability_id,sensitivity,task_id,trace_id,idempotency_key,
    prompt,prompt_sha256,knowledge_snapshot,knowledge_context_sha256,max_output_tokens,timeout_ms,
    estimated_usage_units,usage_unit,estimated_cost_microunits,cost_unit,credits_to_reserve,
    credits_per_usage_unit,credit_scheme_version,tariff_version,entitlement_version,policy_version,
    policy_approval_reference,allow_success_settlement,allow_definitive_failure_release,
    allow_partial_settlement,reservation_id,provider_id,model_id,model_version,pricing_version,max_cost_microunits
  ) values (
    v_requester,v_agent_owner,v_payer,v_grant,
    v_agent,v_skill,(p_command->>'source_version')::integer,p_command->>'capability_id',
    p_command->>'sensitivity',v_task,p_command->>'trace_id',v_key,p_command->>'prompt',
    p_command->>'prompt_sha256',coalesce(p_command->'knowledge_snapshot','{}'::jsonb),
    nullif(p_command->>'knowledge_context_sha256',''),(p_command->>'max_output_tokens')::integer,
    (p_command->>'timeout_ms')::integer,(p_command->>'estimated_usage_units')::bigint,
    p_command->>'usage_unit',(p_command->>'estimated_cost_microunits')::bigint,p_command->>'cost_unit',
    (p_command->>'credits_to_reserve')::bigint,(p_command->>'credits_per_usage_unit')::bigint,
    p_command->>'credit_scheme_version',p_command->>'tariff_version',p_command->>'entitlement_version',
    p_command->>'policy_version',p_command->>'policy_approval_reference',
    (p_command->>'allow_success_settlement')::boolean,(p_command->>'allow_definitive_failure_release')::boolean,
    (p_command->>'allow_partial_settlement')::boolean,v_reservation_id,p_command->>'provider_id',
    p_command->>'model_id',p_command->>'model_version',p_command->>'pricing_version',
    (p_command->>'max_cost_microunits')::bigint
  ) returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'task_id',v_job.task_id,
    'reservation_id',v_job.reservation_id,'reserved_credits',v_job.credits_to_reserve,
    'status',v_job.status,'idempotent_replay',false);
end;
$$;

create or replace function public.generation_complete_job(
  p_job_id uuid,p_lease_token uuid,p_result jsonb
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_job public.generation_jobs;
  v_policy public.credit_policy_versions;
  v_reward jsonb;
  v_actual_units bigint;
  v_actual_credits bigint;
  v_reward_credits bigint;
  v_reward_status text := 'pending_policy';
  v_conversation_id uuid;
  v_message_id uuid;
begin
  select * into v_job from public.generation_jobs
    where id=p_job_id and status='running' and lease_token=p_lease_token
      and lease_expires_at > now() for update;
  if not found then raise exception 'GENERATION_JOB_LEASE_LOST' using errcode='40001'; end if;
  if v_job.artifact_bucket <> 'generation-artifacts' or v_job.artifact_path is null
    or v_job.moderation_status <> 'approved' or v_job.moderation_policy_version is null
    or coalesce((p_result->>'input_tokens')::bigint,-1) < 0
    or coalesce((p_result->>'output_tokens')::bigint,-1) < 0
    or coalesce(p_result->>'source_event_id','')='' then
    raise exception 'GENERATION_JOB_RESULT_INVALID' using errcode='22023';
  end if;

  v_actual_units := (p_result->>'input_tokens')::bigint + (p_result->>'output_tokens')::bigint;
  v_actual_credits := v_actual_units * v_job.credits_per_usage_unit;
  if v_actual_units <= 0 or v_actual_credits > v_job.credits_to_reserve then
    raise exception 'GENERATION_ACTUAL_USAGE_EXCEEDS_RESERVATION' using errcode='22023';
  end if;

  -- Re-check external permission immediately before settlement and delivery.
  -- Revocation during a running provider call prevents publication and leaves
  -- the reservation for explicit reconciliation; no output is sent to the consumer.
  if v_job.consumer_grant_id is not null and not exists (
    select 1 from public.agent_consumer_grants g
    where g.id=v_job.consumer_grant_id
      and g.requester_user_id=v_job.owner_user_id
      and g.owner_user_id=v_job.agent_owner_user_id
      and g.agent_id=v_job.agent_id
      and g.status='active'
      and g.granted_scopes @> array['generation_invoke']::text[]
      and (v_job.knowledge_context_sha256 is null or g.granted_scopes @> array['knowledge_public_read']::text[])
      and (g.expires_at is null or g.expires_at > now())
  ) then
    raise exception 'GENERATION_CONSUMER_GRANT_REVOKED' using errcode='42501';
  end if;

  -- The debit/settlement and creator reward credit are in this same PostgreSQL
  -- transaction. No client-supplied payer or reward amount is trusted.
  perform public.credit_ledger_settle(jsonb_build_object(
    'reservation_id',v_job.reservation_id,
    'idempotency_key','generation-settlement:'||v_job.task_id,
    'policy_version',v_job.policy_version,
    'source_event_id',p_result->>'source_event_id',
    'actual_credits',v_actual_credits,
    'actual_usage_units',v_actual_units,
    'usage_unit',v_job.usage_unit,
    'release_unused',v_actual_credits < v_job.credits_to_reserve
  ));

  if v_job.payer_user_id <> v_job.agent_owner_user_id then
    select * into v_policy from public.credit_policy_versions
      where policy_version=v_job.policy_version
        and approval_reference=v_job.policy_approval_reference
        and status in ('approved','retired') for share;
    if not found then raise exception 'GENERATION_REWARD_POLICY_NOT_FOUND' using errcode='42501'; end if;
    v_reward := v_policy.configuration->'generation_owner_reward';
    if coalesce((v_reward->>'enabled')::boolean,false) then
      if coalesce(v_reward->>'approval_reference','') <> v_job.policy_approval_reference
        or coalesce((v_reward->>'credits_per_usage_unit')::bigint,0) <= 0
        or coalesce((v_reward->>'max_credits_per_job')::bigint,0) <= 0 then
        raise exception 'GENERATION_OWNER_REWARD_POLICY_INVALID' using errcode='42501';
      end if;
      v_reward_credits := v_actual_units * (v_reward->>'credits_per_usage_unit')::bigint;
      if v_reward_credits <= 0 or v_reward_credits > (v_reward->>'max_credits_per_job')::bigint then
        raise exception 'GENERATION_OWNER_REWARD_EXCEEDS_APPROVED_POLICY' using errcode='23514';
      end if;
      perform public.credit_ledger_grant(jsonb_build_object(
        'owner_user_id',v_job.agent_owner_user_id,
        'idempotency_key','generation-owner-reward:'||v_job.task_id,
        'entry_type','grant','credits',v_reward_credits,
        'policy_version',v_job.policy_version,
        'policy_approval_reference',v_job.policy_approval_reference,
        'capability_id','agent_owner_generation_reward',
        'source_event_id',p_result->>'source_event_id',
        'metadata',jsonb_build_object('generation_job_id',v_job.id,'payer_user_id',v_job.payer_user_id,
          'requester_user_id',v_job.owner_user_id,'agent_id',v_job.agent_id,'actual_usage_units',v_actual_units)
      ));
      v_reward_status := 'settled';
    end if;
  else
    v_reward_status := 'not_eligible';
  end if;

  insert into public.conversations(kind,title,created_by)
  values ('agent','Hasil Generate AI',v_job.owner_user_id)
  returning id into v_conversation_id;
  insert into public.conversation_participants(conversation_id,user_id,participant_type)
  values (v_conversation_id,v_job.owner_user_id,'human');
  insert into public.conversation_participants(conversation_id,agent_id,participant_type)
  values (v_conversation_id,v_job.agent_id,'agent');
  insert into public.messages(
    conversation_id,sender_type,sender_agent_id,body,client_message_id,delivery_status,generation_job_id
  ) values (
    v_conversation_id,'agent',v_job.agent_id,
    'Hasil Generate AI sudah siap. Artefak privat dapat dibuka melalui tombol hasil di percakapan ini.',
    v_job.id,'sent',v_job.id
  ) returning id into v_message_id;
  update public.conversations set last_message_at=now(),updated_at=now()
    where id=v_conversation_id;

  update public.generation_jobs set status='succeeded',
    input_tokens=(p_result->>'input_tokens')::bigint,
    output_tokens=(p_result->>'output_tokens')::bigint,
    actual_cost_microunits=(p_result->>'cost_microunits')::bigint,
    owner_reward_status=v_reward_status,
    dm_conversation_id=v_conversation_id,dm_message_id=v_message_id,dm_delivered_at=now(),
    completed_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
    where id=p_job_id returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'status',v_job.status,
    'owner_reward_status',v_job.owner_reward_status,
    'dm_conversation_id',v_job.dm_conversation_id,'dm_message_id',v_job.dm_message_id);
end;
$$;

revoke all on function public.generation_create_job(jsonb),
  public.generation_complete_job(uuid,uuid,jsonb)
  from public,anon,authenticated;
grant execute on function public.generation_create_job(jsonb),
  public.generation_complete_job(uuid,uuid,jsonb)
  to service_role;

commit;

      and p.configuration->>'allow_grants'='true'
      and coalesce(p.configuration->'allowed_grant_types','[]'::jsonb) ? 'grant'
      and (p.configuration->>'max_grant_credits')::bigint >=
          (p.configuration->'generation_owner_reward'->>'max_credits_per_job')::bigint
  ) then
    raise exception 'GENERATION_OWNER_REWARD_POLICY_NOT_APPROVED' using errcode='42501';
  end if;

  if not exists (
    select 1 from public.billing_subscriptions s
    where s.owner_user_id=v_payer and s.status='active'
      and s.entitlement_version=p_command->>'entitlement_version'
      and s.current_period_end > now()
  ) then raise exception 'GENERATION_PREMIUM_ENTITLEMENT_REQUIRED' using errcode='42501'; end if;

  v_reservation := public.credit_ledger_reserve(jsonb_build_object(
    'owner_user_id',v_payer,
    'idempotency_key','generation-reserve:'||v_task,
    'task_id',v_task,
    'capability_id',p_command->>'capability_id',
    'credits_to_reserve',(p_command->>'credits_to_reserve')::bigint,
    'estimated_usage_units',(p_command->>'estimated_usage_units')::bigint,
    'usage_unit',p_command->>'usage_unit',
    'estimated_cost_microunits',(p_command->>'estimated_cost_microunits')::bigint,
    'cost_unit',p_command->>'cost_unit',
    'credit_scheme_version',p_command->>'credit_scheme_version',
    'tariff_version',p_command->>'tariff_version',
    'entitlement_version',p_command->>'entitlement_version',
    'policy_version',p_command->>'policy_version',
    'policy_approval_reference',p_command->>'policy_approval_reference'
  ));
  v_reservation_id := (v_reservation->>'reservation_id')::uuid;

  insert into public.generation_jobs(
    owner_user_id,agent_owner_user_id,payer_user_id,consumer_grant_id,
    agent_id,skill_id,source_version,capability_id,sensitivity,task_id,trace_id,idempotency_key,
    prompt,prompt_sha256,knowledge_snapshot,knowledge_context_sha256,max_output_tokens,timeout_ms,
    estimated_usage_units,usage_unit,estimated_cost_microunits,cost_unit,credits_to_reserve,
    credits_per_usage_unit,credit_scheme_version,tariff_version,entitlement_version,policy_version,
    policy_approval_reference,allow_success_settlement,allow_definitive_failure_release,
    allow_partial_settlement,reservation_id,provider_id,model_id,model_version,pricing_version,max_cost_microunits
  ) values (
    v_requester,v_agent_owner,v_payer,v_grant,
    v_agent,v_skill,(p_command->>'source_version')::integer,p_command->>'capability_id',
    p_command->>'sensitivity',v_task,p_command->>'trace_id',v_key,p_command->>'prompt',
    p_command->>'prompt_sha256',coalesce(p_command->'knowledge_snapshot','{}'::jsonb),
    nullif(p_command->>'knowledge_context_sha256',''),(p_command->>'max_output_tokens')::integer,
    (p_command->>'timeout_ms')::integer,(p_command->>'estimated_usage_units')::bigint,
    p_command->>'usage_unit',(p_command->>'estimated_cost_microunits')::bigint,p_command->>'cost_unit',
    (p_command->>'credits_to_reserve')::bigint,(p_command->>'credits_per_usage_unit')::bigint,
    p_command->>'credit_scheme_version',p_command->>'tariff_version',p_command->>'entitlement_version',
    p_command->>'policy_version',p_command->>'policy_approval_reference',
    (p_command->>'allow_success_settlement')::boolean,(p_command->>'allow_definitive_failure_release')::boolean,
    (p_command->>'allow_partial_settlement')::boolean,v_reservation_id,p_command->>'provider_id',
    p_command->>'model_id',p_command->>'model_version',p_command->>'pricing_version',
    (p_command->>'max_cost_microunits')::bigint
  ) returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'task_id',v_job.task_id,
    'reservation_id',v_job.reservation_id,'reserved_credits',v_job.credits_to_reserve,
    'status',v_job.status,'idempotent_replay',false);
end;
$$;

create or replace function public.generation_complete_job(
  p_job_id uuid,p_lease_token uuid,p_result jsonb
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_job public.generation_jobs;
  v_policy public.credit_policy_versions;
  v_reward jsonb;
  v_actual_units bigint;
  v_actual_credits bigint;
  v_reward_credits bigint;
  v_reward_status text := 'pending_policy';
  v_conversation_id uuid;
  v_message_id uuid;
begin
  select * into v_job from public.generation_jobs
    where id=p_job_id and status='running' and lease_token=p_lease_token
      and lease_expires_at > now() for update;
  if not found then raise exception 'GENERATION_JOB_LEASE_LOST' using errcode='40001'; end if;
  if v_job.artifact_bucket <> 'generation-artifacts' or v_job.artifact_path is null
    or v_job.moderation_status <> 'approved' or v_job.moderation_policy_version is null
    or coalesce((p_result->>'input_tokens')::bigint,-1) < 0
    or coalesce((p_result->>'output_tokens')::bigint,-1) < 0
    or coalesce(p_result->>'source_event_id','')='' then
    raise exception 'GENERATION_JOB_RESULT_INVALID' using errcode='22023';
  end if;

  v_actual_units := (p_result->>'input_tokens')::bigint + (p_result->>'output_tokens')::bigint;
  v_actual_credits := v_actual_units * v_job.credits_per_usage_unit;
  if v_actual_units <= 0 or v_actual_credits > v_job.credits_to_reserve then
    raise exception 'GENERATION_ACTUAL_USAGE_EXCEEDS_RESERVATION' using errcode='22023';
  end if;

  -- Re-check external permission immediately before settlement and delivery.
  -- Revocation during a running provider call prevents publication and leaves
  -- the reservation for explicit reconciliation; no output is sent to the consumer.
  if v_job.consumer_grant_id is not null and not exists (
    select 1 from public.agent_consumer_grants g
    where g.id=v_job.consumer_grant_id
      and g.requester_user_id=v_job.owner_user_id
      and g.owner_user_id=v_job.agent_owner_user_id
      and g.agent_id=v_job.agent_id
      and g.status='active'
      and g.granted_scopes @> array['generation_invoke']::text[]
      and (v_job.knowledge_context_sha256 is null or g.granted_scopes @> array['knowledge_public_read']::text[])
      and (g.expires_at is null or g.expires_at > now())
  ) then
    raise exception 'GENERATION_CONSUMER_GRANT_REVOKED' using errcode='42501';
  end if;

  -- The debit/settlement and creator reward credit are in this same PostgreSQL
  -- transaction. No client-supplied payer or reward amount is trusted.
  perform public.credit_ledger_settle(jsonb_build_object(
    'reservation_id',v_job.reservation_id,
    'idempotency_key','generation-settlement:'||v_job.task_id,
    'policy_version',v_job.policy_version,
    'source_event_id',p_result->>'source_event_id',
    'actual_credits',v_actual_credits,
    'actual_usage_units',v_actual_units,
    'usage_unit',v_job.usage_unit,
    'release_unused',v_actual_credits < v_job.credits_to_reserve
  ));

  if v_job.payer_user_id <> v_job.agent_owner_user_id then
    select * into v_policy from public.credit_policy_versions
      where policy_version=v_job.policy_version
        and approval_reference=v_job.policy_approval_reference
        and status in ('approved','retired') for share;
    if not found then raise exception 'GENERATION_REWARD_POLICY_NOT_FOUND' using errcode='42501'; end if;
    v_reward := v_policy.configuration->'generation_owner_reward';
    if coalesce((v_reward->>'enabled')::boolean,false) then
      if coalesce(v_reward->>'approval_reference','') <> v_job.policy_approval_reference
        or coalesce((v_reward->>'credits_per_usage_unit')::bigint,0) <= 0
        or coalesce((v_reward->>'max_credits_per_job')::bigint,0) <= 0 then
        raise exception 'GENERATION_OWNER_REWARD_POLICY_INVALID' using errcode='42501';
      end if;
      v_reward_credits := v_actual_units * (v_reward->>'credits_per_usage_unit')::bigint;
      if v_reward_credits <= 0 or v_reward_credits > (v_reward->>'max_credits_per_job')::bigint then
        raise exception 'GENERATION_OWNER_REWARD_EXCEEDS_APPROVED_POLICY' using errcode='23514';
      end if;
      perform public.credit_ledger_grant(jsonb_build_object(
        'owner_user_id',v_job.agent_owner_user_id,
        'idempotency_key','generation-owner-reward:'||v_job.task_id,
        'entry_type','grant','credits',v_reward_credits,
        'policy_version',v_job.policy_version,
        'policy_approval_reference',v_job.policy_approval_reference,
        'capability_id','agent_owner_generation_reward',
        'source_event_id',p_result->>'source_event_id',
        'metadata',jsonb_build_object('generation_job_id',v_job.id,'payer_user_id',v_job.payer_user_id,
          'requester_user_id',v_job.owner_user_id,'agent_id',v_job.agent_id,'actual_usage_units',v_actual_units)
      ));
      v_reward_status := 'settled';
    end if;
  else
    v_reward_status := 'not_eligible';
  end if;

  insert into public.conversations(kind,title,created_by)
  values ('agent','Hasil Generate AI',v_job.owner_user_id)
  returning id into v_conversation_id;
  insert into public.conversation_participants(conversation_id,user_id,participant_type)
  values (v_conversation_id,v_job.owner_user_id,'human');
  insert into public.conversation_participants(conversation_id,agent_id,participant_type)
  values (v_conversation_id,v_job.agent_id,'agent');
  insert into public.messages(
    conversation_id,sender_type,sender_agent_id,body,client_message_id,delivery_status,generation_job_id
  ) values (
    v_conversation_id,'agent',v_job.agent_id,
    'Hasil Generate AI sudah siap. Artefak privat dapat dibuka melalui tombol hasil di percakapan ini.',
    v_job.id,'sent',v_job.id
  ) returning id into v_message_id;
  update public.conversations set last_message_at=now(),updated_at=now()
    where id=v_conversation_id;

  update public.generation_jobs set status='succeeded',
    input_tokens=(p_result->>'input_tokens')::bigint,
    output_tokens=(p_result->>'output_tokens')::bigint,
    actual_cost_microunits=(p_result->>'cost_microunits')::bigint,
    owner_reward_status=v_reward_status,
    dm_conversation_id=v_conversation_id,dm_message_id=v_message_id,dm_delivered_at=now(),
    completed_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
    where id=p_job_id returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'status',v_job.status,
    'owner_reward_status',v_job.owner_reward_status,
    'dm_conversation_id',v_job.dm_conversation_id,'dm_message_id',v_job.dm_message_id);
end;
$$;

revoke all on function public.generation_create_job(jsonb),
  public.generation_complete_job(uuid,uuid,jsonb)
  from public,anon,authenticated;
grant execute on function public.generation_create_job(jsonb),
  public.generation_complete_job(uuid,uuid,jsonb)
  to service_role;

commit;
