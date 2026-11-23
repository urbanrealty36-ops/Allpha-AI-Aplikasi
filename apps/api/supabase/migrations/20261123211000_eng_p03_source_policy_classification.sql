-- ENG-P03: deterministically classify every enabled export/deletion source.
-- This records the product-owner-directed source map but deliberately leaves
-- policies inactive: retention periods and the 42 remaining FK dispositions
-- must be configured before destructive execution can be enabled.
do $$
declare v_count integer;
begin
  update public.account_deletion_source_policies p
     set data_class = case
       when p.filter_kind in ('participant_conversations','conversation_messages')
         then 'session_scoped'
       when p.table_name in (
         'communities','community_memberships','community_mission_progress',
         'community_mission_progress_events','community_posts','community_invites',
         'community_reports','workspaces','workspace_memberships','workspace_documents',
         'workspace_document_versions','workspace_annotations','workspace_presence',
         'organizations','organization_memberships'
       ) then 'tenant_shared'
       when p.table_name in (
         'ai_agents','agent_ownerships','agent_skills','agent_skill_versions',
         'agent_capabilities','agent_knowledge_sources','agent_knowledge_jobs',
         'agent_knowledge_chunks','agent_model_usage_metering','agent_runtime_policies',
         'agent_runtime_sessions','agent_runtime_tasks','agent_runtime_checkpoints',
         'agent_runtime_effect_receipts','agent_skill_challenge_runs',
         'agent_skill_challenge_achievement_evidence','agent_skill_challenge_issue_windows',
         'agent_consumer_grants','agent_consumer_grant_events','agent_resource_grant_audit',
         'agent_resource_grants','agent_social_action_approvals','agent_social_audit_events',
         'agent_social_presence_policies','workflow_definitions','workflow_runs',
         'workflow_steps','workflow_run_events','generation_jobs','generation_artifacts',
         'generation_artifact_deletion_jobs','generation_job_cancellation_events',
         'cinema_titles','cinema_episodes','cinema_generation_job_links'
       ) then 'agent_operational'
       when p.table_name in (
         'spatial_themes','spatial_theme_versions','spatial_agent_asset_mappings'
       ) then 'public_catalog'
       else 'owner_private'
     end,
     deletion_action = case
       when p.source_key in (
         'agent_ownerships','agents_created','agent_skills_created',
         'agent_skill_versions_created','agent_capabilities','conversations',
         'communities_created','workspaces_created','organizations_owned',
         'cinema_titles','cinema_episodes','spatial_themes_created',
         'spatial_theme_versions','spatial_agent_asset_mappings'
       ) then 'block'
       when p.table_name in (
         'billing_orders','billing_receipts','billing_subscriptions',
         'playback_entitlements','credit_ledger_accounts','credit_ledger_entries',
         'credit_balance_projection','credit_reservations','credit_reconciliation_events',
         'audit_events','platform_operator_grants','platform_operator_audit_events',
         'agent_resource_grant_audit','agent_social_audit_events',
         'agent_consumer_grant_events','agent_skill_challenge_achievement_evidence',
         'agent_skill_challenge_issue_windows','content_reports','content_appeals',
         'content_retention_holds','content_retention_receipts','community_reports',
         'generation_artifact_deletion_jobs','generation_job_cancellation_events',
         'content_lifecycle_events','workflow_run_events'
       ) then 'preserve'
       else 'delete_rows'
     end,
     dependency_order = p.dependency_order,
     policy_version = 'owner-directive-2026-11-23-v1',
     reason = 'Source classification derived from the canonical account export registry (table, filter_kind and owner_columns) and Master PRD v3.1.0 §§74.1, 75; source-level visibility is not inferred. Disposition is a conservative implementation mapping only. Policy remains inactive until retention periods, legal-hold behavior and FK dependencies are configured.',
     active = false,
     approved_by = null,
     approved_at = null,
     updated_at = pg_catalog.clock_timestamp()
   where exists (
     select 1 from private.account_export_sources s
      where s.source_key=p.source_key and s.enabled=true
   );

  get diagnostics v_count = row_count;
  if v_count <> 106 then
    raise exception 'ENG-P03 expected 106 enabled source policies to be classified, updated %',v_count;
  end if;

  if exists (
    select 1 from public.account_deletion_source_policies p
    join private.account_export_sources s using(source_key)
    where s.enabled=true
      and (p.data_class is null or p.deletion_action is null
        or p.policy_version is null or p.reason is null or p.active)
  ) then
    raise exception 'ENG-P03 source policy classification is incomplete or unexpectedly active';
  end if;
end $$;
