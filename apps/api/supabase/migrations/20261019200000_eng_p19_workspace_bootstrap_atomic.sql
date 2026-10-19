-- ENG-P19: atomically create a workspace and its initial access grants.
create or replace function public.create_workspace_with_owner(
  p_title text, p_description text, p_created_by uuid, p_community_id uuid, p_visibility text
) returns setof public.workspaces
language plpgsql security definer set search_path = public, pg_temp as $$
declare created public.workspaces;
begin
  if p_visibility not in ('private','community') then raise exception 'invalid_visibility'; end if;
  if p_visibility='community' and p_community_id is null then raise exception 'community_required'; end if;
  if p_community_id is not null and not exists (
    select 1 from public.community_memberships
    where community_id=p_community_id and user_id=p_created_by and status='active'
  ) then raise exception 'community_membership_required'; end if;
  insert into public.workspaces(title,description,created_by,community_id,visibility)
  values(trim(p_title),coalesce(p_description,''),p_created_by,p_community_id,p_visibility)
  returning * into created;
  insert into public.workspace_memberships(workspace_id,user_id,role,status)
  values(created.id,p_created_by,'owner','active');
  if p_visibility='community' then
    insert into public.workspace_memberships(workspace_id,user_id,role,status)
    select created.id, cm.user_id,
      case when cm.role='moderator' then 'editor' else 'viewer' end,
      'active'
    from public.community_memberships cm
    where cm.community_id=p_community_id and cm.status='active' and cm.user_id<>p_created_by
    on conflict(workspace_id,user_id) do nothing;
  end if;
  return next created;
end $$;
revoke all on function public.create_workspace_with_owner(text,text,uuid,uuid,text) from public, anon, authenticated;
grant execute on function public.create_workspace_with_owner(text,text,uuid,uuid,text) to service_role;
