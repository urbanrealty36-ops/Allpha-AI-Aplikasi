-- WP-04: make moderation appeal decisions atomic.
-- The API service role is the only caller; operator authorization remains in FastAPI.
create or replace function public.decide_content_appeal(
  p_appeal_id uuid,
  p_operator_id uuid,
  p_decision text,
  p_reason text
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_appeal public.content_appeals%rowtype;
  v_content public.content_items%rowtype;
begin
  if p_decision not in ('approve','reject') then
    return jsonb_build_object('outcome','invalid_decision');
  end if;
  if char_length(coalesce(trim(p_reason),'')) < 8 or char_length(p_reason) > 500 then
    return jsonb_build_object('outcome','invalid_reason');
  end if;
  select * into v_appeal
  from public.content_appeals
  where id = p_appeal_id
  for update;
  if not found or v_appeal.status <> 'pending' then
    return jsonb_build_object('outcome','appeal_conflict');
  end if;

  select * into v_content
  from public.content_items
  where id = v_appeal.content_id and owner_id = v_appeal.owner_id
  for update;
  if not found then
    return jsonb_build_object('outcome','content_conflict');
  end if;

  if p_decision = 'approve' and (
    v_content.status <> 'failed'
    or v_content.moderation_status <> 'rejected'
    or v_content.version <> v_appeal.submitted_version
  ) then
    return jsonb_build_object('outcome','content_conflict');
  end if;

  update public.content_appeals
  set status = case when p_decision = 'approve' then 'approved' else 'rejected' end,
      decision_reason = trim(p_reason),
      decided_by = p_operator_id,
      decided_at = now()
  where id = p_appeal_id
  returning * into v_appeal;

  if p_decision = 'approve' then
    update public.content_items
    set status = 'review',
        moderation_status = 'pending',
        error_code = null,
        version = version + 1
    where id = v_content.id
    returning * into v_content;
  end if;

  return jsonb_build_object(
    'outcome','committed',
    'appeal',to_jsonb(v_appeal),
    'content',case when p_decision = 'approve' then to_jsonb(v_content) else null end
  );
end;
$$;

revoke all on function public.decide_content_appeal(uuid,uuid,text,text) from public, anon, authenticated;
grant execute on function public.decide_content_appeal(uuid,uuid,text,text) to service_role;
