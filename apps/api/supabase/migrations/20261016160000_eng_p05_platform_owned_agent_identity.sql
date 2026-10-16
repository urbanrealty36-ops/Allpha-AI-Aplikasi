-- ENG-P05: platform-owned official Agent identities through the canonical AI Agent Identity tables.
-- SOURCE ONLY. Do not apply to canonical production. Validate only in an already-confirmed,
-- isolated non-production target during the approved ENG-P37 integration window.
-- This extends the existing identity contract; it does not create a second Agent registry.
--
-- The platform owner must be a real, dedicated service-account user in auth.users. The backend
-- supplies its configured UUID; no client may choose the owner. Provisioning remains draft-only.
create or replace function public.provision_official_agent_identity(
  p_bot_id uuid,
  p_platform_owner_user_id uuid
)
returns setof public.ai_agents
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_bot public.official_agent_bots;
  v_agent public.ai_agents;
  v_handle text;
  v_persona jsonb;
  v_boundaries jsonb;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;

  if p_bot_id is null or p_platform_owner_user_id is null then
    raise exception 'official_bot_and_platform_owner_required' using errcode = '22023';
  end if;

  if not exists (
    select 1 from auth.users u where u.id = p_platform_owner_user_id
  ) then
    raise exception 'platform_owner_identity_not_found' using errcode = '23503';
  end if;

  select b.* into v_bot
  from public.official_agent_bots b
  where b.id = p_bot_id
  for update;

  if not found then
    raise exception 'official_bot_not_found' using errcode = 'P0002';
  end if;

  -- Idempotent retry: return the existing canonical identity only if its owner
  -- and active ownership relationship still match the configured platform principal.
  if v_bot.agent_id is not null then
    select a.* into v_agent
    from public.ai_agents a
    where a.id = v_bot.agent_id
      and a.created_by = p_platform_owner_user_id;

    if not found or not exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = v_bot.agent_id
        and o.owner_user_id = p_platform_owner_user_id
        and o.ownership_role = 'owner'
        and o.status = 'active'
    ) then
      raise exception 'official_bot_identity_owner_mismatch' using errcode = '42501';
    end if;

    return next v_agent;
    return;
  end if;

  if v_bot.status not in ('draft', 'pending_approval') then
    raise exception 'official_bot_state_not_provisionable' using errcode = '23514';
  end if;

  v_handle := 'allpha_' ||
    pg_catalog.substr(pg_catalog.regexp_replace(v_bot.skill_key, '[^a-z0-9_]', '_', 'g'), 1, 16) ||
    '_' || pg_catalog.substr(pg_catalog.md5(v_bot.skill_key), 1, 5);

  v_persona := pg_catalog.jsonb_build_object(
    'allpha_skill_key', v_bot.skill_key,
    'allpha_skill_catalog_version', coalesce(v_bot.metadata ->> 'catalog_version', 'allpha-skill-catalog-v1'),
    'character_profile', pg_catalog.jsonb_build_object(
      'archetype_key', v_bot.character_archetype_key,
      'asset_key', null
    ),
    'official_bot', true
  );
  v_boundaries := pg_catalog.jsonb_build_object(
    'owner_type', 'platform',
    'official_bot_id', v_bot.id::text,
    'autonomy_mode', 'supervised',
    'runtime_authority', 'disabled_until_policy_tool_and_asset_binding'
  );

  insert into public.ai_agents (
    handle, display_name, description, avatar_url, persona,
    visibility, status, disclosure, boundaries, created_by
  ) values (
    v_handle,
    pg_catalog.left(v_bot.display_name, 80),
    pg_catalog.left(coalesce(v_bot.skill_description, ''), 1000),
    null,
    v_persona,
    'private',
    'draft',
    'Official Allpha AI Agent. Operated by Allpha with supervised, policy-bounded authority.',
    v_boundaries,
    p_platform_owner_user_id
  )
  returning * into v_agent;

  insert into public.agent_ownerships(agent_id, owner_user_id, ownership_role, status)
  values (v_agent.id, p_platform_owner_user_id, 'owner', 'active');

  update public.official_agent_bots
  set agent_id = v_agent.id,
      last_action = 'canonical_agent_identity_provisioned',
      updated_at = pg_catalog.now()
  where id = v_bot.id;

  return next v_agent;
end;
$$;

revoke all on function public.provision_official_agent_identity(uuid, uuid) from public, anon, authenticated;
grant execute on function public.provision_official_agent_identity(uuid, uuid) to service_role;

comment on function public.provision_official_agent_identity(uuid, uuid) is
  'ENG-P05 privileged adapter over canonical ai_agents + agent_ownerships. Requires service_role and a real dedicated platform owner auth.users identity; idempotently creates draft official bot identities. Source-only until approved non-production validation.';
