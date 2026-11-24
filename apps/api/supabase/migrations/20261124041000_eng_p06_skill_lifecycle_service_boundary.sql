-- ENG-P06: move privileged Skill lifecycle mutations behind FastAPI service identity.
-- FastAPI authenticates the Human, supplies the trusted actor UUID, and invokes
-- these RPCs with service_role. No client role may call SECURITY DEFINER functions.
drop function if exists public.install_agent_skill(uuid,uuid,uuid,integer,boolean,text);
drop function if exists public.revoke_agent_skill_installation(uuid,uuid,text);
drop function if exists public.expire_agent_skill_installations(uuid);

create or replace function public.install_agent_skill(
  p_agent_id uuid,
  p_source_agent_id uuid,
  p_source_skill_id uuid,
  p_source_version integer,
  p_accept_license boolean,
  p_idempotency_key text,
  p_actor_user_id uuid
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
  v_actor uuid:=p_actor_user_id;
  v_source_agent public.ai_agents%rowtype;
  v_source_skill public.agent_skills%rowtype;
  v_snapshot jsonb;
  v_terms jsonb;
  v_license text;
  v_license_expiry timestamptz;
  v_snapshot_digest text;
  v_terms_digest text;
  v_existing public.agent_skill_installations%rowtype;
  v_installation public.agent_skill_installations%rowtype;
  v_installed_skill_id uuid:=gen_random_uuid();
  v_slug text;
begin
  if v_actor is null then
    raise exception 'AUTHENTICATED_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if not coalesce(p_accept_license,false) then
    raise exception 'SKILL_LICENSE_ACCEPTANCE_REQUIRED' using errcode='42501';
  end if;
  if p_agent_id is null or p_source_agent_id is null or p_source_skill_id is null
     or p_source_version is null or p_source_version<1
     or p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'SKILL_INSTALL_ARGUMENTS_INVALID' using errcode='22023';
  end if;
  if not private.has_agent_ownership(p_agent_id,v_actor,'owner') then
    raise exception 'TARGET_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  select * into v_existing from public.agent_skill_installations i
   where i.agent_id=p_agent_id and i.idempotency_key=p_idempotency_key;
  if found then
    if v_existing.source_agent_id<>p_source_agent_id or v_existing.source_skill_id<>p_source_skill_id
       or v_existing.source_version<>p_source_version then
      raise exception 'SKILL_INSTALL_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('installation',to_jsonb(v_existing),'installed_skill_id',v_existing.installed_skill_id,'idempotent_replay',true);
  end if;
  if p_agent_id=p_source_agent_id then
    raise exception 'SKILL_CANNOT_BE_INSTALLED_FROM_SAME_AGENT' using errcode='22023';
  end if;
  select * into v_source_agent from public.ai_agents a
   where a.id=p_source_agent_id and a.status='active' and a.visibility='public';
  if not found then raise exception 'SOURCE_AGENT_NOT_PUBLIC' using errcode='40400'; end if;
  select * into v_source_skill from public.agent_skills s
   where s.id=p_source_skill_id and s.agent_id=p_source_agent_id and s.status<>'archived';
  if not found then raise exception 'SOURCE_SKILL_NOT_AVAILABLE' using errcode='40400'; end if;
  select v.snapshot into v_snapshot
    from public.agent_skill_versions v
   where v.skill_id=p_source_skill_id and v.agent_id=p_source_agent_id and v.version=p_source_version
     and v.snapshot->>'status'='published'
   limit 1;
  if v_snapshot is null then raise exception 'PUBLISHED_SKILL_VERSION_NOT_FOUND' using errcode='40400'; end if;

  v_terms:=coalesce(v_snapshot->'publication_terms','{}'::jsonb);
  v_license:=coalesce(
    nullif(btrim(v_terms->>'license_key'),''),
    nullif(btrim(v_terms->>'license'),''),
    nullif(btrim(v_terms->>'license_type'),'')
  );
  if jsonb_typeof(v_terms)<>'object' or v_terms='{}'::jsonb or v_license is null then
    raise exception 'SKILL_PUBLICATION_LICENSE_TERMS_REQUIRED' using errcode='23514';
  end if;
  if lower(coalesce(v_terms->>'requires_purchase','false')) in ('true','yes','1')
     or lower(coalesce(v_terms->>'license_type','')) in ('paid','purchase_required')
     or (jsonb_typeof(v_terms->'price')='number' and (v_terms->>'price')::numeric>0) then
    raise exception 'SKILL_LICENSE_ENTITLEMENT_REQUIRED' using errcode='42501';
  end if;
  if nullif(v_terms->>'expires_at','') is not null then
    begin v_license_expiry:=(v_terms->>'expires_at')::timestamptz;
    exception when others then raise exception 'SKILL_LICENSE_EXPIRY_INVALID' using errcode='22023'; end;
    if v_license_expiry<=clock_timestamp() then raise exception 'SKILL_LICENSE_EXPIRED' using errcode='23514'; end if;
  end if;
  v_snapshot_digest:=encode(extensions.digest(v_snapshot::text,'sha256'),'hex');
  v_terms_digest:=encode(extensions.digest(v_terms::text,'sha256'),'hex');

  if exists(select 1 from public.agent_skill_installations i
     where i.agent_id=p_agent_id and i.source_skill_id=p_source_skill_id and i.source_version=p_source_version and i.status='active') then
    raise exception 'SKILL_VERSION_ALREADY_INSTALLED' using errcode='23505';
  end if;

  v_slug:=left(coalesce(v_snapshot->>'slug','skill'),35)||'-i-'||substr(replace(v_installed_skill_id::text,'-',''),1,12);
  insert into public.agent_skills(
    id,agent_id,created_by,slug,name,description,category,inputs_schema,outputs_schema,
    instructions,constraints,tool_dependencies,required_permission_scopes,model_requirements,
    budget_limits,tests,evaluation_rubric,provenance,version,changelog,publication_terms,status
  ) values(
    v_installed_skill_id,p_agent_id,v_actor,v_slug,
    coalesce(v_snapshot->>'name','Installed Skill'),
    coalesce(v_snapshot->>'description',''),
    coalesce(v_snapshot->>'category','general'),
    coalesce(v_snapshot->'inputs_schema','{"type":"object"}'::jsonb),
    coalesce(v_snapshot->'outputs_schema','{"type":"object"}'::jsonb),
    coalesce(v_snapshot->>'instructions',''),
    coalesce(v_snapshot->'constraints','{}'::jsonb),
    array(select jsonb_array_elements_text(coalesce(v_snapshot->'tool_dependencies','[]'::jsonb))),
    array(select jsonb_array_elements_text(coalesce(v_snapshot->'required_permission_scopes','[]'::jsonb))),
    coalesce(v_snapshot->'model_requirements','{}'::jsonb),
    coalesce(v_snapshot->'budget_limits','{}'::jsonb),
    coalesce(v_snapshot->'tests','[]'::jsonb),
    coalesce(v_snapshot->'evaluation_rubric','{}'::jsonb),
    coalesce(v_snapshot->'provenance','{}'::jsonb)||jsonb_build_object(
      'installed_from_agent_id',p_source_agent_id,
      'installed_from_skill_id',p_source_skill_id,
      'installed_from_version',p_source_version,
      'source_snapshot_digest',v_snapshot_digest,
      'license_terms_digest',v_terms_digest,
      'license_key',v_license
    ),
    1,'Installed from public Agent Skill; owner review required before publication.',
    v_terms,'draft'
  );

  insert into public.agent_skill_installations(
    agent_id,source_agent_id,source_skill_id,source_version,source_snapshot_digest,
    installed_skill_id,installed_by,installer_subject_ref,license_terms_snapshot,
    license_terms_digest,license_expires_at,idempotency_key
  ) values(
    p_agent_id,p_source_agent_id,p_source_skill_id,p_source_version,v_snapshot_digest,
    v_installed_skill_id,v_actor,encode(extensions.digest(v_actor::text,'sha256'),'hex'),
    v_terms,v_terms_digest,v_license_expiry,p_idempotency_key
  ) returning * into v_installation;

  insert into public.agent_skill_installation_events(
    installation_id,agent_id,source_agent_id,source_skill_id,event_type,actor_user_id,
    actor_subject_ref,source_version,source_snapshot_digest,license_terms_digest,details
  ) values(
    v_installation.id,p_agent_id,p_source_agent_id,p_source_skill_id,'installed',v_actor,
    encode(extensions.digest(v_actor::text,'sha256'),'hex'),p_source_version,
    v_snapshot_digest,v_terms_digest,jsonb_build_object('license_key',v_license,'installed_skill_id',v_installed_skill_id)
  );
  return jsonb_build_object('installation',to_jsonb(v_installation),'installed_skill_id',v_installed_skill_id,'idempotent_replay',false);
end;
$function$;

create or replace function public.revoke_agent_skill_installation(
  p_agent_id uuid,p_installation_id uuid,p_reason text,p_actor_user_id uuid
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare v_actor uuid:=p_actor_user_id; v_installation public.agent_skill_installations%rowtype;
begin
  if v_actor is null then
    raise exception 'AUTHENTICATED_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if not private.has_agent_ownership(p_agent_id,v_actor,'owner') then
    raise exception 'TARGET_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if p_reason is null or char_length(btrim(p_reason))<8 or char_length(p_reason)>500 then
    raise exception 'SKILL_INSTALL_REVOCATION_REASON_REQUIRED' using errcode='22023';
  end if;
  update public.agent_skill_installations i
     set status='revoked',revoked_by=v_actor,revoked_at=clock_timestamp(),
         revocation_reason=btrim(p_reason),updated_at=clock_timestamp()
   where i.id=p_installation_id and i.agent_id=p_agent_id and i.status='active'
   returning * into v_installation;
  if not found then raise exception 'ACTIVE_SKILL_INSTALLATION_NOT_FOUND' using errcode='40400'; end if;
  insert into public.agent_skill_installation_events(
    installation_id,agent_id,source_agent_id,source_skill_id,event_type,actor_user_id,
    actor_subject_ref,source_version,source_snapshot_digest,license_terms_digest,details
  ) values(
    v_installation.id,v_installation.agent_id,v_installation.source_agent_id,v_installation.source_skill_id,
    'revoked',v_actor,encode(extensions.digest(v_actor::text,'sha256'),'hex'),
    v_installation.source_version,v_installation.source_snapshot_digest,v_installation.license_terms_digest,
    jsonb_build_object('reason',v_installation.revocation_reason,'installed_skill_id',v_installation.installed_skill_id)
  );
  return jsonb_build_object('installation',to_jsonb(v_installation),'runtime_authorized',false);
end;
$function$;

create or replace function public.expire_agent_skill_installations(p_agent_id uuid,p_actor_user_id uuid)
returns integer
language plpgsql security definer set search_path=''
as $function$
declare v_actor uuid:=p_actor_user_id; v_row public.agent_skill_installations%rowtype; v_count integer:=0;
begin
  if v_actor is null then
    raise exception 'AUTHENTICATED_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if not private.has_agent_ownership(p_agent_id,v_actor,'owner') then
    raise exception 'TARGET_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  for v_row in
    update public.agent_skill_installations i
       set status='expired',revoked_at=clock_timestamp(),revocation_reason='license_expired',updated_at=clock_timestamp()
     where i.agent_id=p_agent_id and i.status='active'
       and i.license_expires_at is not null and i.license_expires_at<=clock_timestamp()
     returning i.*
  loop
    insert into public.agent_skill_installation_events(
      installation_id,agent_id,source_agent_id,source_skill_id,event_type,actor_user_id,
      actor_subject_ref,source_version,source_snapshot_digest,license_terms_digest,details
    ) values(
      v_row.id,v_row.agent_id,v_row.source_agent_id,v_row.source_skill_id,'expired',null,
      v_row.installer_subject_ref,v_row.source_version,v_row.source_snapshot_digest,v_row.license_terms_digest,
      jsonb_build_object('reason','license_expired','expired_at',v_row.license_expires_at)
    ) on conflict(installation_id,event_type) do nothing;
    v_count:=v_count+1;
  end loop;
  return v_count;
end;
$function$;

revoke all on function public.install_agent_skill(uuid,uuid,uuid,integer,boolean,text,uuid) from public,anon,authenticated;
revoke all on function public.revoke_agent_skill_installation(uuid,uuid,text,uuid) from public,anon,authenticated;
revoke all on function public.expire_agent_skill_installations(uuid,uuid) from public,anon,authenticated;
grant execute on function public.install_agent_skill(uuid,uuid,uuid,integer,boolean,text,uuid) to service_role;
grant execute on function public.revoke_agent_skill_installation(uuid,uuid,text,uuid) to service_role;
grant execute on function public.expire_agent_skill_installations(uuid,uuid) to service_role;

notify pgrst, 'reload schema';
