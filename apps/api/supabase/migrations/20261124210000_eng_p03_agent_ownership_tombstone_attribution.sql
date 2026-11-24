-- ENG-P03: preserve Agent ownership history while transferring only verified active owners.
-- Also create identity subjects for every newly registered Auth user before any subject-backed FK writes.

create or replace function private.ensure_account_identity_subject_from_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare v_subject_ref text;
begin
  v_subject_ref := encode(extensions.digest(new.id::text,'sha256'),'hex');
  insert into private.account_identity_subjects(subject_id,subject_ref,status)
  values(new.id,v_subject_ref,'active')
  on conflict(subject_id) do nothing;

  if not exists (
    select 1 from private.account_identity_subjects s
     where s.subject_id=new.id and s.subject_ref=v_subject_ref and s.status='active'
  ) then
    raise exception 'account_identity_subject_not_active' using errcode='23514';
  end if;
  return new;
end;
$$;
revoke all on function private.ensure_account_identity_subject_from_auth_user() from public,anon,authenticated,service_role;

drop trigger if exists on_auth_user_created_account_identity_subject on auth.users;
create trigger on_auth_user_created_account_identity_subject
after insert on auth.users
for each row execute function private.ensure_account_identity_subject_from_auth_user();

insert into private.account_identity_subjects(subject_id,subject_ref,status)
select u.id,encode(extensions.digest(u.id::text,'sha256'),'hex'),'active'
from auth.users u
on conflict(subject_id) do nothing;

do $$
begin
  if exists (
    select 1 from auth.users u
    left join private.account_identity_subjects s on s.subject_id=u.id
    where s.subject_id is null or s.status<>'active'
      or s.subject_ref<>encode(extensions.digest(u.id::text,'sha256'),'hex')
  ) then
    raise exception 'account_identity_subject_backfill_incomplete';
  end if;
end;
$$;

alter table public.agent_ownerships
  add column if not exists owner_subject_ref text;

update public.agent_ownerships ao
   set owner_subject_ref=s.subject_ref
  from private.account_identity_subjects s
 where s.subject_id=ao.owner_user_id
   and ao.owner_subject_ref is distinct from s.subject_ref;

do $$
begin
  if exists(select 1 from public.agent_ownerships
    where owner_user_id is not null and owner_subject_ref is null) then
    raise exception 'agent_ownership_subject_reference_backfill_incomplete';
  end if;
end;
$$;

alter table public.agent_ownerships
  drop constraint if exists agent_ownerships_owner_subject_ref_fkey;
alter table public.agent_ownerships
  add constraint agent_ownerships_owner_subject_ref_fkey
  foreign key (owner_subject_ref)
  references private.account_identity_subjects(subject_ref)
  on delete restrict not valid;
alter table public.agent_ownerships
  validate constraint agent_ownerships_owner_subject_ref_fkey;

create or replace function private.sync_agent_ownership_subject_reference()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare v_subject_ref text;
begin
  if new.owner_user_id is not null then
    select s.subject_ref into v_subject_ref
      from private.account_identity_subjects s
     where s.subject_id=new.owner_user_id and s.status='active';
    if v_subject_ref is null then
      raise exception 'agent_ownership_identity_subject_unavailable' using errcode='23514';
    end if;
    new.owner_subject_ref:=v_subject_ref;
  elsif tg_op='UPDATE' then
    new.owner_subject_ref:=coalesce(new.owner_subject_ref,old.owner_subject_ref);
  end if;
  return new;
end;
$$;
revoke all on function private.sync_agent_ownership_subject_reference() from public,anon,authenticated,service_role;

drop trigger if exists agent_ownership_subject_reference_sync on public.agent_ownerships;
create trigger agent_ownership_subject_reference_sync
before insert or update of owner_user_id on public.agent_ownerships
for each row execute function private.sync_agent_ownership_subject_reference();

alter table public.agent_ownerships alter column owner_user_id drop not null;
alter table public.agent_ownerships
  drop constraint if exists agent_ownerships_owner_user_id_fkey;
alter table public.agent_ownerships
  add constraint agent_ownerships_owner_user_id_fkey
  foreign key (owner_user_id) references auth.users(id)
  on delete set null not valid;
alter table public.agent_ownerships
  validate constraint agent_ownerships_owner_user_id_fkey;

update public.account_deletion_dependency_rules
   set delete_rule='SET NULL',
       resolution_action='transfer_owner',
       reason='Transfer only active owner-role rows to a verified successor; preserve historical attribution in owner_subject_ref and null remaining Auth references'
 where child_schema='public' and child_table='agent_ownerships'
   and constraint_name='agent_ownerships_owner_user_id_fkey' and active=true;

do $$
declare
  v_definition text;
  v_old text;
  v_new text;
begin
  -- Authenticated owner transfer must target an active owner-role row.
  v_definition:=pg_get_functiondef('public.set_my_account_deletion_ownership_transfer(uuid,text,uuid,uuid)'::regprocedure);
  v_old:='where ao.agent_id=p_resource_id and ao.owner_user_id=v_actor';
  v_new:=v_old||' and ao.ownership_role=''owner'' and ao.status=''active''';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_rpc_validation_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  v_definition:=replace(v_definition,'encode(digest(u.id::text,','encode(extensions.digest(u.id::text,');
  execute v_definition;

  -- Governance requires a transfer only for an active owner-role row.
  v_definition:=pg_get_functiondef('public.prepare_account_deletion_execution(uuid)'::regprocedure);
  v_old:='where ao.owner_user_id=v_request.user_id';
  v_new:=v_old||' and ao.ownership_role=''owner'' and ao.status=''active''';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_prepare_validation_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  execute v_definition;

  -- The executor moves only active ownership rows. It then verifies that no active owner
  -- reference remains before nulling residual historical/delegated references.
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  v_old:='and t.status=''requested'' and ao.owner_user_id=v_job.user_id';
  v_new:=v_old||' and ao.ownership_role=''owner'' and ao.status=''active''';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_executor_update_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;

  v_old:='where ao.agent_id=t.resource_id and ao.owner_user_id=t.successor_user_id';
  v_new:=v_old||' and ao.ownership_role=''owner'' and ao.status=''active''';
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_executor_fence_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;

  v_old:=$old$
        update public.account_deletion_ownership_transfers t
           set status='applied',applied_at=clock_timestamp()
$new$;
  v_new:=$new$
        if v_rule.child_table='agent_ownerships' and v_rule.fk_column='owner_user_id' then
          if exists(select 1 from public.agent_ownerships ao
            where ao.owner_user_id=v_job.user_id
              and ao.ownership_role='owner' and ao.status='active') then
            raise exception 'account_deletion_agent_transfer_incomplete' using errcode='55000';
          end if;
          update public.agent_ownerships ao
             set owner_user_id=null
           where ao.owner_user_id=v_job.user_id;
        end if;
        update public.account_deletion_ownership_transfers t
           set status='applied',applied_at=clock_timestamp()
$new$;
  if position(v_new in v_definition)=0 then
    if position(v_old in v_definition)=0 then raise exception 'agent_transfer_executor_history_anchor_missing'; end if;
    v_definition:=replace(v_definition,v_old,v_new);
  end if;
  execute v_definition;
end;
$$;

-- Verify every retained Agent ownership reference has a private subject reference.
do $$
begin
  if exists(select 1 from public.agent_ownerships ao
    left join private.account_identity_subjects s on s.subject_ref=ao.owner_subject_ref
    where ao.owner_subject_ref is null or s.subject_ref is null) then
    raise exception 'agent_ownership_subject_reference_integrity_failed';
  end if;
end;
$$;
