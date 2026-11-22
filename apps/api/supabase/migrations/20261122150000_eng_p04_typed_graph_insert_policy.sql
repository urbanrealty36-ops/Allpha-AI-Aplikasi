-- ENG-P04: allow owner-scoped typed node writes without the legacy owner-ID self check.
alter table public.social_edges drop constraint if exists social_edges_no_self;

drop policy if exists social_edges_insert_actor on public.social_edges;
create policy social_edges_insert_actor
on public.social_edges
for insert
to authenticated
with check (
  actor_user_id = (select auth.uid())
  and not (
    actor_node_type = target_node_type
    and coalesce(actor_agent_id,actor_user_id) = coalesce(target_agent_id,target_user_id)
  )
);

grant insert (actor_node_type,target_node_type,actor_agent_id,target_agent_id,idempotency_key)
on public.social_edges to authenticated;

comment on policy social_edges_insert_actor on public.social_edges is
  'ENG-P04: authenticated Human owner may create a typed edge only after the server/database ownership trigger validates the actor Agent and target visibility; self-edge comparison uses typed node identity, not shared owner context.';
