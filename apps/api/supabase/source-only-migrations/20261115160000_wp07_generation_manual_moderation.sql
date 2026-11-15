-- WP-07 manual moderation review and safe finalization for generated private artifacts.
-- SOURCE ONLY: requires the durable Generation Job and ENG-P09 usage-metering schema.
-- Do not apply to production or staging during the source-only implementation window.
begin;

create table if not exists public.generation_output_review_events (
  id uuid primary key default gen_random_uuid(),
  generation_job_id uuid not null unique references public.generation_jobs(id) on delete restrict,
  reviewer_user_id uuid not null references auth.users(id) on delete restrict,
  decision text not null check (decision in ('approve','reject')),
  reason text not null check (char_length(reason) between 8 and 500),
  evidence_reference text not null check (char_length(evidence_reference) between 8 and 200),
  created_at timestamptz not null default now()
);
alter table public.generation_output_review_events enable row level security;
revoke all on public.generation_output_review_events from public, anon, authenticated, service_role;
grant select, insert on public.generation_output_review_events to service_role;

create or replace function public.prevent_generation_output_review_event_mutation()
returns trigger language plpgsql set search_path = '' as $$
begin
  raise exception 'GENERATION_OUTPUT_REVIEW_EVENT_APPEND_ONLY' using errcode='42501';
end;
$$;
revoke all on function public.prevent_generation_output_review_event_mutation() from public, anon, authenticated, service_role;
create trigger generation_output_review_events_append_only
before update or delete on public.generation_output_review_events
for each row execute function public.prevent_generation_output_review_event_mutation();

create or replace function public.generation_prepare_manual_review(
  p_job_id uuid, p_reviewer_user_id uuid, p_decision text, p_reason text, p_evidence_reference text
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_job public.generation_jobs;
  v_review public.generation_output_review_events;
  v_lease uuid;
  v_reservation_state text;
  v_metering_ok boolean;
begin
  if p_job_id is null or p_reviewer_user_id is null
    or p_decision not in ('approve','reject')
    or char_length(coalesce(p_reason,'')) not between 8 and 500
    or char_length(coalesce(p_evidence_reference,'')) not between 8 and 200 then
    raise exception 'GENERATION_MANUAL_REVIEW_INPUT_INVALID' using errcode='22023';
  end if;
  select * into v_job from public.generation_jobs where id=p_job_id for update;
  if not found then raise exception 'GENERATION_REVIEW_JOB_NOT_FOUND' using errcode='P0002'; end if;
  select * into v_review from public.generation_output_review_events
    where generation_job_id=p_job_id for update;
  if found and v_review.decision<>p_decision then
    raise exception 'GENERATION_REVIEW_DECISION_ALREADY_RECORDED' using errcode='23505';
  end if;

  if p_decision='reject' then
    if found then
      return jsonb_build_object('job_id',v_job.id,'status',v_job.status,
        'reservation_state',case when v_job.status='failed' then 'released' else 'pending_reconciliation' end,
        'idempotent_replay',true);
    end if;
    if v_job.status<>'pending_reconciliation' or v_job.moderation_status<>'review_required'
      or v_job.artifact_bucket<>'generation-artifacts' or v_job.artifact_path is null then
      raise exception 'GENERATION_REVIEW_STATE_CONFLICT' using errcode='40001';
    end if;
    insert into public.generation_output_review_events(
      generation_job_id,reviewer_user_id,decision,reason,evidence_reference
    ) values (p_job_id,p_reviewer_user_id,'reject',p_reason,p_evidence_reference);
    if v_job.allow_definitive_failure_release then
      perform public.credit_ledger_release(jsonb_build_object(
        'reservation_id',v_job.reservation_id,
        'idempotency_key','generation-moderation-rejected:'||v_job.task_id,
        'policy_version',v_job.policy_version,
        'reason_code','generation_output_moderation_rejected'
      ));
      update public.generation_jobs set status='failed',moderation_status='rejected',
        error_code='generation_output_moderation_rejected',completed_at=now(),
        lease_token=null,lease_expires_at=null,moderated_at=now(),updated_at=now()
        where id=p_job_id returning * into v_job;
      select state into v_reservation_state from public.credit_reservations where id=v_job.reservation_id;
    else
      perform public.credit_ledger_mark_pending(jsonb_build_object(
        'reservation_id',v_job.reservation_id,'reason_code','generation_output_moderation_rejected_release_not_approved'
      ));
      update public.generation_jobs set status='pending_reconciliation',moderation_status='rejected',
        error_code='generation_output_moderation_rejected_release_not_approved',
        lease_token=null,lease_expires_at=null,moderated_at=now(),updated_at=now()
        where id=p_job_id returning * into v_job;
      select state into v_reservation_state from public.credit_reservations where id=v_job.reservation_id;
    end if;
    return jsonb_build_object('job_id',v_job.id,'status',v_job.status,
      'reservation_state',coalesce(v_reservation_state,'unknown'),'idempotent_replay',false);
  end if;

  if v_job.status='succeeded' and found then
    return jsonb_build_object('job_id',v_job.id,'status','succeeded','idempotent_replay',true);
  end if;
  if found and v_job.status='running' and v_job.moderation_status='approved'
    and v_job.lease_token is not null and v_job.lease_expires_at>now() then
    return jsonb_build_object('job_id',v_job.id,'status',v_job.status,'lease_token',v_job.lease_token,
      'input_tokens',v_job.input_tokens,'output_tokens',v_job.output_tokens,
      'actual_cost_microunits',v_job.actual_cost_microunits,'source_event_id',v_job.idempotency_key,
      'idempotent_replay',true);
  end if;
  if not found then
    if v_job.status<>'pending_reconciliation' or v_job.moderation_status<>'review_required'
      or v_job.artifact_bucket<>'generation-artifacts' or v_job.artifact_path is null
      or v_job.output_sha256 is null or v_job.input_tokens is null or v_job.output_tokens is null
      or v_job.actual_cost_microunits is null or v_job.moderation_policy_version is null then
      raise exception 'GENERATION_REVIEW_STATE_CONFLICT' using errcode='40001';
    end if;
    select exists(
      select 1 from public.agent_model_usage_metering m
      where m.idempotency_key=v_job.idempotency_key and m.task_id=v_job.task_id
        and m.trace_id=v_job.trace_id
        and m.owner_id=coalesce(v_job.payer_user_id,v_job.owner_user_id)::text
        and m.agent_id=v_job.agent_id::text and m.source_id=v_job.skill_id::text
        and m.source_version=v_job.source_version and m.sensitivity=v_job.sensitivity
        and m.provider_id=v_job.provider_id and m.model_id=v_job.model_id
        and m.model_version=v_job.model_version
        and m.usage_units=v_job.input_tokens+v_job.output_tokens
        and m.usage_unit=v_job.usage_unit
        and m.cost_microunits=v_job.actual_cost_microunits
        and m.cost_unit=v_job.cost_unit and m.pricing_version=v_job.pricing_version
    ) into v_metering_ok;
    if not v_metering_ok then
      raise exception 'GENERATION_REVIEW_METERING_EVIDENCE_MISSING' using errcode='42501';
    end if;
    if not exists(select 1 from storage.objects o where o.bucket_id='generation-artifacts' and o.name=v_job.artifact_path) then
      raise exception 'GENERATION_REVIEW_ARTIFACT_MISSING' using errcode='P0002';
    end if;
    insert into public.generation_output_review_events(
      generation_job_id,reviewer_user_id,decision,reason,evidence_reference
    ) values (p_job_id,p_reviewer_user_id,'approve',p_reason,p_evidence_reference);
    update public.generation_jobs set moderation_status='approved',moderated_at=now(),
      status='running',lease_token=gen_random_uuid(),lease_expires_at=now()+interval '5 minutes',
      error_code=null,updated_at=now()
      where id=p_job_id returning * into v_job;
  elsif v_review.decision='approve' and v_job.status='pending_reconciliation'
    and v_job.moderation_status='approved' and v_job.artifact_path is not null then
    if not exists(select 1 from storage.objects o where o.bucket_id='generation-artifacts' and o.name=v_job.artifact_path) then
      raise exception 'GENERATION_REVIEW_ARTIFACT_MISSING' using errcode='P0002';
    end if;
    v_lease := gen_random_uuid();
    update public.generation_jobs set status='running',lease_token=v_lease,
      lease_expires_at=now()+interval '5 minutes',error_code=null,updated_at=now()
      where id=p_job_id returning * into v_job;
  else
    raise exception 'GENERATION_REVIEW_STATE_CONFLICT' using errcode='40001';
  end if;
  return jsonb_build_object('job_id',v_job.id,'status',v_job.status,'lease_token',v_job.lease_token,
    'input_tokens',v_job.input_tokens,'output_tokens',v_job.output_tokens,
    'actual_cost_microunits',v_job.actual_cost_microunits,'source_event_id',v_job.idempotency_key,
    'idempotent_replay',false);
end;
$$;

revoke all on function public.generation_prepare_manual_review(uuid,uuid,text,text,text) from public, anon, authenticated, service_role;
grant execute on function public.generation_prepare_manual_review(uuid,uuid,text,text,text) to service_role;

comment on table public.generation_output_review_events is
  'Append-only, operator-attributed manual review decision for a private AI Generation artifact. Review does not publish the artifact publicly.';

commit;