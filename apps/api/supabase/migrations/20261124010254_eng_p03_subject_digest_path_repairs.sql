-- ENG-P03: qualify pgcrypto calls for SECURITY DEFINER functions with an empty search_path.
-- The extension is installed in the extensions schema on the canonical Supabase project.

do $$
declare
  v_signature text;
  v_definition text;
  v_patched text;
  v_signatures text[] := array[
    'private.ensure_account_identity_subject()',
    'public.create_account_deletion_request_for_actor(uuid)',
    'public.fail_account_export_job(uuid,uuid,text,integer)'
  ];
begin
  foreach v_signature in array v_signatures loop
    v_definition:=pg_get_functiondef(v_signature::regprocedure);
    if position('digest(' in v_definition)>0
       and position('extensions.digest(' in v_definition)=0 then
      v_patched:=replace(v_definition,'digest(','extensions.digest(');
      if v_patched=v_definition then
        raise exception 'account_lifecycle_digest_qualification_failed:%',v_signature;
      end if;
      execute v_patched;
    end if;
  end loop;
end;
$$;
