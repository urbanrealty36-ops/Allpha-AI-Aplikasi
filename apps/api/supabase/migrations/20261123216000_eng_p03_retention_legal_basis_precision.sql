update public.account_data_retention_policies
set legal_basis = 'UU No. 27/2022 Pasal 42-44: end processing/delete/destroy when retention ends, purpose is achieved or subject requests, subject to applicable law and legal proceedings. 0 days is Allpha''s operational deletion-on-request period, not a statutory numeric term. Active legal holds and applicable statutory records override; specified company/tax documents remain preserved where applicable under UU 8/1997 Pasal 11 and UU KUP Pasal 28 ayat (11) (10 years).',
    updated_at=clock_timestamp()
where policy_version='owner-directive-2026-11-23-v1'
  and data_class in ('owner_private','agent_operational','tenant_shared','published_knowledge','session_scoped','public_catalog');
do $$
begin
 if (select count(*) from public.account_data_retention_policies
     where policy_version='owner-directive-2026-11-23-v1'
       and legal_basis like '%Pasal 42-44%') <> 6 then
   raise exception 'ENG-P03 expected six corrected retention legal bases';
 end if;
end $$;
