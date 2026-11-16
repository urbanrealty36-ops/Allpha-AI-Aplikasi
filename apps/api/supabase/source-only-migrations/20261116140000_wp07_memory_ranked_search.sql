-- WP-07 owner-private Memory retrieval: ranked full-text + policy metadata.
-- This does not create a vector column or claim semantic/hybrid vector retrieval.
begin;

create or replace function public.agent_memory_search(
  p_owner_user_id uuid,
  p_agent_id uuid,
  p_policy_ids uuid[],
  p_purpose text,
  p_allowed_sensitivities text[],
  p_query text default null,
  p_max_sensitivity text default null,
  p_limit integer default 12
)
returns table (
  id uuid,
  memory_type text,
  content text,
  classification text,
  source_ref jsonb,
  provenance jsonb,
  confidence numeric,
  version integer,
  content_sha256 text,
  policy_id uuid,
  policy_version integer,
  created_at timestamptz,
  retrieval_score real,
  retrieval_method text
)
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_query tsquery;
  v_max_rank integer;
begin
  if current_user <> 'service_role' then
    raise exception 'MEMORY_SERVICE_ROLE_REQUIRED' using errcode='42501';
  end if;
  if p_owner_user_id is null or p_purpose is null
    or p_purpose not in ('agent_generation_context','agent_runtime_context','workflow_context','personalization_context')
    or p_policy_ids is null or cardinality(p_policy_ids) not between 1 and 20
    or p_allowed_sensitivities is null or cardinality(p_allowed_sensitivities) not between 1 and 4
    or p_limit not between 1 and 30
    or (p_query is not null and char_length(p_query) > 300)
    or (p_max_sensitivity is not null and p_max_sensitivity not in ('public','internal','confidential','restricted'))
    or not (p_allowed_sensitivities <@ array['public','internal','confidential','restricted']::text[])
  then
    raise exception 'MEMORY_SEARCH_REQUEST_INVALID' using errcode='22023';
  end if;

  v_query := case
    when nullif(trim(p_query), '') is null then null
    else plainto_tsquery('simple'::regconfig, trim(p_query))
  end;
  v_max_rank := case p_max_sensitivity
    when 'public' then 0 when 'internal' then 1
    when 'confidential' then 2 when 'restricted' then 3
    else 3
  end;

  return query
  select
    i.id, i.memory_type, i.content, i.classification,
    i.source_ref, i.provenance, i.confidence, i.version,
    i.content_sha256, i.policy_id, i.policy_version, i.created_at,
    case when v_query is null then 0::real else ts_rank_cd(i.search_vector, v_query)::real end,
    case when v_query is null then 'metadata'::text else 'keyword'::text end
  from public.agent_memory_items i
  join public.agent_memory_policies p
    on p.id = i.policy_id
   and p.owner_user_id = p_owner_user_id
   and p.agent_id is not distinct from p_agent_id
   and p.enabled = true
   and p.consent_version = 'allpha.memory.v1'
   and p.consent_revoked_at is null
   and p.policy_version = i.policy_version
   and p.allowed_purposes @> array[p_purpose]::text[]
   and i.classification = any(p.allowed_sensitivities)
  where i.owner_user_id = p_owner_user_id
    and i.agent_id is not distinct from p_agent_id
    and i.policy_id = any(p_policy_ids)
    and i.purpose = p_purpose
    and i.status = 'active'
    and i.retention_expires_at > now()
    and i.classification = any(p_allowed_sensitivities)
    and (
      p_max_sensitivity is null
      or case i.classification
        when 'public' then 0 when 'internal' then 1
        when 'confidential' then 2 when 'restricted' then 3
        else 99
      end <= v_max_rank
    )
    and (v_query is null or i.search_vector @@ v_query)
  order by
    case when v_query is null then 0::real else ts_rank_cd(i.search_vector, v_query)::real end desc,
    i.created_at desc
  limit p_limit;
end;
$$;

revoke all on function public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer)
  from public, anon, authenticated;
grant execute on function public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer)
  to service_role;

comment on function public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer) is
  'Owner/Agent/policy/consent/retention constrained ranked full-text Memory retrieval. Vector search remains disabled until an approved embedding/index profile exists.';

commit;
