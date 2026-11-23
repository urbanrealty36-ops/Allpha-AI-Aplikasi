-- ENG-P03: durable, lease-fenced progress for account export jobs.
alter table public.account_export_jobs
  add column if not exists progress_percent smallint not null default 0,
  add column if not exists progress_stage text not null default 'queued';

do $progress_constraints$
begin
  if not exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid='public.account_export_jobs'::regclass
       and conname='account_export_jobs_progress_percent_check'
  ) then
    alter table public.account_export_jobs
      add constraint account_export_jobs_progress_percent_check
      check (progress_percent between 0 and 100);
  end if;
  if not exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid='public.account_export_jobs'::regclass
       and conname='account_export_jobs_progress_stage_check'
  ) then
    alter table public.account_export_jobs
      add constraint account_export_jobs_progress_stage_check
      check (progress_stage in ('queued','claimed','snapshot','compress','upload','publishing','completed','failed'));
  end if;
end;
$progress_constraints$;

create or replace function private.sync_account_export_progress_status()
returns trigger
language plpgsql
security definer
set search_path = ''
as $sync_export_progress$
begin
  if new.status='running' and new.lease_token is not null
     and (old.status is distinct from 'running' or old.lease_token is distinct from new.lease_token) then
    new.progress_percent := 5;
    new.progress_stage := 'claimed';
  elsif new.status='succeeded' then
    new.progress_percent := 100;
    new.progress_stage := 'completed';
  elsif new.status='queued' then
    new.progress_percent := 0;
    new.progress_stage := 'queued';
  elsif new.status='failed' then
    new.progress_percent := 0;
    new.progress_stage := 'failed';
  end if;
  return new;
end;
$sync_export_progress$;

drop trigger if exists account_export_jobs_sync_progress on public.account_export_jobs;
create trigger account_export_jobs_sync_progress
before update of status,lease_token on public.account_export_jobs
for each row execute function private.sync_account_export_progress_status();

create or replace function public.update_account_export_job_progress(
  p_job_id uuid,
  p_lease_token uuid,
  p_progress_percent smallint,
  p_progress_stage text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $update_export_progress$
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_job_id is null or p_lease_token is null
     or p_progress_percent is null or p_progress_percent not between 5 and 99
     or p_progress_stage is null
     or p_progress_stage not in ('snapshot','compress','upload','publishing')
     or (p_progress_stage='snapshot' and p_progress_percent not between 6 and 40)
     or (p_progress_stage='compress' and p_progress_percent not between 41 and 65)
     or (p_progress_stage='upload' and p_progress_percent not between 66 and 85)
     or (p_progress_stage='publishing' and p_progress_percent not between 86 and 99) then
    raise exception 'account_export_progress_input_invalid' using errcode='22023';
  end if;

  update public.account_export_jobs j
     set progress_percent=p_progress_percent,
         progress_stage=p_progress_stage,
         updated_at=pg_catalog.clock_timestamp()
   where j.id=p_job_id
     and j.status='running'
     and j.lease_token=p_lease_token
     and j.lease_expires_at > pg_catalog.clock_timestamp()
     and j.progress_percent <= p_progress_percent;
  return found;
end;
$update_export_progress$;

revoke all on function private.sync_account_export_progress_status() from public,anon,authenticated;
revoke all on function public.update_account_export_job_progress(uuid,uuid,smallint,text) from public,anon,authenticated;
grant execute on function public.update_account_export_job_progress(uuid,uuid,smallint,text) to service_role;
