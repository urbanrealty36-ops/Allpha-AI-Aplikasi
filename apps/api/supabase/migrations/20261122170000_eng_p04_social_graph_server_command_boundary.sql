-- ENG-P04 Social Graph command boundary. Forward-only; do not replay historical migrations.
-- Keep one social_edges table and existing policy/event triggers as the canonical authority.
revoke insert, update, delete, truncate, references, trigger on table public.social_edges from public, anon, authenticated;
-- PostgreSQL table-level REVOKE does not remove column-level grants. Revoke
-- the exact authenticated write columns discovered in the live ACL catalog.
revoke insert (
  actor_user_id, target_user_id, actor_node_type, target_node_type,
  actor_agent_id, target_agent_id, edge_type, status, idempotency_key
) on table public.social_edges from public, anon, authenticated;
revoke update (status) on table public.social_edges from public, anon, authenticated;
grant select on table public.social_edges to authenticated;

create or replace function public.create_social_edge_for_actor(
  p_actor_user_id uuid,
  p_target_user_id uuid,
  p_actor_node_type text,
  p_target_node_type text,
  p_actor_agent_id uuid,
  p_target_agent_id uuid,
  p_edge_type text,
  p_idempotency_key text default null
) returns setof public.social_edges
language plpgsql security definer set search_path = ''
as $$
begin
  if p_actor_user_id is null or p_target_user_id is null then
    raise exception using errcode = '22023', message = 'social_edge_principal_required';
  end if;
  if p_actor_node_type is null or p_target_node_type is null
     or p_actor_node_type not in ('human', 'agent')
     or p_target_node_type not in ('human', 'agent')
     or p_edge_type is null or p_edge_type not in ('follow', 'block', 'mute') then
    raise exception using errcode = '22023', message = 'social_edge_type_invalid';
  end if;
  if (p_actor_node_type = 'human' and p_actor_agent_id is not null)
     or (p_actor_node_type = 'agent' and p_actor_agent_id is null)
     or (p_target_node_type = 'human' and p_target_agent_id is not null)
     or (p_target_node_type = 'agent' and p_target_agent_id is null) then
    raise exception using errcode = '22023', message = 'social_edge_node_shape_invalid';
  end if;
  if p_idempotency_key is not null and pg_catalog.char_length(p_idempotency_key) not between 8 and 160 then
    raise exception using errcode = '22023', message = 'social_idempotency_key_invalid';
  end if;
  perform pg_catalog.set_config('request.jwt.claim.sub', p_actor_user_id::text, true);
  return query
    insert into public.social_edges (
      actor_user_id, target_user_id, actor_node_type, target_node_type,
      actor_agent_id, target_agent_id, edge_type, idempotency_key
    ) values (
      p_actor_user_id, p_target_user_id, p_actor_node_type, p_target_node_type,
      p_actor_agent_id, p_target_agent_id, p_edge_type, p_idempotency_key
    )
    returning *;
end;
$$;

create or replace function public.accept_social_follow_for_actor(p_actor_user_id uuid, p_edge_id uuid)
returns setof public.social_edges
language plpgsql security definer set search_path = ''
as $$
begin
  if p_actor_user_id is null or p_edge_id is null then
    raise exception using errcode = '22023', message = 'social_follow_accept_input_invalid';
  end if;
  perform pg_catalog.set_config('request.jwt.claim.sub', p_actor_user_id::text, true);
  return query
    update public.social_edges e set status = 'active'
    where e.id = p_edge_id and e.target_user_id = p_actor_user_id
      and e.edge_type = 'follow' and e.status = 'requested'
    returning e.*;
end;
$$;

create or replace function public.reject_social_follow_for_actor(p_actor_user_id uuid, p_edge_id uuid)
returns setof public.social_edges
language plpgsql security definer set search_path = ''
as $$
begin
  if p_actor_user_id is null or p_edge_id is null then
    raise exception using errcode = '22023', message = 'social_follow_reject_input_invalid';
  end if;
  perform pg_catalog.set_config('request.jwt.claim.sub', p_actor_user_id::text, true);
  return query
    delete from public.social_edges e
    where e.id = p_edge_id and e.target_user_id = p_actor_user_id
      and e.edge_type = 'follow' and e.status = 'requested'
    returning e.*;
end;
$$;

create or replace function public.remove_social_edge_for_actor(p_actor_user_id uuid, p_edge_id uuid)
returns setof public.social_edges
language plpgsql security definer set search_path = ''
as $$
begin
  if p_actor_user_id is null or p_edge_id is null then
    raise exception using errcode = '22023', message = 'social_edge_remove_input_invalid';
  end if;
  perform pg_catalog.set_config('request.jwt.claim.sub', p_actor_user_id::text, true);
  return query
    delete from public.social_edges e
    where e.id = p_edge_id and e.actor_user_id = p_actor_user_id
    returning e.*;
end;
$$;

revoke all on function public.create_social_edge_for_actor(uuid,uuid,text,text,uuid,uuid,text,text) from public, anon, authenticated;
revoke all on function public.accept_social_follow_for_actor(uuid,uuid) from public, anon, authenticated;
revoke all on function public.reject_social_follow_for_actor(uuid,uuid) from public, anon, authenticated;
revoke all on function public.remove_social_edge_for_actor(uuid,uuid) from public, anon, authenticated;
grant execute on function public.create_social_edge_for_actor(uuid,uuid,text,text,uuid,uuid,text,text) to service_role;
grant execute on function public.accept_social_follow_for_actor(uuid,uuid) to service_role;
grant execute on function public.reject_social_follow_for_actor(uuid,uuid) to service_role;
grant execute on function public.remove_social_edge_for_actor(uuid,uuid) to service_role;
