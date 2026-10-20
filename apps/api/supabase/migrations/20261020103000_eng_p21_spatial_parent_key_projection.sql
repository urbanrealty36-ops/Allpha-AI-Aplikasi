-- ENG-P21 forward repair: expose stable parent keys in the public navigation projection.
create or replace view public.spatial_public_navigation_nodes as
select n.id, n.node_key, n.parent_id, n.level, n.slug, n.display_name,
       n.coordinates, n.landmarks, n.scene_key, n.version, n.created_at,
       (select count(*)::integer from public.spatial_navigation_nodes child
         where child.parent_id=n.id and child.status='published' and child.access_policy='public') as child_count,
       parent.node_key as parent_node_key
from public.spatial_navigation_nodes n
left join public.spatial_navigation_nodes parent on parent.id=n.parent_id
where n.status='published' and n.access_policy='public';
revoke all on public.spatial_public_navigation_nodes from anon, authenticated;
grant select on public.spatial_public_navigation_nodes to service_role;
