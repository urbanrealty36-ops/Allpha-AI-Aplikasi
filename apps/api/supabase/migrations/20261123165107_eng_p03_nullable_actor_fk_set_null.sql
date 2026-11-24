-- ENG-P03: preserve nullable actor/approver/reviewer references without
-- retaining a hard auth.users deletion dependency. Owner and financial references
-- remain fail-closed until their domain-specific transfer/anonymization policy exists.
do $$
declare
  r record;
  v_constraint record;
  v_count integer := 0;
begin
  for r in
    select * from (values
      ('public','agent_capabilities','agent_capabilities_reviewed_by_fkey','reviewed_by'),
      ('public','agent_consumer_grants','agent_consumer_grants_revoked_by_fkey','revoked_by'),
      ('public','agent_runtime_policies','agent_runtime_policies_approved_by_fkey','approved_by'),
      ('public','agent_runtime_policies','agent_runtime_policies_revoked_by_fkey','revoked_by'),
      ('public','agent_skill_challenge_runs','agent_skill_challenge_runs_release_decided_by_fkey','release_decided_by'),
      ('public','content_reports','content_reports_reviewed_by_fkey','reviewed_by'),
      ('public','content_retention_holds','content_retention_holds_released_by_fkey','released_by'),
      ('public','content_schedules','content_schedules_updated_by_fkey','updated_by'),
      ('public','credit_policy_versions','credit_policy_versions_approved_by_fkey','approved_by'),
      ('public','credit_policy_versions','credit_policy_versions_created_by_fkey','created_by'),
      ('public','credit_reconciliation_events','credit_reconciliation_events_actor_id_fkey','actor_id'),
      ('public','generation_artifact_deletion_jobs','generation_artifact_deletion_jobs_last_retried_by_fkey','last_retried_by'),
      ('public','generation_output_moderation_policies','generation_output_moderation_policies_approved_by_fkey','approved_by'),
      ('public','platform_operator_grants','platform_operator_grants_revoked_by_fkey','revoked_by'),
      ('public','spatial_agent_asset_mappings','spatial_agent_asset_mappings_reviewed_by_fkey','reviewed_by')
    ) as expected(child_schema,child_table,constraint_name,fk_column)
  loop
    select c.oid, c.confdeltype, c.confrelid, c.conkey, c.confkey,
           a.attnotnull as child_not_null
      into v_constraint
      from pg_catalog.pg_constraint c
      join pg_catalog.pg_attribute a
        on a.attrelid=c.conrelid and a.attnum=c.conkey[1]
     where c.conname=r.constraint_name
       and c.conrelid=pg_catalog.to_regclass(pg_catalog.format('%I.%I',r.child_schema,r.child_table))
       and c.contype='f';

    if not found
       or v_constraint.confrelid <> 'auth.users'::regclass
       or pg_catalog.cardinality(v_constraint.conkey) <> 1
       or pg_catalog.cardinality(v_constraint.confkey) <> 1
       or v_constraint.child_not_null then
      raise exception 'ENG-P03 FK precondition failed for %.% constraint %',
        r.child_schema,r.child_table,r.constraint_name using errcode='55000';
    end if;

    execute pg_catalog.format(
      'alter table %I.%I drop constraint %I',
      r.child_schema,r.child_table,r.constraint_name
    );
    execute pg_catalog.format(
      'alter table %I.%I add constraint %I foreign key (%I) references auth.users(id) on delete set null not valid',
      r.child_schema,r.child_table,r.constraint_name,r.fk_column
    );
    execute pg_catalog.format(
      'alter table %I.%I validate constraint %I',
      r.child_schema,r.child_table,r.constraint_name
    );

    update public.account_deletion_dependency_rules
       set delete_rule='SET NULL',
           resolution_action='database_set_null',
           reason='Nullable actor/approver/reviewer reference. Preserve the operational, moderation, policy, reconciliation or audit row and clear only this identity reference when the auth account is deleted. The actual PostgreSQL FK is ON DELETE SET NULL; no business owner or ledger row is deleted.',
           updated_at=pg_catalog.clock_timestamp()
     where child_schema=r.child_schema
       and child_table=r.child_table
       and constraint_name=r.constraint_name
       and fk_column=r.fk_column
       and active=true;

    if not found then
      raise exception 'ENG-P03 dependency registry row missing for %',r.constraint_name
        using errcode='55000';
    end if;
    v_count := v_count + 1;
  end loop;

  if v_count <> 15 then
    raise exception 'ENG-P03 expected 15 nullable actor FK conversions, got %',v_count;
  end if;

  update public.account_deletion_dependency_rules
     set reason = case
       when child_table in ('billing_orders','billing_receipts','billing_subscriptions',
                            'credit_ledger_accounts','credit_policy_versions',
                            'credit_reconciliation_events')
         then 'Financial or credit governance reference. Preserve ledger, order, receipt, subscription and reconciliation history; deletion remains blocked until the canonical financial retention and identity-anonymization path is implemented.'
       when child_table in ('agent_ownerships','ai_agents','agent_skills','agent_skill_versions',
                            'agent_capabilities','agent_runtime_policies','agent_resource_grants',
                            'agent_consumer_grants','agent_consumer_grant_events')
         then 'Agent ownership, capability or grant dependency. Transfer or revoke the resource through the canonical Agent ownership/permission lifecycle before deleting the human identity; do not cascade owner relationships.'
       when child_table in ('organizations','organization_memberships','platform_operator_grants')
         then 'Organization ownership or privileged operator dependency. Transfer ownership or revoke the privileged grant through its canonical lifecycle before deleting the identity; preserve the governance history.'
       when child_table in ('communities','community_invites','community_missions',
                            'community_posts','community_reports','workspaces',
                            'workspace_documents','workspace_document_versions',
                            'workspace_annotations')
         then 'Shared community/workspace authorship or ownership dependency. Preserve shared records and other participants; transfer ownership or apply a source-specific anonymized attribution path before deleting the identity.'
       when child_table in ('generation_jobs','generation_artifacts',
                            'generation_artifact_deletion_jobs','cinema_generation_job_links',
                            'playback_entitlements')
         then 'Generation/media ownership, payer or entitlement dependency. Complete private artifact cleanup and reconcile the associated usage/credit state before resolving this identity reference; preserve charge and settlement history.'
       when child_table in ('content_retention_holds','content_reports',
                            'generation_output_review_events','generation_output_moderation_policies')
         then 'Moderation, review or retention-governance evidence. Preserve the case/history and resolve actor attribution through a nullable reference or immutable pseudonymous audit identity; do not delete evidence.'
       else
         'Restricted identity dependency. Preserve the referenced business/audit record; a source-specific ownership transfer, retention, or anonymized-attribution implementation is required before this FK can be released.'
     end,
     updated_at=pg_catalog.clock_timestamp()
   where active=true
     and resolution_action='block'
     and reason is null;

  if (select count(*) from public.account_deletion_dependency_rules
       where active=true and resolution_action='block' and reason is null) <> 0 then
    raise exception 'ENG-P03 unresolved FK block reasons remain';
  end if;
end $$;
