-- ENG-P03: FK dependency deletion steps may only target direct auth.users(id) references.
do $$
declare
  v_definition text;
  v_old text := $old$
        if v_rule.fk_column is null then raise exception 'composite_foreign_key_requires_manual_handler'; end if;
        if v_step.action='delete_rows' then
          v_sql:=format('DELETE FROM %I.%I WHERE %I::text = $1',v_rule.child_schema,v_rule.child_table,v_rule.fk_column);
        else
          v_sql:=format('UPDATE %I.%I SET %I=NULL WHERE %I::text = $1',
            v_rule.child_schema,v_rule.child_table,v_rule.fk_column,v_rule.fk_column);
        end if;
        execute v_sql using v_job.user_id::text;
        get diagnostics v_rows=row_count;
$old$;
  v_new text := $new$
        if v_rule.fk_column is null then raise exception 'composite_foreign_key_requires_manual_handler'; end if;
        if v_step.action='delete_rows' then
          if v_rule.delete_rule not in ('RESTRICT','NO ACTION') then
            raise exception 'account_deletion_fk_action_incompatible:%',v_rule.constraint_name using errcode='55000';
          end if;
          if not exists (
            select 1 from pg_constraint c
             where c.conname=v_rule.constraint_name
               and c.conrelid=to_regclass(format('%I.%I',v_rule.child_schema,v_rule.child_table))
               and c.contype='f' and c.confrelid='auth.users'::regclass
               and cardinality(c.conkey)=1 and cardinality(c.confkey)=1
               and (select a.attname from pg_attribute a where a.attrelid=c.conrelid and a.attnum=c.conkey[1])=v_rule.fk_column
               and (select a.attname from pg_attribute a where a.attrelid=c.confrelid and a.attnum=c.confkey[1])='id'
          ) then
            raise exception 'account_deletion_fk_parent_not_auth_user:%',v_rule.constraint_name using errcode='55000';
          end if;
          v_sql:=format('DELETE FROM %I.%I WHERE %I::text = $1',v_rule.child_schema,v_rule.child_table,v_rule.fk_column);
        else
          if v_rule.delete_rule <> 'SET NULL' then
            raise exception 'account_deletion_fk_action_incompatible:%',v_rule.constraint_name using errcode='55000';
          end if;
          if not exists (
            select 1 from pg_constraint c
             where c.conname=v_rule.constraint_name
               and c.conrelid=to_regclass(format('%I.%I',v_rule.child_schema,v_rule.child_table))
               and c.contype='f' and c.confrelid='auth.users'::regclass
               and cardinality(c.conkey)=1 and cardinality(c.confkey)=1
               and (select a.attname from pg_attribute a where a.attrelid=c.conrelid and a.attnum=c.conkey[1])=v_rule.fk_column
               and (select a.attname from pg_attribute a where a.attrelid=c.confrelid and a.attnum=c.confkey[1])='id'
          ) then
            raise exception 'account_deletion_fk_parent_not_auth_user:%',v_rule.constraint_name using errcode='55000';
          end if;
          v_sql:=format('UPDATE %I.%I SET %I=NULL WHERE %I::text = $1',
            v_rule.child_schema,v_rule.child_table,v_rule.fk_column,v_rule.fk_column);
        end if;
        execute v_sql using v_job.user_id::text;
        get diagnostics v_rows=row_count;
$new$;
begin
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  if position(v_new in v_definition)>0 then return; end if;
  if position(v_old in v_definition)=0 then raise exception 'account_deletion_fk_guard_patch_anchor_missing'; end if;
  execute replace(v_definition,v_old,v_new);
end;
$$;