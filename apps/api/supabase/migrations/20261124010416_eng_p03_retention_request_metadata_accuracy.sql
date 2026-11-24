-- ENG-P03: report actual retention-policy configuration at request creation.
-- Also make the service-role guard null-safe.

do $$
declare
  v_definition text;
  v_old text;
  v_new text;
begin
  v_definition:=pg_get_functiondef('public.create_account_deletion_request_for_actor(uuid)'::regprocedure);

  v_definition:=replace(
    v_definition,
    'if auth.role() <> ''service_role'' then',
    'if coalesce(auth.role(),'''') <> ''service_role'' then'
  );

  v_old:=$old$jsonb_build_object('execution_state','awaiting_policy','retention_policy_configured',false)$old$;
  v_new:=$new$jsonb_build_object(
    'execution_state','awaiting_policy',
    'retention_policy_configured',
    (select count(distinct p.data_class)=6
       from public.account_data_retention_policies p
      where p.active=true and p.retention_days>=0
        and nullif(p.policy_version,'') is not null
        and nullif(p.legal_basis,'') is not null
        and p.decision_source='product_owner_directive'
        and nullif(p.decision_reference,'') is not null)
  )$new$;

  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then
      raise exception 'account_deletion_retention_metadata_anchor_missing';
    end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  execute v_definition;
end;
$$;
