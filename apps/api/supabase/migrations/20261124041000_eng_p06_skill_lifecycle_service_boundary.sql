-- ENG-P06: move privileged Skill lifecycle mutations behind FastAPI service identity.
-- FastAPI authenticates the Human, supplies the trusted actor UUID, and invokes
-- these RPCs with service_role. No client role may call SECURITY DEFINER functions.
drop function if exists public.install_agent_skill(uuid,uuid,uuid,integer,boolean,text);
drop function if exists public.revoke_agent_skill_installation(uuid,uuid,text);
drop function if exists public.expire_agent_skill_installations(uuid);

create or 

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
