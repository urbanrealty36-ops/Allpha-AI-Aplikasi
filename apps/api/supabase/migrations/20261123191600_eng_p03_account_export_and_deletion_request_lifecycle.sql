-- ENG-P03: durable personal-data export and account-deletion request lifecycle.
-- Destructive account deletion is intentionally not executable until approved
-- per-data-class retention policy and legal-hold controls are populated.

create table if not exists public.account_export_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 128),
  status text not null default 'queued'
    check (status in ('queued','running','succeeded','failed','cancelled','expired')),
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 5 check (max_attempts between 1 and 10),
  next_attempt_at timestamptz not null default now(),
  lease_token uuid,
  lease_owner text,
  lease_expires_at timestamptz,
  storage_bucket text not null default 'account-exports',
  storage_path text,
  file_sha256 text check (file_sha256 is null or file_sha256 ~ '^[a-f0-9]{64}$'),
  file_size_bytes bigint check (file_size_bytes is null or file_size_bytes > 0),
  manifest jsonb not null default '{}'::jsonb check (jsonb_typeof(manifest) = 'object'),
  error_code text,
  requested_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  failed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, idempotency_key)
);
create index if not exists account_export_jobs_claim_idx
  on public.account_export_jobs(status, next_attempt_at, requested_at)
  where status in ('queued','running');
create index if not exists account_export_jobs_user_idx
  on public.account_export_jobs(user_id, requested_at desc);

create table if not exists public.account_deletion_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  subject_ref text not null,
  status text not null default 'awaiting_policy'
    check (status in ('awaiting_policy','scheduled','processing','blocked_legal_hold','completed','cancelled','failed')),
  policy_version text,
  requested_at timestamptz not null default now(),
  scheduled_for timestamptz,
  completed_at timestamptz,
  cancelled_at timestamptz,
  error_code text,
  request_metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(request_metadata) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists account_deletion_one_open_request_per_user
  on public.account_deletion_requests(user_id)
  where user_id is not null and status in ('awaiting_policy','scheduled','processing','blocked_legal_hold');
create index if not exists account_deletion_requests_subject_idx
  on public.account_deletion_requests(subject_ref, requested_at desc);

create table if not exists public.account_lifecycle_events (
  id uuid primary key default gen_random_uuid(),
  request_id uuid references public.account_deletion_requests(id) on delete set null,
  export_job_id uuid references public.account_export_jobs(id) on delete set null,
  user_id uuid references auth.users(id) on delete set null,
  subject_ref text not null,
  event_type text not null check (event_type in (
    'export_requested','export_started','export_completed','export_failed',
    'deletion_requested','deletion_cancelled','deletion_scheduled','deletion_started',
    'deletion_blocked','deletion_completed','deletion_failed'
  )),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  recorded_at timestamptz not null default now()
);
create index if not exists account_lifecycle_events_subject_idx
  on public.account_lifecycle_events(subject_ref, recorded_at desc);

-- Retention periods are intentionally not seeded. No legal retention duration
-- is inferred by engineering. Deletion scheduling requires approved rows for
-- every data class and an independently recorded legal-hold review.
create table if not exists public.account_data_retention_policies (
  id uuid primary key default gen_random_uuid(),
  data_class text not null,
  retention_days integer not null check (retention_days >= 0),
  policy_version text not null check (char_length(policy_version) between 1 and 40),
  legal_basis text not null check (char_length(legal_basis) between 1 and 500),
  approved_by uuid not null,
  approved_at timestamptz not null,
  active boolean not null default false,
  updated_at timestamptz not null default now(),
  unique (data_class, policy_version)
);
create unique index if not exists account_retention_one_active_policy_per_class
  on public.account_data_retention_policies(data_class) where active;

create table if not exists public.account_legal_holds (
  id uuid primary key default gen_random_uuid(),
  subject_ref text not null,
  reference_code text not null,
  reason_code text not null,
  active boolean not null default true,
  created_by uuid not null,
  created_at timestamptz not null default now(),
  released_by uuid,
  released_at timestamptz
);
create index if not exists account_legal_holds_subject_active_idx
  on public.account_legal_holds(subject_ref) where active;

create schema if not exists private;
create table if not exists private.account_export_sources (
  source_key text primary key,
  table_name text not null,
  filter_kind text not null default 'owner_columns'
    check (filter_kind in ('owner_columns','owned_agents','owned_runtime_tasks','participant_conversations','conversation_messages','owned_content','content_activity','member_workspaces','member_communities')),
  owner_columns text[] not null default '{}',
  sort_order integer not null default 100,
  enabled boolean not null default true
);
revoke all on private.account_export_sources from public, anon, authenticated, service_role;

insert into private.account_export_sources(source_key,table_name,filter_kind,owner_columns,sort_order) values
  ('profile','profiles','owner_columns',array['id'],10),
  ('settings','user_settings','owner_columns',array['user_id'],20),
  ('consents','user_consents','owner_columns',array['user_id'],30),
  ('social_edges','social_edges','owner_columns',array['actor_user_id','target_user_id'],40),
  ('social_graph_events','social_graph_events','owner_columns',array['actor_user_id','target_user_id'],41),
  ('interests','user_interests','owner_columns',array['user_id'],42),
  ('feed_preferences','feed_preferences','owner_columns',array['user_id'],43),
  ('feed_impressions','feed_impressions','owner_columns',array['viewer_user_id'],44),
  ('feed_feedback','feed_feedback','owner_columns',array['viewer_user_id'],45),
  ('feed_snapshots','feed_snapshots','owner_columns',array['viewer_user_id'],46),
  ('feed_snapshot_items','feed_snapshot_items','owner_columns',array['owner_id'],47),
  ('agents_created','ai_agents','owner_columns',array['created_by'],50),
  ('agent_ownerships','agent_ownerships','owner_columns',array['owner_user_id'],51),
  ('agent_skills_created','agent_skills','owner_columns',array['created_by'],52),
  ('agent_skills_owned','agent_skills','owned_agents','{}',53),
  ('agent_skill_versions_created','agent_skill_versions','owner_columns',array['created_by'],54),
  ('agent_capabilities','agent_capabilities','owner_columns',array['created_by'],55),
  ('agent_knowledge_sources','agent_knowledge_sources','owner_columns',array['owner_id'],56),
  ('agent_knowledge_jobs','agent_knowledge_jobs','owner_columns',array['owner_id'],57),
  ('agent_knowledge_chunks','agent_knowledge_chunks','owner_columns',array['owner_id'],58),
  ('agent_model_usage','agent_model_usage_metering','owner_columns',array['owner_id'],59),
  ('agent_runtime_policies','agent_runtime_policies','owner_columns',array['created_by'],60),
  ('agent_runtime_sessions','agent_runtime_sessions','owner_columns',array['owner_user_id'],61),
  ('agent_runtime_tasks','agent_runtime_tasks','owner_columns',array['owner_user_id'],62),
  ('agent_runtime_checkpoints','agent_runtime_checkpoints','owned_runtime_tasks','{}',63),
  ('agent_runtime_effect_receipts','agent_runtime_effect_receipts','owned_runtime_tasks','{}',64),
  ('agent_skill_challenge_runs','agent_skill_challenge_runs','owner_columns',array['owner_user_id'],65),
  ('agent_skill_challenge_evidence','agent_skill_challenge_achievement_evidence','owner_columns',array['owner_user_id'],66),
  ('agent_skill_challenge_windows','agent_skill_challenge_issue_windows','owner_columns',array['owner_user_id'],67),
  ('agent_consumer_grants','agent_consumer_grants','owner_columns',array['owner_user_id','requester_user_id'],68),
  ('agent_consumer_grant_events','agent_consumer_grant_events','owner_columns',array['owner_user_id','requester_user_id','actor_user_id'],69),
  ('agent_resource_grant_audit','agent_resource_grant_audit','owner_columns',array['actor_user_id'],70),
  ('agent_social_approvals','agent_social_action_approvals','owner_columns',array['owner_user_id'],71),
  ('agent_social_audit','agent_social_audit_events','owner_columns',array['owner_user_id','actor_user_id'],72),
  ('agent_social_presence','agent_social_presence_policies','owner_columns',array['owner_user_id'],73),
  ('workflows','workflow_definitions','owner_columns',array['owner_user_id'],80),
  ('workflow_runs','workflow_runs','owner_columns',array['owner_user_id'],81),
  ('workflow_steps','workflow_steps','owner_columns',array['owner_user_id'],82),
  ('workflow_events','workflow_run_events','owner_columns',array['owner_user_id'],83),
  ('content_items','content_items','owner_columns',array['owner_id'],90),
  ('content_media','content_media','owner_columns',array['owner_id'],91),
  ('content_versions','content_item_versions','owner_columns',array['owner_id'],92),
  ('content_comments_authored','content_comments','owner_columns',array['actor_user_id'],93),
  ('content_comments_on_owned','content_comments','owned_content','{}',94),
  ('content_reactions_authored','content_reactions','owner_columns',array['actor_user_id'],95),
  ('content_reactions_on_owned','content_reactions','content_activity','{}',96),
  ('content_saves','content_saves','owner_columns',array['actor_user_id'],97),
  ('content_shares','content_shares','owner_columns',array['actor_user_id'],98),
  ('content_mentions','content_mentions','owner_columns',array['mentioner_user_id','mentioned_user_id'],99),
  ('content_reports','content_reports','owner_columns',array['reporter_user_id'],100),
  ('content_appeals','content_appeals','owner_columns',array['owner_id'],101),
  ('content_schedules','content_schedules','owner_columns',array['owner_id'],102),
  ('content_lifecycle_jobs','content_lifecycle_jobs','owner_columns',array['owner_id'],103),
  ('content_lifecycle_events','content_lifecycle_events','owner_columns',array['owner_id'],104),
  ('content_retention_holds','content_retention_holds','owner_columns',array['owner_id','created_by'],105),
  ('content_retention_receipts','content_retention_receipts','owner_columns',array['owner_id'],106),
  ('conversations','conversations','owner_columns',array['created_by'],110),
  ('conversation_participants','conversation_participants','owner_columns',array['user_id'],111),
  ('messages_sent','messages','owner_columns',array['sender_user_id'],112),
  ('messages_in_conversations','messages','conversation_messages','{}',113),
  ('communities_created','communities','owner_columns',array['created_by'],120),
  ('community_memberships','community_memberships','owner_columns',array['user_id'],121),
  ('community_mission_progress','community_mission_progress','owner_columns',array['user_id'],122),
  ('community_mission_progress_events','community_mission_progress_events','owner_columns',array['user_id'],123),
  ('community_posts_authored','community_posts','owner_columns',array['author_id'],124),
  ('community_posts_in_memberships','community_posts','member_communities','{}',125),
  ('community_invites_created','community_invites','owner_columns',array['created_by'],126),
  ('community_reports','community_reports','owner_columns',array['reporter_id'],127),
  ('workspaces_created','workspaces','owner_columns',array['created_by'],130),
  ('workspace_memberships','workspace_memberships','owner_columns',array['user_id'],131),
  ('workspace_documents_created','workspace_documents','owner_columns',array['created_by'],132),
  ('workspace_documents_in_memberships','workspace_documents','member_workspaces','{}',133),
  ('workspace_document_versions','workspace_document_versions','owner_columns',array['created_by'],134),
  ('workspace_annotations_authored','workspace_annotations','owner_columns',array['author_id'],135),
  ('workspace_annotations_in_memberships','workspace_annotations','member_workspaces','{}',136),
  ('workspace_presence','workspace_presence','owner_columns',array['user_id'],137),
  ('notifications','notifications','owner_columns',array['user_id'],140),
  ('notification_devices','notification_devices','owner_columns',array['user_id'],141),
  ('notification_push_deliveries','notification_push_deliveries','owner_columns',array['user_id'],142),
  ('billing_orders','billing_orders','owner_columns',array['owner_user_id'],150),
  ('billing_receipts','billing_receipts','owner_columns',array['owner_user_id'],151),
  ('billing_subscriptions','billing_subscriptions','owner_columns',array['owner_user_id'],152),
  ('playback_entitlements','playback_entitlements','owner_columns',array['owner_user_id'],153),
  ('credit_accounts','credit_ledger_accounts','owner_columns',array['owner_user_id'],154),
  ('credit_entries','credit_ledger_entries','owner_columns',array['owner_user_id'],155),
  ('credit_balance','credit_balance_projection','owner_columns',array['owner_user_id'],156),
  ('credit_reservations','credit_reservations','owner_columns',array['owner_user_id'],157),
  ('credit_reconciliation','credit_reconciliation_events','owner_columns',array['owner_user_id','actor_id'],158),
  ('generation_jobs','generation_jobs','owner_columns',array['owner_user_id','agent_owner_user_id','payer_user_id'],160),
  ('generation_artifacts','generation_artifacts','owner_columns',array['owner_user_id'],161),
  ('generation_artifact_deletions','generation_artifact_deletion_jobs','owner_columns',array['owner_user_id'],162),
  ('generation_cancellations','generation_job_cancellation_events','owner_columns',array['owner_user_id'],163),
  ('cinema_titles','cinema_titles','owner_columns',array['owner_id'],170),
  ('cinema_episodes','cinema_episodes','owner_columns',array['owner_id'],171),
  ('cinema_generation_links','cinema_generation_job_links','owner_columns',array['owner_user_id','owner_id','requester_user_id'],172),
  ('organization_memberships','organization_memberships','owner_columns',array['user_id'],180),
  ('organizations_owned','organizations','owner_columns',array['owner_id'],181),
  ('audit_events','audit_events','owner_columns',array['actor_user_id'],190),
  ('operator_grants','platform_operator_grants','owner_columns',array['user_id'],191),
  ('operator_audit_events','platform_operator_audit_events','owner_columns',array['actor_user_id'],192),
  ('spatial_themes_created','spatial_themes','owner_columns',array['created_by'],200),
  ('spatial_theme_versions','spatial_theme_versions','owner_columns',array['created_by'],201),
  ('spatial_agent_asset_mappings','spatial_agent_asset_mappings','owner_columns',array['created_by'],202)
on conflict (source_key) do nothing;

create or replace function private.build_account_export_snapshot(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_source record;
  v_predicate text;
  v_rows jsonb;
  v_data jsonb := '{}'::jsonb;
  v_manifest jsonb := '[]'::jsonb;
  v_account jsonb;
  v_redacted text[] := array[
    'password','password_hash','encrypted_secret','secret','api_key','access_token',
    'refresh_token','token','authorization','private_key','signing_secret',
    'credential','credentials','credential_ciphertext','provider_request',
    'provider_response','request_headers','response_headers','embedding'
  ];
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_user_id is null then
    raise exception 'account_export_user_required' using errcode = '22023';
  end if;

  select jsonb_build_object(
    'id', u.id,
    'email', u.email,
    'phone', u.phone,
    'created_at', u.created_at,
    'updated_at', u.updated_at,
    'last_sign_in_at', u.last_sign_in_at,
    'email_confirmed_at', u.email_confirmed_at,
    'phone_confirmed_at', u.phone_confirmed_at
  )
  into v_account
  from auth.users u
  where u.id = p_user_id;
  if v_account is null then
    raise exception 'account_export_user_not_found' using errcode = 'P0002';
  end if;

  for v_source in
    select source_key, table_name, filter_kind, owner_columns
    from private.account_export_sources
    where enabled
    order by sort_order, source_key
  loop
    if pg_catalog.to_regclass(pg_catalog.format('public.%I', v_source.table_name)) is null then
      continue;
    end if;

    if v_source.filter_kind = 'owner_columns' then
      select pg_catalog.string_agg(
        pg_catalog.format('t.%I::text = $2::text', column_name), ' OR '
      )
      into v_predicate
      from pg_catalog.unnest(v_source.owner_columns) as owner_column(column_name);
      if v_predicate is null then
        continue;
      end if;
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where %s',
        v_source.table_name, v_predicate
      ) into v_rows using v_redacted, p_user_id;
    elsif v_source.filter_kind = 'owned_agents' then
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where t.agent_id::text in (select ao.agent_id::text from public.agent_ownerships ao where ao.owner_user_id = $2)',
        v_source.table_name
      ) into v_rows using v_redacted, p_user_id;
    elsif v_source.filter_kind = 'owned_runtime_tasks' then
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where t.task_id::text in (select task.id::text from public.agent_runtime_tasks task where task.owner_user_id = $2)',
        v_source.table_name
      ) into v_rows using v_redacted, p_user_id;
    elsif v_source.filter_kind = 'participant_conversations' then
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where t.conversation_id::text in (select cp.conversation_id::text from public.conversation_participants cp where cp.user_id = $2)',
        v_source.table_name
      ) into v_rows using v_redacted, p_user_id;
    elsif v_source.filter_kind = 'conversation_messages' then
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where t.sender_user_id::text = $2::text or t.conversation_id::text in (select cp.conversation_id::text from public.conversation_participants cp where cp.user_id = $2)',
        v_source.table_name
      ) into v_rows using v_redacted, p_user_id;
    elsif v_source.filter_kind = 'owned_content' then
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where t.content_id::text in (select ci.id::text from public.content_items ci where ci.owner_id::text = $2::text)',
        v_source.table_name
      ) into v_rows using v_redacted, p_user_id;
    elsif v_source.filter_kind = 'content_activity' then
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where t.actor_user_id::text = $2::text or t.content_id::text in (select ci.id::text from public.content_items ci where ci.owner_id::text = $2::text)',
        v_source.table_name
      ) into v_rows using v_redacted, p_user_id;
    elsif v_source.filter_kind = 'member_workspaces' then
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where t.workspace_id::text in (select wm.workspace_id::text from public.workspace_memberships wm where wm.user_id = $2)',
        v_source.table_name
      ) into v_rows using v_redacted, p_user_id;
    elsif v_source.filter_kind = 'member_communities' then
      execute pg_catalog.format(
        'select coalesce(jsonb_agg(to_jsonb(t) - $1), ''[]''::jsonb) from public.%I t where t.community_id::text in (select cm.community_id::text from public.community_memberships cm where cm.user_id = $2)',
        v_source.table_name
      ) into v_rows using v_redacted, p_user_id;
    else
      continue;
    end if;

    v_rows := coalesce(v_rows, '[]'::jsonb);
    v_data := v_data || jsonb_build_object(v_source.source_key, v_rows);
    v_manifest := v_manifest || jsonb_build_array(jsonb_build_object(
      'source', v_source.source_key,
      'table', v_source.table_name,
      'row_count', jsonb_array_length(v_rows)
    ));
  end loop;

  return jsonb_build_object(
    'schema_version', '1.0',
    'generated_at', pg_catalog.clock_timestamp(),
    'account', v_account,
    'data', v_data,
    'manifest', v_manifest,
    'source_count', jsonb_array_length(v_manifest)
  );
end;
$$;

revoke all on function private.build_account_export_snapshot(uuid) from public, anon, authenticated;
grant execute on function private.build_account_export_snapshot(uuid) to service_role;

create or replace function public.request_my_account_export(p_idempotency_key text)
returns table (id uuid, status text, requested_at timestamptz, created_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '28000';
  end if;
  if p_idempotency_key is null
     or char_length(p_idempotency_key) < 8
     or char_length(p_idempotency_key) > 128
     or p_idempotency_key !~ '^[A-Za-z0-9._:-]+$' then
    raise exception 'invalid_idempotency_key' using errcode = '22023';
  end if;
  if not exists (select 1 from public.profiles p where p.id = v_user_id and p.account_status = 'active') then
    raise exception 'account_not_active' using errcode = '42501';
  end if;

  insert into public.account_export_jobs(user_id,idempotency_key)
  values (v_user_id,p_idempotency_key)
  on conflict (user_id,idempotency_key) do nothing;

  return query
  select j.id,j.status,j.requested_at,j.created_at
  from public.account_export_jobs j
  where j.user_id = v_user_id and j.idempotency_key = p_idempotency_key
  limit 1;
end;
$$;

create or replace function public.claim_account_export_jobs(
  p_worker_id text,
  p_limit integer default 2,
  p_lease_seconds integer default 300
)
returns table (id uuid,user_id uuid,lease_token uuid,attempts integer)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_worker_id is null or char_length(p_worker_id) not between 1 and 120
     or p_limit not between 1 and 10 or p_lease_seconds not between 30 and 900 then
    raise exception 'invalid_export_claim_bounds' using errcode = '22023';
  end if;

  update public.account_export_jobs j
  set status = 'failed', failed_at = pg_catalog.now(),
      error_code = 'EXPORT_LEASE_EXHAUSTED', lease_token = null,
      lease_owner = null, lease_expires_at = null, updated_at = pg_catalog.now()
  where j.status = 'running' and j.lease_expires_at <= pg_catalog.now()
    and j.attempts >= j.max_attempts;

  return query
  with candidates as (
    select j.id
    from public.account_export_jobs j
    where (
      (j.status = 'queued' and j.next_attempt_at <= pg_catalog.now())
      or (j.status = 'running' and j.lease_expires_at <= pg_catalog.now())
    ) and j.attempts < j.max_attempts
    order by j.requested_at, j.id
    for update skip locked
    limit p_limit
  )
  update public.account_export_jobs j
  set status = 'running',
      attempts = j.attempts + 1,
      lease_token = gen_random_uuid(),
      lease_owner = p_worker_id,
      lease_expires_at = pg_catalog.now() + pg_catalog.make_interval(secs => p_lease_seconds),
      started_at = coalesce(j.started_at, pg_catalog.now()),
      updated_at = pg_catalog.now()
  from candidates c
  where j.id = c.id
  returning j.id,j.user_id,j.lease_token,j.attempts;
end;
$$;

create or replace function public.renew_account_export_job_lease(
  p_job_id uuid,p_lease_token uuid,p_lease_seconds integer default 300
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_lease_seconds not between 30 and 900 then
    raise exception 'invalid_export_lease_duration' using errcode = '22023';
  end if;
  update public.account_export_jobs j
  set lease_expires_at = pg_catalog.now() + pg_catalog.make_interval(secs => p_lease_seconds),
      updated_at = pg_catalog.now()
  where j.id = p_job_id and j.status = 'running'
    and j.lease_token = p_lease_token and j.lease_expires_at > pg_catalog.now();
  return found;
end;
$$;

create or replace function public.build_my_account_export_snapshot(p_job_id uuid,p_lease_token uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare v_user_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  select j.user_id into v_user_id
  from public.account_export_jobs j
  where j.id = p_job_id
    and j.status = 'running'
    and j.lease_token = p_lease_token
    and j.lease_expires_at > pg_catalog.now();
  if v_user_id is null then
    raise exception 'export_lease_lost' using errcode = '40001';
  end if;
  return private.build_account_export_snapshot(v_user_id);
end;
$$;

create or replace function public.complete_account_export_job(
  p_job_id uuid,p_lease_token uuid,p_storage_path text,p_file_sha256 text,
  p_file_size_bytes bigint,p_manifest jsonb
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_user_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_storage_path is null or p_file_sha256 is null or p_file_sha256 !~ '^[a-f0-9]{64}
    raise exception 'invalid_export_receipt' using errcode = '22023';
  end if;
  update public.account_export_jobs j
  set status = 'succeeded',
      storage_bucket = 'account-exports',
      storage_path = p_storage_path,
      file_sha256 = p_file_sha256,
      file_size_bytes = p_file_size_bytes,
      manifest = p_manifest,
      completed_at = pg_catalog.now(),
      lease_token = null,
      lease_owner = null,
      lease_expires_at = null,
      error_code = null,
      updated_at = pg_catalog.now()
  where j.id = p_job_id
    and j.status = 'running'
    and j.lease_token = p_lease_token
    and j.lease_expires_at > pg_catalog.now()
    and p_storage_path = j.user_id::text || '/' || j.id::text || '.json.gz';
  if not found then return false; end if;
  select j.user_id into v_user_id from public.account_export_jobs j where j.id = p_job_id;
  insert into public.account_lifecycle_events(export_job_id,user_id,subject_ref,event_type,metadata)
  values (p_job_id,v_user_id,encode(digest(v_user_id::text,'sha256'),'hex'),'export_completed',
          jsonb_build_object('file_size_bytes',p_file_size_bytes,'file_sha256',p_file_sha256));
  return true;
end;
$$;

create or replace function public.fail_account_export_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text,p_retry_seconds integer default 30
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_job public.account_export_jobs%rowtype;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_retry_seconds not between 5 and 3600 then
    raise exception 'invalid_export_retry_delay' using errcode = '22023';
  end if;
  update public.account_export_jobs j
  set status = case when j.attempts >= j.max_attempts then 'failed' else 'queued' end,
      next_attempt_at = pg_catalog.now() + pg_catalog.make_interval(secs => p_retry_seconds),
      failed_at = case when j.attempts >= j.max_attempts then pg_catalog.now() else null end,
      error_code = left(coalesce(p_error_code,'EXPORT_FAILED'),80),
      lease_token = null,
      lease_owner = null,
      lease_expires_at = null,
      updated_at = pg_catalog.now()
  where j.id = p_job_id and j.status = 'running' and j.lease_token = p_lease_token
  returning j.* into v_job;
  if not found then return false; end if;
  insert into public.account_lifecycle_events(export_job_id,user_id,subject_ref,event_type,metadata)
  values (v_job.id,v_job.user_id,encode(digest(v_job.user_id::text,'sha256'),'hex'),'export_failed',
          jsonb_build_object('error_code',v_job.error_code,'attempts',v_job.attempts,'status',v_job.status));
  return true;
end;
$$;

create or replace function public.create_account_deletion_request_for_actor(p_actor_user_id uuid)
returns table (id uuid,status text,requested_at timestamptz,subject_ref text)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_subject_ref text;
  v_request_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_actor_user_id is null or not exists (
    select 1 from auth.users u where u.id = p_actor_user_id
  ) then
    raise exception 'account_not_found' using errcode = 'P0002';
  end if;
  if not exists (
    select 1 from public.profiles p where p.id = p_actor_user_id and p.account_status = 'active'
  ) then
    raise exception 'account_not_active' using errcode = '42501';
  end if;
  v_subject_ref := encode(digest(p_actor_user_id::text,'sha256'),'hex');
  if exists (
    select 1 from public.account_deletion_requests r
    where r.user_id = p_actor_user_id
      and r.status in ('awaiting_policy','scheduled','processing','blocked_legal_hold')
  ) then
    raise exception 'account_deletion_request_already_open' using errcode = '23505';
  end if;

  insert into public.account_deletion_requests(user_id,subject_ref,status)
  values (p_actor_user_id,v_subject_ref,'awaiting_policy')
  returning account_deletion_requests.id into v_request_id;

  update public.profiles p
  set account_status = 'deactivation_requested'
  where p.id = p_actor_user_id and p.account_status = 'active';
  if not found then
    raise exception 'account_deletion_request_not_created' using errcode = '40001';
  end if;

  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values (v_request_id,p_actor_user_id,v_subject_ref,'deletion_requested',
          jsonb_build_object('execution_state','awaiting_policy','retention_policy_configured',false));

  return query
  select r.id,r.status,r.requested_at,r.subject_ref
  from public.account_deletion_requests r
  where r.id = v_request_id;
end;
$$;
create or replace function public.cancel_my_account_deletion(p_request_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_request public.account_deletion_requests%rowtype;
begin
  if (select auth.uid()) is null then
    raise exception 'authentication_required' using errcode = '28000';
  end if;
  update public.account_deletion_requests r
  set status = 'cancelled', cancelled_at = pg_catalog.now(), updated_at = pg_catalog.now()
  where r.id = p_request_id
    and r.user_id = (select auth.uid())
    and r.status = 'awaiting_policy'
  returning r.* into v_request;
  if not found then return false; end if;

  update public.profiles p
  set account_status = 'active'
  where p.id = (select auth.uid())
    and not exists (
      select 1 from public.account_deletion_requests r
      where r.user_id = (select auth.uid())
        and r.status in ('awaiting_policy','scheduled','processing','blocked_legal_hold')
    );
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values (v_request.id,(select auth.uid()),v_request.subject_ref,'deletion_cancelled','{}'::jsonb);
  return true;
end;
$$;

create or replace function public.set_account_lifecycle_updated_at()
returns trigger language plpgsql set search_path = ''
as $$ begin new.updated_at := pg_catalog.now(); return new; end; $$;

drop trigger if exists account_export_jobs_set_updated_at on public.account_export_jobs;
create trigger account_export_jobs_set_updated_at before update on public.account_export_jobs
for each row execute function public.set_account_lifecycle_updated_at();
drop trigger if exists account_deletion_requests_set_updated_at on public.account_deletion_requests;
create trigger account_deletion_requests_set_updated_at before update on public.account_deletion_requests
for each row execute function public.set_account_lifecycle_updated_at();

alter table public.account_export_jobs enable row level security;
alter table public.account_deletion_requests enable row level security;
alter table public.account_lifecycle_events enable row level security;
alter table public.account_data_retention_policies enable row level security;
alter table public.account_legal_holds enable row level security;

drop policy if exists account_export_jobs_select_self on public.account_export_jobs;
create policy account_export_jobs_select_self on public.account_export_jobs
for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists account_deletion_requests_select_self on public.account_deletion_requests;
create policy account_deletion_requests_select_self on public.account_deletion_requests
for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists account_lifecycle_events_select_self on public.account_lifecycle_events;
create policy account_lifecycle_events_select_self on public.account_lifecycle_events
for select to authenticated using (user_id = (select auth.uid()));

revoke all on public.account_export_jobs, public.account_deletion_requests,
  public.account_lifecycle_events, public.account_data_retention_policies,
  public.account_legal_holds from anon, authenticated;
grant select on public.account_export_jobs, public.account_deletion_requests,
  public.account_lifecycle_events to authenticated;
grant select, insert, update, delete on public.account_export_jobs,
  public.account_deletion_requests, public.account_lifecycle_events,
  public.account_data_retention_policies, public.account_legal_holds to service_role;

revoke all on function public.request_my_account_export(text) from public, anon;
grant execute on function public.request_my_account_export(text) to authenticated;
revoke all on function public.claim_account_export_jobs(text,integer,integer) from public, anon, authenticated;
grant execute on function public.claim_account_export_jobs(text,integer,integer) to service_role;
revoke all on function public.renew_account_export_job_lease(uuid,uuid,integer) from public, anon, authenticated;\ngrant execute on function public.renew_account_export_job_lease(uuid,uuid,integer) to service_role;\nrevoke all on function public.build_my_account_export_snapshot(uuid,uuid) from public, anon, authenticated;
grant execute on function public.build_my_account_export_snapshot(uuid,uuid) to service_role;
revoke all on function public.complete_account_export_job(uuid,uuid,text,text,bigint,jsonb) from public, anon, authenticated;
grant execute on function public.complete_account_export_job(uuid,uuid,text,text,bigint,jsonb) to service_role;
revoke all on function public.fail_account_export_job(uuid,uuid,text,integer) from public, anon, authenticated;
grant execute on function public.fail_account_export_job(uuid,uuid,text,integer) to service_role;
revoke all on function public.create_account_deletion_request_for_actor(uuid) from public, anon, authenticated;
grant execute on function public.create_account_deletion_request_for_actor(uuid) to service_role;
revoke all on function public.cancel_my_account_deletion(uuid) from public, anon;
grant execute on function public.cancel_my_account_deletion(uuid) to authenticated;

insert into storage.buckets(id,name,public)
values ('account-exports','account-exports',false)
on conflict (id) do nothing;

do $$
begin
  if exists (
    select 1 from storage.buckets b
    where b.id = 'account-exports' and b.public is distinct from false
  ) then
    raise exception 'account_exports_bucket_must_remain_private';
  end if;
end;
$$;

     or p_file_size_bytes is null or p_file_size_bytes <= 0
     or p_manifest is null or jsonb_typeof(p_manifest) <> 'object' then
    raise exception 'invalid_export_receipt' using errcode = '22023';
  end if;
  update public.account_export_jobs j
  set status = 'succeeded',
      storage_bucket = 'account-exports',
      storage_path = p_storage_path,
      file_sha256 = p_file_sha256,
      file_size_bytes = p_file_size_bytes,
      manifest = p_manifest,
      completed_at = pg_catalog.now(),
      lease_token = null,
      lease_owner = null,
      lease_expires_at = null,
      error_code = null,
      updated_at = pg_catalog.now()
  where j.id = p_job_id
    and j.status = 'running'
    and j.lease_token = p_lease_token
    and j.lease_expires_at > pg_catalog.now()
    and p_storage_path = j.user_id::text || '/' || j.id::text || '.json.gz';
  if not found then return false; end if;
  select j.user_id into v_user_id from public.account_export_jobs j where j.id = p_job_id;
  insert into public.account_lifecycle_events(export_job_id,user_id,subject_ref,event_type,metadata)
  values (p_job_id,v_user_id,encode(digest(v_user_id::text,'sha256'),'hex'),'export_completed',
          jsonb_build_object('file_size_bytes',p_file_size_bytes,'file_sha256',p_file_sha256));
  return true;
end;
$$;

create or replace function public.fail_account_export_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text,p_retry_seconds integer default 30
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_job public.account_export_jobs%rowtype;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_retry_seconds not between 5 and 3600 then
    raise exception 'invalid_export_retry_delay' using errcode = '22023';
  end if;
  update public.account_export_jobs j
  set status = case when j.attempts >= j.max_attempts then 'failed' else 'queued' end,
      next_attempt_at = pg_catalog.now() + pg_catalog.make_interval(secs => p_retry_seconds),
      failed_at = case when j.attempts >= j.max_attempts then pg_catalog.now() else null end,
      error_code = left(coalesce(p_error_code,'EXPORT_FAILED'),80),
      lease_token = null,
      lease_owner = null,
      lease_expires_at = null,
      updated_at = pg_catalog.now()
  where j.id = p_job_id and j.status = 'running' and j.lease_token = p_lease_token
  returning j.* into v_job;
  if not found then return false; end if;
  insert into public.account_lifecycle_events(export_job_id,user_id,subject_ref,event_type,metadata)
  values (v_job.id,v_job.user_id,encode(digest(v_job.user_id::text,'sha256'),'hex'),'export_failed',
          jsonb_build_object('error_code',v_job.error_code,'attempts',v_job.attempts,'status',v_job.status));
  return true;
end;
$$;

create or replace function public.create_account_deletion_request_for_actor(p_actor_user_id uuid)
returns table (id uuid,status text,requested_at timestamptz,subject_ref text)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_subject_ref text;
  v_request_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_actor_user_id is null or not exists (
    select 1 from auth.users u where u.id = p_actor_user_id
  ) then
    raise exception 'account_not_found' using errcode = 'P0002';
  end if;
  if not exists (
    select 1 from public.profiles p where p.id = p_actor_user_id and p.account_status = 'active'
  ) then
    raise exception 'account_not_active' using errcode = '42501';
  end if;
  v_subject_ref := encode(digest(p_actor_user_id::text,'sha256'),'hex');
  if exists (
    select 1 from public.account_deletion_requests r
    where r.user_id = p_actor_user_id
      and r.status in ('awaiting_policy','scheduled','processing','blocked_legal_hold')
  ) then
    raise exception 'account_deletion_request_already_open' using errcode = '23505';
  end if;

  insert into public.account_deletion_requests(user_id,subject_ref,status)
  values (p_actor_user_id,v_subject_ref,'awaiting_policy')
  returning account_deletion_requests.id into v_request_id;

  update public.profiles p
  set account_status = 'deactivation_requested'
  where p.id = p_actor_user_id and p.account_status = 'active';
  if not found then
    raise exception 'account_deletion_request_not_created' using errcode = '40001';
  end if;

  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values (v_request_id,p_actor_user_id,v_subject_ref,'deletion_requested',
          jsonb_build_object('execution_state','awaiting_policy','retention_policy_configured',false));

  return query
  select r.id,r.status,r.requested_at,r.subject_ref
  from public.account_deletion_requests r
  where r.id = v_request_id;
end;
$$;
create or replace function public.cancel_my_account_deletion(p_request_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_request public.account_deletion_requests%rowtype;
begin
  if (select auth.uid()) is null then
    raise exception 'authentication_required' using errcode = '28000';
  end if;
  update public.account_deletion_requests r
  set status = 'cancelled', cancelled_at = pg_catalog.now(), updated_at = pg_catalog.now()
  where r.id = p_request_id
    and r.user_id = (select auth.uid())
    and r.status = 'awaiting_policy'
  returning r.* into v_request;
  if not found then return false; end if;

  update public.profiles p
  set account_status = 'active'
  where p.id = (select auth.uid())
    and not exists (
      select 1 from public.account_deletion_requests r
      where r.user_id = (select auth.uid())
        and r.status in ('awaiting_policy','scheduled','processing','blocked_legal_hold')
    );
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values (v_request.id,(select auth.uid()),v_request.subject_ref,'deletion_cancelled','{}'::jsonb);
  return true;
end;
$$;

create or replace function public.set_account_lifecycle_updated_at()
returns trigger language plpgsql set search_path = ''
as $$ begin new.updated_at := pg_catalog.now(); return new; end; $$;

drop trigger if exists account_export_jobs_set_updated_at on public.account_export_jobs;
create trigger account_export_jobs_set_updated_at before update on public.account_export_jobs
for each row execute function public.set_account_lifecycle_updated_at();
drop trigger if exists account_deletion_requests_set_updated_at on public.account_deletion_requests;
create trigger account_deletion_requests_set_updated_at before update on public.account_deletion_requests
for each row execute function public.set_account_lifecycle_updated_at();

alter table public.account_export_jobs enable row level security;
alter table public.account_deletion_requests enable row level security;
alter table public.account_lifecycle_events enable row level security;
alter table public.account_data_retention_policies enable row level security;
alter table public.account_legal_holds enable row level security;

drop policy if exists account_export_jobs_select_self on public.account_export_jobs;
create policy account_export_jobs_select_self on public.account_export_jobs
for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists account_deletion_requests_select_self on public.account_deletion_requests;
create policy account_deletion_requests_select_self on public.account_deletion_requests
for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists account_lifecycle_events_select_self on public.account_lifecycle_events;
create policy account_lifecycle_events_select_self on public.account_lifecycle_events
for select to authenticated using (user_id = (select auth.uid()));

revoke all on public.account_export_jobs, public.account_deletion_requests,
  public.account_lifecycle_events, public.account_data_retention_policies,
  public.account_legal_holds from anon, authenticated;
grant select on public.account_export_jobs, public.account_deletion_requests,
  public.account_lifecycle_events to authenticated;
grant select, insert, update, delete on public.account_export_jobs,
  public.account_deletion_requests, public.account_lifecycle_events,
  public.account_data_retention_policies, public.account_legal_holds to service_role;

revoke all on function public.request_my_account_export(text) from public, anon;
grant execute on function public.request_my_account_export(text) to authenticated;
revoke all on function public.claim_account_export_jobs(text,integer,integer) from public, anon, authenticated;
grant execute on function public.claim_account_export_jobs(text,integer,integer) to service_role;
revoke all on function public.renew_account_export_job_lease(uuid,uuid,integer) from public, anon, authenticated;\ngrant execute on function public.renew_account_export_job_lease(uuid,uuid,integer) to service_role;\nrevoke all on function public.build_my_account_export_snapshot(uuid,uuid) from public, anon, authenticated;
grant execute on function public.build_my_account_export_snapshot(uuid,uuid) to service_role;
revoke all on function public.complete_account_export_job(uuid,uuid,text,text,bigint,jsonb) from public, anon, authenticated;
grant execute on function public.complete_account_export_job(uuid,uuid,text,text,bigint,jsonb) to service_role;
revoke all on function public.fail_account_export_job(uuid,uuid,text,integer) from public, anon, authenticated;
grant execute on function public.fail_account_export_job(uuid,uuid,text,integer) to service_role;
revoke all on function public.create_account_deletion_request_for_actor(uuid) from public, anon, authenticated;
grant execute on function public.create_account_deletion_request_for_actor(uuid) to service_role;
revoke all on function public.cancel_my_account_deletion(uuid) from public, anon;
grant execute on function public.cancel_my_account_deletion(uuid) to authenticated;

insert into storage.buckets(id,name,public)
values ('account-exports','account-exports',false)
on conflict (id) do nothing;

do $$
begin
  if exists (
    select 1 from storage.buckets b
    where b.id = 'account-exports' and b.public is distinct from false
  ) then
    raise exception 'account_exports_bucket_must_remain_private';
  end if;
end;
$$;
