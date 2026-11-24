-- ENG-P06: materialize license expiry events on owner reads; Runtime independently fails closed.
create or replace function public.expire_agent_skill_installations(p_agent_id uuid)
returns integer
language plpgsql security definer set search_path=''
as $function$
declare v_actor uuid:=auth.uid(); v_row public.agent_skill_installations%rowtype; v_count integer:=0;
begin
  if v_actor is null or coalesce(auth.role(),'')<>'authenticated' then
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
revoke all on function public.expire_agent_skill_installations(uuid) from public,anon;
grant execute on function public.expire_agent_skill_installations(uuid) to authenticated;
