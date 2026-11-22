-- SOURCE ONLY — WP-11 Cinema screenplay generation integration.
-- Reuses the canonical Generation Job queue, Model Router, credit ledger,
-- moderation, retry/cancellation and private artifact bucket. This table is
-- only an owner-scoped link/projection; it is not a second queue or ledger.
begin;

do $$
begin
  if to_regclass('public.cinema_titles') is null
     or to_regclass('public.generation_jobs') is null
     or to_regclass('public.cinema_collaborators') is null then
    raise exception 'WP11_CINEMA_GENERATION_PREREQUISITES_MISSING';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='cinema_titles'
      and column_name='production_document'
  ) then
    raise exception 'WP11_CINEMA_PRODUCTION_DOCUMENT_PREREQUISITE_MISSING';
  end if;
end $$;

create table if not exists public.cinema_generation_job_links (
  id uuid primary key default gen_random_uuid(),
  generation_job_id uuid not null unique
    references public.generation_jobs(id) on delete restrict,
  title_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  requester_user_id uuid not null references auth.users(id) on delete cascade,
  target_section text not null check (target_section='screenplay_draft'),
  expected_title_version integer not null check (expected_title_version>=1),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  created_at timestamptz not null default now(),
  applied_at timestamptz,
  applied_version integer,
  foreign key (title_id,owner_id)
    references public.cinema_titles(id,owner_id) on delete cascade,
  unique(requester_user_id,idempotency_key),
  check ((applied_at is null)=(applied_version is null))
);

create index if not exists cinema_generation_job_links_title_created_idx
  on public.cinema_generation_job_links(title_id,created_at desc);
create index if not exists cinema_generation_job_links_requester_created_idx
  on public.cinema_generation_job_links(requester_user_id,created_at desc);

alter table public.cinema_generation_job_links enable row level security;
revoke all on public.cinema_generation_job_links from public,anon,authenticated;
grant select,insert,update on public.cinema_generation_job_links to service_role;

create or replace function public.cinema_apply_generation_job_output(
  p_generation_job_id uuid,
  p_owner_id uuid,
  p_requester_user_id uuid,
  p_expected_version integer,
  p_output_text text
) returns jsonb
language plpgsql security definer set search_path=''
as $$
declare
  v_link public.cinema_generation_job_links%rowtype;
  v_job public.generation_jobs%rowtype;
  v_title public.cinema_titles%rowtype;
  v_new_version integer;
begin
  if p_generation_job_id is null or p_owner_id is null or p_requester_user_id is null
     or p_expected_version is null or p_expected_version<1
     or coalesce(length(btrim(p_output_text)),0)=0
     or octet_length(p_output_text)>60000 then
    raise exception 'CINEMA_GENERATION_APPLY_INPUT_INVALID' using errcode='22023';
  end if;

  select * into v_link
  from public.cinema_generation_job_links
  where generation_job_id=p_generation_job_id
    and owner_id=p_owner_id and requester_user_id=p_requester_user_id
  for update;
  if not found then
    raise exception 'CINEMA_GENERATION_LINK_NOT_FOUND' using errcode='42501';
  end if;
  if v_link.applied_at is not null then
    return jsonb_build_object(
      'outcome','replayed','generation_job_id',p_generation_job_id,
      'title_id',v_link.title_id,'title_version',v_link.applied_version
    );
  end if;
  if v_link.target_section<>'screenplay_draft'
     or v_link.expected_title_version<>p_expected_version then
    raise exception 'CINEMA_GENERATION_TARGET_OR_VERSION_CONFLICT' using errcode='40001';
  end if;

  if p_requester_user_id<>p_owner_id and not exists (
    select 1 from public.cinema_collaborators c
    where c.title_id=v_link.title_id and c.owner_id=p_owner_id
      and c.collaborator_user_id=p_requester_user_id and c.status='active'
      and (c.expires_at is null or c.expires_at>now())
      and 'edit_metadata'=any(c.permissions)
  ) then
    raise exception 'CINEMA_COLLABORATOR_PERMISSION_REVOKED' using errcode='42501';
  end if;

  select * into v_job
  from public.generation_jobs
  where id=p_generation_job_id and owner_user_id=p_requester_user_id
  for share;
  if not found or v_job.status<>'succeeded' or v_job.moderation_status<>'approved'
     or v_job.artifact_bucket<>'generation-artifacts' or v_job.artifact_path is null
     or v_job.artifact_deletion_requested_at is not null or v_job.artifact_deleted_at is not null then
    raise exception 'CINEMA_GENERATION_ARTIFACT_NOT_READY' using errcode='55000';
  end if;

  select * into v_title
  from public.cinema_titles
  where id=v_link.title_id and owner_id=p_owner_id
  for update;
  if not found or v_title.status not in ('draft','rejected')
     or v_title.version<>p_expected_version then
    raise exception 'CINEMA_PRODUCTION_VERSION_CONFLICT' using errcode='40001';
  end if;
  if jsonb_typeof(v_title.production_document)<>'object'
     or jsonb_typeof(v_title.production_document->'screenplay')<>'object' then
    raise exception 'CINEMA_PRODUCTION_DOCUMENT_INVALID' using errcode='23514';
  end if;

  update public.cinema_titles
  set production_document=jsonb_set(
        v_title.production_document,'{screenplay,draft}',to_jsonb(p_output_text),true
      ),
      version=version+1,updated_at=now()
  where id=v_link.title_id and owner_id=p_owner_id and version=p_expected_version
  returning version into v_new_version;
  if not found then
    raise exception 'CINEMA_PRODUCTION_VERSION_CONFLICT' using errcode='40001';
  end if;

  update public.cinema_generation_job_links
  set applied_at=now(),applied_version=v_new_version
  where id=v_link.id and applied_at is null;

  return jsonb_build_object(
    'outcome','applied','generation_job_id',p_generation_job_id,
    'title_id',v_link.title_id,'title_version',v_new_version,
    'target_section',v_link.target_section
  );
end;
$$;

revoke all on function public.cinema_apply_generation_job_output(uuid,uuid,uuid,integer,text)
  from public,anon,authenticated;
grant execute on function public.cinema_apply_generation_job_output(uuid,uuid,uuid,integer,text)
  to service_role;

create or replace function public.cinema_generation_schema_readiness()
returns jsonb
language plpgsql security definer set search_path=''
as $
declare
  v_missing text[] := array[]::text[];
begin
  if to_regclass('public.generation_jobs') is null then
    v_missing := array_append(v_missing,'generation_jobs');
  end if;
  if to_regclass('public.cinema_titles') is null then
    v_missing := array_append(v_missing,'cinema_titles');
  end if;
  if to_regclass('public.cinema_collaborators') is null then
    v_missing := array_append(v_missing,'cinema_collaborators');
  end if;
  if to_regclass('public.cinema_generation_job_links') is null then
    v_missing := array_append(v_missing,'cinema_generation_job_links');
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='cinema_titles'
      and column_name='production_document'
  ) then
    v_missing := array_append(v_missing,'cinema_titles.production_document');
  end if;
  if to_regprocedure('public.cinema_apply_generation_job_output(uuid,uuid,uuid,integer,text)') is null then
    v_missing := array_append(v_missing,'cinema_apply_generation_job_output');
  end if;
  return jsonb_build_object('ready',cardinality(v_missing)=0,'missing',v_missing);
end;
$;

revoke all on function public.cinema_generation_schema_readiness()
  from public,anon,authenticated;
grant execute on function public.cinema_generation_schema_readiness()
  to service_role;

commit;
