-- ENG-P03 forward repair: delete skills only for Agents with an active owner relationship.
create or replace function private.delete_account_source_rows(p_source_key text, p_user_id uuid)
returns bigint language plpgsql security definer set search_path = '' as $$
declare v_source private.account_export_sources%rowtype; v_rows bigint := 0;
begin
  if coalesce(auth.role(), '') <> 'service_role' then raise exception 'service_role_required' using errcode = '42501'; end if;
  if p_source_key is null or p_user_id is null then raise exception 'account_deletion_source_arguments_invalid' using errcode = '22023'; end if;
  select * into v_source from private.account_export_sources where source_key=p_source_key and enabled=true;
  if not found then raise exception 'account_deletion_source_not_enabled:%',p_source_key using errcode='P0002'; end if;
  if p_source_key='agent_skills_owned' and v_source.table_name='agent_skills' and v_source.filter_kind='owned_agents' then
    delete from public.agent_skills s where s.agent_id in (
      select ao.agent_id from public.agent_ownerships ao
       where ao.owner_user_id=p_user_id and ao.ownership_role='owner' and ao.status='active'
    );
  elsif p_source_key in ('agent_runtime_checkpoints','agent_runtime_effect_receipts') and v_source.filter_kind='owned_runtime_tasks' and v_source.table_name=p_source_key then
    if p_source_key='agent_runtime_checkpoints' then
      delete from public.agent_runtime_checkpoints c where c.task_id in (select t.id from public.agent_runtime_tasks t where t.owner_user_id=p_user_id);
    else
      delete from public.agent_runtime_effect_receipts e where e.task_id in (select t.id from public.agent_runtime_tasks t where t.owner_user_id=p_user_id);
    end if;
  elsif p_source_key='content_comments_on_owned' and v_source.table_name='content_comments' and v_source.filter_kind='owned_content' then
    delete from public.content_comments c where c.content_id in (select i.id from public.content_items i where i.owner_id=p_user_id);
  elsif p_source_key='content_reactions_on_owned' and v_source.table_name='content_reactions' and v_source.filter_kind='content_activity' then
    delete from public.content_reactions r where r.actor_user_id=p_user_id or r.content_id in (select i.id from public.content_items i where i.owner_id=p_user_id);
  elsif p_source_key='messages_in_conversations' and v_source.table_name='messages' and v_source.filter_kind='conversation_messages' then
    delete from public.messages m where m.sender_user_id=p_user_id;
  elsif p_source_key='community_posts_in_memberships' and v_source.table_name='community_posts' and v_source.filter_kind='member_communities' then
    delete from public.community_posts p where p.author_id=p_user_id;
  elsif p_source_key='workspace_documents_in_memberships' and v_source.table_name='workspace_documents' and v_source.filter_kind='member_workspaces' then
    delete from public.workspace_documents d where d.created_by=p_user_id;
  elsif p_source_key='workspace_annotations_in_memberships' and v_source.table_name='workspace_annotations' and v_source.filter_kind='member_workspaces' then
    delete from public.workspace_annotations a where a.author_id=p_user_id;
  else
    raise exception 'account_deletion_source_handler_missing:%',p_source_key using errcode='0A000';
  end if;
  get diagnostics v_rows=row_count;
  return v_rows;
end;
$$;