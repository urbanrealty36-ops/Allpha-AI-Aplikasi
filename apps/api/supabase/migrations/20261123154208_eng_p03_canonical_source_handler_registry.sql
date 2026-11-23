-- ENG-P03: publish one canonical handler-capability registry to API and Super Admin.
create or replace function private.account_deletion_source_handler_available(
  p_source_key text, p_table_name text, p_filter_kind text, p_owner_columns text[]
)
returns boolean language sql immutable set search_path = '' as $$
  select
    (p_filter_kind = 'owner_columns' and coalesce(cardinality(p_owner_columns),0) > 0)
    or (p_source_key='agent_skills_owned' and p_table_name='agent_skills' and p_filter_kind='owned_agents')
    or (p_source_key='agent_runtime_checkpoints' and p_table_name='agent_runtime_checkpoints' and p_filter_kind='owned_runtime_tasks')
    or (p_source_key='agent_runtime_effect_receipts' and p_table_name='agent_runtime_effect_receipts' and p_filter_kind='owned_runtime_tasks')
    or (p_source_key='content_comments_on_owned' and p_table_name='content_comments' and p_filter_kind='owned_content')
    or (p_source_key='content_reactions_on_owned' and p_table_name='content_reactions' and p_filter_kind='content_activity')
    or (p_source_key='messages_in_conversations' and p_table_name='messages' and p_filter_kind='conversation_messages')
    or (p_source_key='community_posts_in_memberships' and p_table_name='community_posts' and p_filter_kind='member_communities')
    or (p_source_key='workspace_documents_in_memberships' and p_table_name='workspace_documents' and p_filter_kind='member_workspaces')
    or (p_source_key='workspace_annotations_in_memberships' and p_table_name='workspace_annotations' and p_filter_kind='member_workspaces');
$$;
revoke all on function private.account_deletion_source_handler_available(text,text,text,text[]) from public,anon,authenticated,service_role;
grant execute on function private.account_deletion_source_handler_available(text,text,text,text[]) to service_role;

drop function public.list_account_deletion_source_registry();
create function public.list_account_deletion_source_registry()
returns table (
  source_key text, table_name text, filter_kind text, owner_columns text[],
  dependency_order integer, enabled boolean, data_class text, deletion_action text,
  policy_version text, reason text, policy_active boolean, approved_by uuid,
  approved_at timestamptz, deletion_handler_available boolean
)
language plpgsql security definer set search_path = '' as $$
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  return query
    select s.source_key,s.table_name,s.filter_kind,s.owner_columns,s.sort_order,s.enabled,
           p.data_class,p.deletion_action,p.policy_version,p.reason,coalesce(p.active,false),
           p.approved_by,p.approved_at,
           private.account_deletion_source_handler_available(s.source_key,s.table_name,s.filter_kind,s.owner_columns)
      from private.account_export_sources s
      left join public.account_deletion_source_policies p on p.source_key=s.source_key
     order by s.sort_order,s.source_key;
end;
$$;
revoke all on function public.list_account_deletion_source_registry() from public,anon,authenticated;
grant execute on function public.list_account_deletion_source_registry() to service_role;