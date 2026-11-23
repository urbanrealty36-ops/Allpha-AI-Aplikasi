-- ENG-P04: exact, untruncated typed-node relationship counts for profile projections.
create or replace function public.social_graph_node_counts(p_node_type text, p_node_id uuid)
returns table(followers_count bigint, following_count bigint)
language plpgsql
stable
security definer
set search_path = ''
as $function$
begin
  if p_node_type not in ('human','agent') or p_node_id is null then
    raise exception using errcode='22023', message='social graph node reference is invalid';
  end if;
  return query
  select
    count(*) filter (
      where e.edge_type='follow' and e.status='active'
        and e.target_node_type=p_node_type
        and coalesce(e.target_agent_id,e.target_user_id)=p_node_id
    )::bigint as followers_count,
    count(*) filter (
      where e.edge_type='follow' and e.status='active'
        and e.actor_node_type=p_node_type
        and coalesce(e.actor_agent_id,e.actor_user_id)=p_node_id
    )::bigint as following_count
  from public.social_edges e;
end
$function$;

revoke all on function public.social_graph_node_counts(text,uuid) from public,anon,authenticated;
grant execute on function public.social_graph_node_counts(text,uuid) to service_role;
comment on function public.social_graph_node_counts(text,uuid) is
  'ENG-P04: exact counts for typed Human/Agent nodes without exposing edge records.';
