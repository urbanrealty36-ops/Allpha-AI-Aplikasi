-- ENG-P03: complete remaining source-specific Cinema, Conversation and Spatial theme dispositions.
alter table public.conversations alter column created_by drop not null;
alter table public.conversations drop constraint conversations_created_by_fkey;
alter table public.conversations add constraint conversations_created_by_fkey
  foreign key (created_by) references auth.users(id) on delete set null;

alter table public.spatial_themes alter column created_by drop not null;
alter table public.spatial_theme_versions alter column created_by drop not null;

alter table public.account_deletion_dependency_rules
  drop constraint if exists account_deletion_dependency_rules_resolution_action_check;
alter table public.account_deletion_dependency_rules
  add constraint account_deletion_dependency_rules_resolution_action_check
  check (resolution_action = any (array[
    'database_cascade','database_set_null','delete_rows','set_null','block','transfer_owner'
  ]::text[]));

update public.account_deletion_dependency_rules
   set resolution_action='set_null',delete_rule='SET NULL',
       reason='Conversation creator attribution is anonymized while the shared conversation and participant/message history remain intact.',
       updated_at=clock_timestamp()
 where active=true and constraint_name='conversations_created_by_fkey';

alter table public.account_deletion_source_policies
  drop constraint if exists account_deletion_source_policies_deletion_action_check;
alter table public.account_deletion_source_policies
  add constraint account_deletion_source_policies_deletion_action_check
  check (deletion_action = any (array['delete_rows','preserve','block','anonymize']::text[]));

create or replace function private.anonymize_account_deletion_source(
  p_source_key text,
  p_user_id uuid
) returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_rows bigint := 0;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_source_key is null or p_user_id is null then
    raise exception 'account_deletion_anonymize_arguments_invalid' using errcode='22023';
  end if;

  if p_source_key='spatial_theme_versions' then
    update public.spatial_theme_versions
       set created_by=null
     where created_by=p_user_id;
  elsif p_source_key='spatial_themes_created' then
    update public.spatial_themes
       set created_by=null,updated_at=clock_timestamp()
     where created_by=p_user_id;
  else
    raise exception 'account_deletion_anonymize_handler_missing:%',p_source_key using errcode='0A000';
  end if;
  get diagnostics v_rows=row_count;
  return v_rows;
end;
$$;

revoke all on function private.anonymize_account_deletion_source(text,uuid)
  from public,anon,authenticated;
grant execute on function private.anonymize_account_deletion_source(text,uuid)
  to service_role;

update public.account_deletion_source_policies
   set deletion_action='delete_rows',
       reason='Owner-scoped Cinema title and episode media are removed after the worker completes their queued Storage cleanup and legal-hold checks.',
       updated_at=clock_timestamp()
 where active=true and source_key in ('cinema_episodes','cinema_titles');

update public.account_deletion_source_policies
   set deletion_action='preserve',
       reason='Preserve shared conversation and participant/message history; creator identity is anonymized by the nullable SET NULL FK disposition.',
       updated_at=clock_timestamp()
 where active=true and source_key='conversations';

update public.account_deletion_source_policies
   set deletion_action='anonymize',
       reason='Preserve published theme catalog and immutable version manifests while clearing only the deleted creator attribution through a source-specific handler.',
       updated_at=clock_timestamp()
 where active=true and source_key in ('spatial_theme_versions','spatial_themes_created');

do $$
declare
  v_definition text;
  v_old text := $old$
      elsif v_step.action='delete_rows' then
        select * into v_source from private.account_export_sources
         where source_key=v_step.step_key and enabled=true;
        if not found then
          raise exception 'account_deletion_source_handler_missing:%',v_step.step_key using errcode='0A000';
        end if;
        if v_source.filter_kind='owner_columns' then
$old$;
  v_new text := $new$
      elsif v_step.action='anonymize' then
        v_rows:=private.anonymize_account_deletion_source(v_step.step_key,v_job.user_id);
      elsif v_step.action='delete_rows' then
        select * into v_source from private.account_export_sources
         where source_key=v_step.step_key and enabled=true;
        if not found then
          raise exception 'account_deletion_source_handler_missing:%',v_step.step_key using errcode='0A000';
        end if;
        if v_source.filter_kind='owner_columns' then
$new$;
begin
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  if position(v_new in v_definition)>0 then return; end if;
  if position(v_old in v_definition)=0 then
    raise exception 'account_deletion_source_anonymize_executor_patch_anchor_missing';
  end if;
  execute replace(v_definition,v_old,v_new);
end;
$$;

update public.account_deletion_source_policies
   set deletion_action='preserve',
       reason='Preserve Agent skill definitions when their parent Agent is transferred; the deletion executor blocks the entire transaction if any Agent lacks a validated successor.',
       updated_at=clock_timestamp()
 where active=true and source_key='agent_skills_owned';
