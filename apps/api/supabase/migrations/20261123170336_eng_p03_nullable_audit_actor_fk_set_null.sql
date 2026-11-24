-- ENG-P03: retain grant, moderation and shared-document evidence while
-- anonymizing only nullable actor/requester references. Ownership references stay blocked.
do $$
declare
  r record;
  v_constraint record;
  v_count integer := 0;
begin
  for r in
    select * from (values
      ('public','agent_consumer_grant_events','agent_consumer_grant_events_actor_user_id_fkey','actor_user_id'),
      ('public','agent_consumer_grant_events','agent_consumer_grant_events_requester_user_id_fkey','requester_user_id'),
      ('public','agent_consumer_grants','agent_consumer_grants_granted_by_fkey','granted_by'),
      ('public','agent_resource_grant_audit','agent_resource_grant_audit_actor_user_id_fkey','actor_user_id'),
      ('public','agent_resource_grants','agent_resource_grants_granted_by_fkey','granted_by'),
      ('public','community_reports','community_reports_reporter_id_fkey','reporter_id'),
      ('public','generation_artifact_deletion_jobs','generation_artifact_deletion_jobs_requested_by_fkey','requested_by'),
      ('public','generation_output_review_events','generation_output_review_events_reviewer_user_id_fkey','reviewer_user_id'),
      ('public','platform_operator_grants','platform_operator_grants_granted_by_fkey','granted_by'),
      ('public','workspace_documents','workspace_documents_updated_by_fkey','updated_by')
    ) as expected(child_schema,child_table,constraint_name,fk_column)
  loop
    select c.confrelid,c.conkey,c.confkey,a.attnotnull as child_not_null
      into v_constraint
      from pg_catalog.pg_constraint c
      join pg_catalog.pg_attribute a on a.attrelid=c.conrelid and a.attnum=c.conkey[1]
     where c.conname=r.constraint_name
       and c.conrelid=pg_catalog.to_regclass(pg_catalog.format('%I.%I',r.child_schema,r.child_table))
       and c.contype='f';
    if not found
       or v_constraint.confrelid <> 'auth.users'::regclass
       or pg_catalog.cardinality(v_constraint.conkey) <> 1
       or pg_catalog.cardinality(v_constraint.confkey) <> 1 then
      raise exception 'ENG-P03 actor FK precondition failed for %.% constraint %',
        r.child_schema,r.child_table,r.constraint_name using errcode='55000';
    end if;
    execute pg_catalog.format('alter table %I.%I alter column %I drop not null',
      r.child_schema,r.child_table,r.fk_column);
    execute pg_catalog.format('alter table %I.%I drop constraint %I',
      r.child_schema,r.child_table,r.constraint_name);
    execute pg_catalog.format(
      'alter table %I.%I add constraint %I foreign key (%I) references auth.users(id) on delete set null not valid',
      r.child_schema,r.child_table,r.constraint_name,r.fk_column
    );
    execute pg_catalog.format('alter table %I.%I validate constraint %I',
      r.child_schema,r.child_table,r.constraint_name);
    update public.account_deletion_dependency_rules
       set delete_rule='SET NULL',
           resolution_action='database_set_null',
           reason='Actor/requester/reviewer/grantor reference only. Preserve the grant, moderation or shared-document evidence and clear only the deleted account reference; ownership and target-user references remain separately protected.',
           updated_at=pg_catalog.clock_timestamp()
     where child_schema=r.child_schema and child_table=r.child_table
       and constraint_name=r.constraint_name and fk_column=r.fk_column and active=true;
    if not found then
      raise exception 'ENG-P03 FK registry row missing for %',r.constraint_name using errcode='55000';
    end if;
    v_count:=v_count+1;
  end loop;
  if v_count<>10 then raise exception 'ENG-P03 expected 10 nullable audit actor FK conversions, got %',v_count; end if;
end $$;
