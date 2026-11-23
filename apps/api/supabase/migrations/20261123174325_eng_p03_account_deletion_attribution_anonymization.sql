-- ENG-P03: preserve shared content while anonymizing attribution and revoking credentials.
-- The migration changes only FK nullability/actions; data is modified only inside a
-- lease-fenced deletion execution after storage cleanup and legal-hold checks.
alter table public.agent_capabilities alter column created_by drop not null;
alter table public.agent_capabilities drop constraint agent_capabilities_created_by_fkey;
alter table public.agent_capabilities add constraint agent_capabilities_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.agent_runtime_policies alter column created_by drop not null;
alter table public.agent_runtime_policies drop constraint agent_runtime_policies_created_by_fkey;
alter table public.agent_runtime_policies add constraint agent_runtime_policies_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.agent_skill_versions alter column created_by drop not null;
alter table public.agent_skill_versions drop constraint agent_skill_versions_created_by_fkey;
alter table public.agent_skill_versions add constraint agent_skill_versions_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.agent_skills alter column created_by drop not null;
alter table public.agent_skills drop constraint agent_skills_created_by_fkey;
alter table public.agent_skills add constraint agent_skills_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.ai_agents alter column created_by drop not null;
alter table public.ai_agents drop constraint ai_agents_created_by_fkey;
alter table public.ai_agents add constraint ai_agents_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.communities alter column created_by drop not null;
alter table public.communities drop constraint communities_created_by_fkey;
alter table public.communities add constraint communities_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.community_invites alter column created_by drop not null;
alter table public.community_invites drop constraint community_invites_created_by_fkey;
alter table public.community_invites add constraint community_invites_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.community_missions alter column created_by drop not null;
alter table public.community_missions drop constraint community_missions_created_by_fkey;
alter table public.community_missions add constraint community_missions_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.community_posts alter column author_id drop not null;
alter table public.community_posts drop constraint community_posts_author_id_fkey;
alter table public.community_posts add constraint community_posts_author_id_fkey
  foreign key (author_id) references auth.users(id) on delete set null;

alter table public.platform_operator_grants alter column user_id drop not null;
alter table public.platform_operator_grants drop constraint platform_operator_grants_user_id_fkey;
alter table public.platform_operator_grants add constraint platform_operator_grants_user_id_fkey
  foreign key (user_id) references auth.users(id) on delete set null;

alter table public.spatial_agent_asset_mappings alter column created_by drop not null;
alter table public.spatial_agent_asset_mappings drop constraint spatial_agent_asset_mappings_created_by_fkey;
alter table public.spatial_agent_asset_mappings add constraint spatial_agent_asset_mappings_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.workspace_annotations alter column author_id drop not null;
alter table public.workspace_annotations drop constraint workspace_annotations_author_id_fkey;
alter table public.workspace_annotations add constraint workspace_annotations_author_id_fkey
  foreign key (author_id) references auth.users(id) on delete set null;

alter table public.workspace_document_versions alter column created_by drop not null;
alter table public.workspace_document_versions drop constraint workspace_document_versions_created_by_fkey;
alter table public.workspace_document_versions add constraint workspace_document_versions_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.workspace_documents alter column created_by drop not null;
alter table public.workspace_documents drop constraint workspace_documents_created_by_fkey;
alter table public.workspace_documents add constraint workspace_documents_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.workspaces alter column created_by drop not null;
alter table public.workspaces drop constraint workspaces_created_by_fkey;
alter table public.workspaces add constraint workspaces_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

update public.account_deletion_dependency_rules
   set resolution_action='set_null', delete_rule='SET NULL',
       reason='Preserve the source record and anonymize only its creator/author attribution; FK now supports SET NULL and the executor applies it after legal-hold and Storage gates.',
       updated_at=clock_timestamp()
 where active=true and constraint_name in (
   'agent_capabilities_created_by_fkey',
   'agent_runtime_policies_created_by_fkey',
   'agent_skill_versions_created_by_fkey',
   'agent_skills_created_by_fkey',
   'ai_agents_created_by_fkey',
   'communities_created_by_fkey',
   'community_invites_created_by_fkey',
   'community_missions_created_by_fkey',
   'community_posts_author_id_fkey',
   'platform_operator_grants_user_id_fkey',
   'spatial_agent_asset_mappings_created_by_fkey',
   'workspace_annotations_author_id_fkey',
   'workspace_document_versions_created_by_fkey',
   'workspace_documents_created_by_fkey',
   'workspaces_created_by_fkey'
 );

update public.account_deletion_source_policies
   set deletion_action='preserve',
       reason='Preserve shared or transferable resource content; the FK executor anonymizes creator attribution or revokes the invite/grant before nulling the identity reference.',
       updated_at=clock_timestamp()
 where active=true and source_key in (
   'agent_capabilities',
   'agent_skill_versions_created',
   'agent_skills_created',
   'agent_skills_owned',
   'agents_created',
   'communities_created',
   'community_invites_created',
   'spatial_agent_asset_mappings',
   'workspaces_created'
 );

do $$
declare
  v_definition text;
  v_old text := $old$
          v_sql:=format('UPDATE %I.%I SET %I=NULL WHERE %I::text = $1',
            v_rule.child_schema,v_rule.child_table,v_rule.fk_column,v_rule.fk_column);
$old$;
  v_new text := $new$
          if v_rule.child_table='community_invites' and v_rule.fk_column='created_by' then
            update public.community_invites
               set revoked_at=coalesce(revoked_at,clock_timestamp())
             where created_by=v_job.user_id;
          elsif v_rule.child_table='platform_operator_grants' and v_rule.fk_column='user_id' then
            update public.platform_operator_grants
               set status='revoked',
                   revoked_at=coalesce(revoked_at,clock_timestamp()),
                   revocation_reason=coalesce(revocation_reason,'account_deletion')
             where user_id=v_job.user_id and status='active';
          end if;
          v_sql:=format('UPDATE %I.%I SET %I=NULL WHERE %I::text = $1',
            v_rule.child_schema,v_rule.child_table,v_rule.fk_column,v_rule.fk_column);
$new$;
begin
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  if position(v_new in v_definition)>0 then return; end if;
  if position(v_old in v_definition)=0 then
    raise exception 'account_deletion_anonymization_executor_patch_anchor_missing';
  end if;
  execute replace(v_definition,v_old,v_new);
end;
$$;
