-- ENG-P03: enforce exact FK metadata/constraint agreement and active-owner transfer semantics.

update public.account_deletion_dependency_rules
   set delete_rule='RESTRICT'
 where active=true and child_schema='public' and child_table='content_retention_holds'
   and constraint_name='content_retention_holds_created_by_fkey';

create or replace function private.account_deletion_fk_action_mismatch_count()
returns integer
language sql
stable
security definer
set search_path = ''
as $$
  select count(*)::integer
    from public.account_deletion_dependency_rules r
    join pg_constraint c
      on c.conname=r.constraint_name
     and c.conrelid=to_regclass(format('%I.%I',r.child_schema,r.child_table))
   where r.active=true
     and r.delete_rule <> case c.confdeltype
       when 'a' then 'NO ACTION'
       when 'r' then 'RESTRICT'
       when 'c' then 'CASCADE'
       when 'n' then 'SET NULL'
       when 'd' then 'SET DEFAULT'
       else 'UNKNOWN'
     end;
$$;
revoke all on function private.account_deletion_fk_action_mismatch_count() from public,anon,authenticated,service_role;

do $$
declare
  v_definition text;
  v_old text;
  v_new text;
begin
  v_definition:=pg_get_functiondef('public.prepare_account_deletion_execution(uuid)'::regprocedure);
  v_old:='or v_missing_fk_rules>0 or v_missing_transfers>0 then';
  v_new:='or v_missing_fk_rules>0 or v_missing_transfers>0 or private.account_deletion_fk_action_mismatch_count()>0 then';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'prepare_fk_mismatch_gate_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  v_old:=$old$'missing_fk_rules',v_missing_fk_rules,'missing_ownership_transfers',v_missing_transfers,$old$;
  v_new:=$new$'missing_fk_rules',v_missing_fk_rules,'missing_ownership_transfers',v_missing_transfers,
        'fk_action_mismatches',private.account_deletion_fk_action_mismatch_count(),$new$;
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'prepare_fk_mismatch_metadata_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  execute v_definition;

  v_definition:=pg_get_functiondef('public.evaluate_account_deletion_governance(integer)'::regprocedure);
  v_old:='or v_missing_fk_rules>0 or v_missing_transfers>0 then';
  v_new:='or v_missing_fk_rules>0 or v_missing_transfers>0 or private.account_deletion_fk_action_mismatch_count()>0 then';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'governance_fk_mismatch_gate_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  v_old:=$old$where ao.owner_user_id=v_request.user_id 
          and not exists(select 1 from public.account_deletion_ownership_transfers tr$old$;
  v_new:=$new$where ao.owner_user_id=v_request.user_id and ao.ownership_role='owner' and ao.status='active'
          and not exists(select 1 from public.account_deletion_ownership_transfers tr$new$;
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'governance_agent_active_owner_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  v_old:=$old$'missing_fk_rules',v_missing_fk_rules,'missing_ownership_transfers',v_missing_transfers,$old$;
  v_new:=$new$'missing_fk_rules',v_missing_fk_rules,'missing_ownership_transfers',v_missing_transfers,
               'fk_action_mismatches',private.account_deletion_fk_action_mismatch_count(),$new$;
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'governance_fk_mismatch_metadata_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  execute v_definition;
end;
$$;
