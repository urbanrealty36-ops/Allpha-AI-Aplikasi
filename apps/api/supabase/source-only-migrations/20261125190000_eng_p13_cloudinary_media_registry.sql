-- ENG-P13: canonical media asset registry with authenticated Cloudinary binaries.
-- Forward-only source migration. Keep source-only until ADR-0024 recovery preflight is evidenced.
begin;

alter table public.content_media
  add column if not exists provider_asset_id text,
  add column if not exists provider_public_id text,
  add column if not exists provider_batch_id text,
  add column if not exists provider_callback_verified_at timestamptz,
  add column if not exists processed_at timestamptz,
  add column if not exists processing_version integer not null default 0,
  add column if not exists processing_attempt integer not null default 0,
  add column if not exists derivatives jsonb not null default '[]'::jsonb,
  add column if not exists storage_provider text not null default 'supabase',
  add column if not exists domain text not null default 'content',
  add column if not exists purpose text not null default 'attachment',
  add column if not exists resource_id uuid,
  add column if not exists tenant_id uuid,
  add column if not exists session_id uuid,
  add column if not exists provider_resource_type text,
  add column if not exists provider_delivery_type text,
  add column if not exists provider_version bigint,
  add column if not exists provider_format text,
  add column if not exists provider_width integer,
  add column if not exists provider_height integer,
  add column if not exists provider_duration numeric,
  add column if not exists provider_bytes bigint,
  add column if not exists provider_tags text[] not null default '{}'::text[],
  add column if not exists provider_metadata jsonb not null default '{}'::jsonb,
  add column if not exists upload_expires_at timestamptz,
  add column if not exists upload_completed_at timestamptz,
  add column if not exists upload_idempotency_key text,
  add column if not exists provider_deleted_at timestamptz,
  add column if not exists provider_delete_state text not null default 'not_requested',
  add column if not exists updated_at timestamptz not null default now(),
  add column if not exists scan_receipt jsonb;

alter table public.content_media alter column content_id drop not null;
alter table public.content_lifecycle_jobs alter column content_id drop not null;
alter table public.content_lifecycle_events alter column content_id drop not null;

alter table public.content_lifecycle_jobs
  add column if not exists domain text not null default 'content',
  add column if not exists resource_id uuid,
  add column if not exists purpose text not null default 'attachment',
  add column if not exists tenant_id uuid,
  add column if not exists session_id uuid;

alter table public.content_lifecycle_events
  add column if not exists domain text not null default 'content',
  add column if not exists resource_id uuid,
  add column if not exists purpose text not null default 'attachment',
  add column if not exists tenant_id uuid,
  add column if not exists session_id uuid;

alter table public.content_media drop constraint if exists content_media_bucket_id_check;
alter table public.content_media add constraint content_media_bucket_id_check
  check (bucket_id in ('content-media','cloudinary'));
alter table public.content_media drop constraint if exists content_media_media_type_check;
alter table public.content_media add constraint content_media_media_type_check check (media_type in (
  'image/jpeg','image/png','image/webp','video/mp4','video/webm',
  'audio/mpeg','audio/mp4','audio/aac','audio/ogg','audio/wav','audio/webm',
  'text/vtt','application/x-subrip'
));
alter table public.content_media drop constraint if exists content_media_status_check;
alter table public.content_media add constraint content_media_status_check
  check (status in ('uploading','uploaded','processing','ready','failed','deleting'));
alter table public.content_media drop constraint if exists content_media_scan_status_check;
alter table public.content_media add constraint content_media_scan_status_check
  check (scan_status in ('pending','clean','rejected','unavailable'));
alter table public.content_media drop constraint if exists content_media_size_bytes_check;
alter table public.content_media add constraint content_media_size_bytes_check
  check (size_bytes>0 and size_bytes<=52428800);

alter table public.content_media drop constraint if exists content_media_storage_provider_check;
alter table public.content_media add constraint content_media_storage_provider_check
  check (storage_provider in ('supabase','cloudinary'));
alter table public.content_media drop constraint if exists content_media_storage_provider_bucket_check;
alter table public.content_media add constraint content_media_storage_provider_bucket_check
  check ((storage_provider='supabase' and bucket_id='content-media') or (storage_provider='cloudinary' and bucket_id='cloudinary'));

alter table public.content_media drop constraint if exists content_media_domain_check;
alter table public.content_media add constraint content_media_domain_check
  check (domain in ('content','profile','feed','reels','stories','cinema','live','agent','messaging','community','marketplace','other'));
alter table public.content_media drop constraint if exists content_media_purpose_check;
alter table public.content_media add constraint content_media_purpose_check
  check (purpose in ('attachment','avatar','cover','post_attachment','reel','story','cinema_poster','cinema_asset','live_recording','live_replay','agent_artifact','chat_attachment','community_attachment','marketplace_attachment','other'));
alter table public.content_media drop constraint if exists content_media_domain_resource_check;
alter table public.content_media add constraint content_media_domain_resource_check
  check ((domain='content' and content_id is not null) or (domain<>'content' and content_id is null and resource_id is not null));

alter table public.content_media drop constraint if exists content_media_provider_resource_type_check;
alter table public.content_media add constraint content_media_provider_resource_type_check
  check (provider_resource_type is null or provider_resource_type in ('image','video','raw'));
alter table public.content_media drop constraint if exists content_media_provider_delivery_type_check;
alter table public.content_media add constraint content_media_provider_delivery_type_check
  check (provider_delivery_type is null or provider_delivery_type in ('authenticated','private'));
alter table public.content_media drop constraint if exists content_media_provider_delete_state_check;
alter table public.content_media add constraint content_media_provider_delete_state_check
  check (provider_delete_state in ('not_requested','queued','deleting','deleted','failed'));
alter table public.content_media drop constraint if exists content_media_provider_metadata_check;
alter table public.content_media add constraint content_media_provider_metadata_check
  check (jsonb_typeof(provider_metadata)='object');
alter table public.content_media drop constraint if exists content_media_scan_receipt_check;
alter table public.content_media add constraint content_media_scan_receipt_check
  check (scan_receipt is null or jsonb_typeof(scan_receipt)='object');
alter table public.content_media drop constraint if exists content_media_cloudinary_identity_check;
alter table public.content_media add constraint content_media_cloudinary_identity_check
  check (storage_provider<>'cloudinary' or (
    provider_public_id is not null and provider_resource_type is not null
    and provider_delivery_type='authenticated' and storage_path=provider_public_id
  ));
alter table public.content_media drop constraint if exists content_media_cloudinary_upload_expiry_check;
alter table public.content_media add constraint content_media_cloudinary_upload_expiry_check
  check (storage_provider<>'cloudinary' or status<>'uploading' or upload_expires_at is not null);
alter table public.content_media drop constraint if exists content_media_cloudinary_upload_completed_check;
alter table public.content_media add constraint content_media_cloudinary_upload_completed_check
  check (storage_provider<>'cloudinary' or status='uploading' or upload_completed_at is not null);
alter table public.content_media drop constraint if exists content_media_provider_dimensions_check;
alter table public.content_media add constraint content_media_provider_dimensions_check
  check (
    (provider_width is null or provider_width>0)
    and (provider_height is null or provider_height>0)
    and (provider_duration is null or provider_duration>=0)
    and (provider_bytes is null or provider_bytes>0)
    and (provider_version is null or provider_version>0)
  );

alter table public.content_lifecycle_jobs drop constraint if exists content_lifecycle_jobs_job_type_check;
alter table public.content_lifecycle_jobs add constraint content_lifecycle_jobs_job_type_check
  check (job_type in ('image_process','media_transcode','subtitle_validate','scheduled_publish','retention_purge','provider_cleanup','provider_callback'));
alter table public.content_lifecycle_jobs drop constraint if exists content_lifecycle_jobs_status_check;
alter table public.content_lifecycle_jobs add constraint content_lifecycle_jobs_status_check
  check (status in ('pending','processing','awaiting_provider','succeeded','failed','dead','cancelled'));

create unique index if not exists content_media_owner_domain_idempotency_uq
  on public.content_media(owner_id,domain,upload_idempotency_key) where upload_idempotency_key is not null;
create unique index if not exists content_media_cloudinary_public_id_uq
  on public.content_media(provider_public_id) where storage_provider='cloudinary' and provider_public_id is not null;
create unique index if not exists content_media_cloudinary_asset_id_uq
  on public.content_media(provider_asset_id) where storage_provider='cloudinary' and provider_asset_id is not null;
create index if not exists content_media_domain_resource_idx
  on public.content_media(domain,resource_id,created_at desc);

create or replace function public.content_media_readiness_guard()
returns trigger language plpgsql set search_path=pg_catalog,public
as $function$
begin
  if new.status='ready' then
    if new.processed_at is null or new.scan_status<>'clean' or new.processing_version<1 then
      raise exception 'MEDIA_PROCESSING_NOT_COMPLETE' using errcode='23514';
    end if;
    if new.media_type like 'image/%' and jsonb_array_length(new.derivatives)=0 then
      raise exception 'MEDIA_DERIVATIVES_MISSING' using errcode='23514';
    end if;
    if (new.media_type like 'video/%' or new.media_type like 'audio/%')
       and (new.provider_asset_id is null or new.provider_callback_verified_at is null) then
      raise exception 'MEDIA_PROVIDER_CALLBACK_NOT_VERIFIED' using errcode='23514';
    end if;
    if new.storage_provider='cloudinary' then
      if new.provider_asset_id is null or new.provider_public_id is null
         or new.provider_resource_type is null or new.provider_delivery_type<>'authenticated'
         or new.storage_path<>new.provider_public_id then
        raise exception 'CLOUDINARY_ASSET_IDENTITY_INCOMPLETE' using errcode='23514';
      end if;
      if new.scan_receipt is null or jsonb_typeof(new.scan_receipt)<>'object' then
        raise exception 'MEDIA_SCAN_RECEIPT_MISSING' using errcode='23514';
      end if;
      if (new.media_type like 'image/%' or new.media_type like 'video/%' or new.media_type like 'audio/%')
         and new.provider_callback_verified_at is null then
        raise exception 'MEDIA_PROVIDER_CALLBACK_NOT_VERIFIED' using errcode='23514';
      end if;
    end if;
  end if;
  return new;
end;
$function$;

create or replace function public.enqueue_content_media_processing()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare v_job_type text; v_job_status text; v_attempt integer;
begin
  if new.status='uploaded' and (tg_op='INSERT' or old.status is distinct from new.status) then
    v_attempt:=coalesce(new.processing_attempt,0)+1;
    if new.media_type in ('text/vtt','application/x-subrip') then
      v_job_type:='subtitle_validate'; v_job_status:='pending';
    elsif new.storage_provider='cloudinary' then
      v_job_type:='media_transcode'; v_job_status:='awaiting_provider';
    else
      -- All binary media from the legacy TUS/Supabase ingress is promoted to
      -- Cloudinary by the single transcode dispatcher. No new derivative is
      -- written back to Supabase Storage.
      v_job_type:='media_transcode'; v_job_status:='pending';
    end if;
    insert into public.content_lifecycle_jobs(
      job_type,content_id,media_id,owner_id,domain,resource_id,purpose,tenant_id,session_id,idempotency_key,payload,status
    ) values(
      v_job_type,new.content_id,new.id,new.owner_id,new.domain,new.resource_id,new.purpose,new.tenant_id,new.session_id,
      'media:'||new.id::text||':v'||v_attempt::text,
      jsonb_build_object(
        'bucket_id',new.bucket_id,'storage_path',new.storage_path,'storage_provider',new.storage_provider,
        'media_type',new.media_type,'sha256',new.sha256,'size_bytes',new.size_bytes,
        'processing_attempt',v_attempt,'provider','cloudinary','provider_asset_id',new.provider_asset_id,
        'provider_public_id',new.provider_public_id,'provider_batch_id',new.provider_batch_id,
        'provider_resource_type',new.provider_resource_type,'provider_delivery_type',new.provider_delivery_type,
        'provider_format',new.provider_format,'domain',new.domain,'resource_id',new.resource_id,'purpose',new.purpose
      ),v_job_status
    ) on conflict(idempotency_key) do nothing;
    update public.content_media set status='processing',processing_attempt=v_attempt
    where id=new.id and status='uploaded';
  end if;
  return new;
end;
$function$;

create or replace function public.claim_content_lifecycle_jobs(
  p_worker_id text,p_limit integer,p_lease_seconds integer,p_job_type text
) returns setof public.content_lifecycle_jobs
language plpgsql security definer set search_path=pg_catalog,public
as $function$
begin
  if p_job_type not in ('image_process','media_transcode','subtitle_validate','scheduled_publish','retention_purge','provider_cleanup','provider_callback') then
    return;
  end if;
  return query
  with candidates as (
    select id from public.content_lifecycle_jobs
    where job_type=p_job_type and run_at<=now() and attempts<max_attempts
      and (status='pending' or (status='processing' and lease_expires_at<now()))
    order by run_at,created_at for update skip locked limit greatest(1,least(p_limit,50))
  )
  update public.content_lifecycle_jobs j
  set status='processing',attempts=j.attempts+1,lease_token=gen_random_uuid(),
      lease_expires_at=now()+make_interval(secs=>greatest(15,least(p_lease_seconds,300))),updated_at=now()
  from candidates c where j.id=c.id returning j.*;
end;
$function$;

create or replace function public.enqueue_cloudinary_asset_cleanup()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $function$
begin
  if new.storage_provider<>'cloudinary' and new.status='ready' and old.status is distinct from new.status
     and new.provider_asset_id is not null and new.provider_public_id is not null then
    insert into public.content_lifecycle_jobs(
      job_type,content_id,media_id,owner_id,domain,resource_id,purpose,tenant_id,session_id,idempotency_key,payload
    ) values(
      'provider_cleanup',new.content_id,new.id,new.owner_id,new.domain,new.resource_id,new.purpose,new.tenant_id,new.session_id,
      'provider-cleanup:cloudinary:'||new.provider_asset_id,
      jsonb_build_object('provider','cloudinary','provider_asset_id',new.provider_asset_id,
        'provider_public_id',new.provider_public_id,'resource_type',coalesce(new.provider_resource_type,'video'),
        'delivery_type',coalesce(new.provider_delivery_type,'authenticated'))
    ) on conflict(idempotency_key) do nothing;
  end if;
  return new;
end;
$function$;

create or replace function public.complete_content_subtitle_job(
  p_job_id uuid,p_lease_token uuid,p_media_id uuid,p_scan_receipt jsonb,p_processing_version integer default 1
) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare v_job public.content_lifecycle_jobs%rowtype; v_media public.content_media%rowtype; v_cues integer; v_contract text;
begin
  select * into v_job from public.content_lifecycle_jobs
  where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
    and job_type='subtitle_validate' and media_id=p_media_id for update;
  if not found then return jsonb_build_object('outcome','lease_lost'); end if;
  select * into v_media from public.content_media
  where id=p_media_id and status='processing' and media_type in ('text/vtt','application/x-subrip') for update;
  if not found then return jsonb_build_object('outcome','media_not_processing'); end if;

  v_contract:=coalesce(p_scan_receipt->>'contract_version','');
  if jsonb_typeof(p_scan_receipt)<>'object' or coalesce(p_scan_receipt->>'scanner_id','')=''
     or v_contract not in ('allpha.local-clamav.v1','allpha.document-scan.v1')
     or coalesce(p_scan_receipt->>'sha256','')<>v_media.sha256
     or coalesce(p_scan_receipt->>'engine_version','')='' or coalesce(p_scan_receipt->>'signature_version','')=''
     or jsonb_typeof(p_scan_receipt->'validation')<>'object'
     or coalesce(p_scan_receipt->'validation'->>'sha256','')<>v_media.sha256
     or coalesce(p_scan_receipt->'validation'->>'format','') not in ('webvtt','subrip')
     or coalesce(p_scan_receipt->'validation'->>'cue_count','') !~ '^[1-9][0-9]*$' then
    return jsonb_build_object('outcome','scan_receipt_invalid');
  end if;
  if v_contract='allpha.local-clamav.v1' and p_scan_receipt->>'scanner_id'<>'clamav-local' then
    return jsonb_build_object('outcome','scan_receipt_invalid');
  end if;
  v_cues:=(p_scan_receipt->'validation'->>'cue_count')::integer;
  if v_cues<1 or v_cues>100000 then return jsonb_build_object('outcome','subtitle_cue_count_invalid'); end if;

  update public.content_media set status='ready',scan_status='clean',processed_at=now(),
    processing_version=greatest(1,processing_version+1),derivatives='[]'::jsonb,scan_receipt=p_scan_receipt
  where id=p_media_id returning * into v_media;
  update public.content_lifecycle_jobs set status='succeeded',lease_token=null,lease_expires_at=null,
    completed_at=now(),updated_at=now(),last_error_code=null where id=p_job_id;
  insert into public.content_lifecycle_events(
    event_key,event_type,content_id,media_id,owner_id,domain,resource_id,purpose,tenant_id,session_id,payload
  ) values(
    'subtitle-validated:'||p_media_id::text||':v'||greatest(1,p_processing_version)::text,
    'media.subtitle_validated',v_media.content_id,v_media.id,v_media.owner_id,v_media.domain,v_media.resource_id,
    v_media.purpose,v_media.tenant_id,v_media.session_id,p_scan_receipt
  ) on conflict(event_key) do nothing;
  return jsonb_build_object('outcome','completed','media',to_jsonb(v_media),'cue_count',v_cues);
end;
$function$;

create or replace function public.reserve_cloudinary_media_upload(
  p_media_id uuid,p_content_id uuid,p_owner_id uuid,p_domain text,p_purpose text,p_resource_id uuid,
  p_tenant_id uuid,p_session_id uuid,p_filename text,p_media_type text,p_size_bytes bigint,p_sha256 text,
  p_public_id text,p_resource_type text,p_delivery_type text,p_upload_expires_at timestamptz,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare v_existing public.content_media%rowtype; v_media public.content_media%rowtype; v_expected_resource text; v_authorized boolean;
begin
  if p_media_id is null or p_owner_id is null or not exists(select 1 from auth.users where id=p_owner_id) then
    raise exception 'MEDIA_OWNER_NOT_FOUND' using errcode='23503';
  end if;
  if coalesce(p_domain,'') not in ('content','profile','feed','reels','stories','cinema','agent','messaging','community')
     or coalesce(p_purpose,'') not in ('attachment','avatar','cover','post_attachment','reel','story','cinema_poster','cinema_asset','agent_artifact','chat_attachment','community_attachment') then
    raise exception 'MEDIA_DOMAIN_OR_PURPOSE_INVALID' using errcode='23514';
  end if;
  if (p_domain='content' and (p_content_id is null or p_resource_id is not null))
     or (p_domain<>'content' and (p_content_id is not null or p_resource_id is null)) then
    raise exception 'MEDIA_DOMAIN_RESOURCE_INVALID' using errcode='23514';
  end if;
  if (p_domain='content' and p_purpose not in ('attachment','post_attachment'))
     or (p_domain='profile' and p_purpose not in ('avatar','cover'))
     or (p_domain='feed' and p_purpose<>'post_attachment')
     or (p_domain='reels' and p_purpose<>'reel')
     or (p_domain='stories' and p_purpose<>'story')
     or (p_domain='cinema' and p_purpose not in ('cinema_poster','cinema_asset'))
     or (p_domain='live' and p_purpose not in ('live_recording','live_replay'))
     or (p_domain='agent' and p_purpose<>'agent_artifact')
     or (p_domain='messaging' and p_purpose<>'chat_attachment')
     or (p_domain='community' and p_purpose<>'community_attachment')
     or (p_domain='marketplace' and p_purpose<>'marketplace_attachment')
     or (p_domain='other' and p_purpose<>'other') then
    raise exception 'MEDIA_DOMAIN_PURPOSE_MISMATCH' using errcode='23514';
  end if;

  v_authorized := case
    when p_domain='content' then exists(
      select 1 from public.content_items c
      where c.id=p_content_id and c.owner_id=p_owner_id and c.status in ('draft','failed')
    )
    when p_domain in ('feed','reels','stories') then exists(
      select 1 from public.content_items c
      where c.id=p_resource_id and c.owner_id=p_owner_id and c.status in ('draft','failed')
    )
    when p_domain='profile' then p_resource_id=p_owner_id and exists(
      select 1 from public.profiles p where p.id=p_owner_id
    )
    when p_domain='cinema' and p_purpose='cinema_poster' then exists(
      select 1 from public.cinema_titles t where t.id=p_resource_id and t.owner_id=p_owner_id
    )
    when p_domain='cinema' and p_purpose='cinema_asset' then exists(
      select 1 from public.cinema_episodes e where e.id=p_resource_id and e.owner_id=p_owner_id
    )
    when p_domain='agent' then (
      exists(select 1 from public.ai_agents a where a.id=p_resource_id and a.created_by=p_owner_id)
      or exists(select 1 from public.agent_runtime_tasks t where t.id=p_resource_id and t.owner_user_id=p_owner_id)
    )
    when p_domain='messaging' then exists(
      select 1 from public.conversation_participants cp
      where cp.conversation_id=p_resource_id and cp.user_id=p_owner_id
    )
    when p_domain='community' then exists(
      select 1 from public.community_posts p
      join public.community_memberships m on m.community_id=p.community_id
      where p.id=p_resource_id and p.author_id=p_owner_id
        and m.user_id=p_owner_id and m.status='active'
    )
    else false
  end;
  if not coalesce(v_authorized,false) then
    raise exception 'MEDIA_RESOURCE_ACCESS_DENIED' using errcode='42501';
  end if;
  if p_tenant_id is not null or p_session_id is not null then
    raise exception 'MEDIA_TENANT_SESSION_AUTHORIZATION_NOT_SUPPORTED' using errcode='23514';
  end if;
  v_expected_resource:=case
    when coalesce(p_media_type,'') like 'image/%' then 'image'
    when p_media_type like 'video/%' or p_media_type like 'audio/%' then 'video'
    when p_media_type in ('text/vtt','application/x-subrip') then 'raw'
    else null end;
  if v_expected_resource is null or p_resource_type is distinct from v_expected_resource
     or p_delivery_type is distinct from 'authenticated'
     or p_public_id is distinct from 'allpha/'||p_media_id::text
     or coalesce(p_sha256,'') !~ '^[0-9a-f]{64}$'
     or p_size_bytes is null or p_size_bytes<=0 or p_size_bytes>52428800
     or (p_media_type like 'image/%' and p_size_bytes>10485760)
     or p_upload_expires_at is null or p_upload_expires_at<=now()
     or p_upload_expires_at>now()+interval '15 minutes'
     or coalesce(p_filename,'')='' or char_length(p_filename)>120
     or coalesce(p_idempotency_key,'')='' or char_length(p_idempotency_key)<8 or char_length(p_idempotency_key)>200 then
    raise exception 'MEDIA_UPLOAD_INTENT_INVALID' using errcode='23514';
  end if;
  select * into v_existing from public.content_media
  where owner_id=p_owner_id and domain=p_domain and upload_idempotency_key=p_idempotency_key for update;
  if found then
    if v_existing.id<>p_media_id or v_existing.content_id is distinct from p_content_id
       or v_existing.resource_id is distinct from p_resource_id or v_existing.purpose is distinct from p_purpose
       or v_existing.tenant_id is distinct from p_tenant_id or v_existing.session_id is distinct from p_session_id
       or v_existing.filename is distinct from p_filename or v_existing.sha256<>p_sha256
       or v_existing.media_type<>p_media_type or v_existing.size_bytes<>p_size_bytes
       or v_existing.provider_public_id is distinct from p_public_id
       or v_existing.provider_resource_type is distinct from p_resource_type
       or v_existing.provider_delivery_type is distinct from p_delivery_type then
      raise exception 'MEDIA_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    if v_existing.status='uploading' and v_existing.provider_asset_id is null then
      update public.content_media
      set upload_expires_at=p_upload_expires_at,updated_at=now()
      where id=v_existing.id returning * into v_existing;
    end if;
    return jsonb_build_object('media',to_jsonb(v_existing),'idempotent_replay',true);
  end if;
  insert into public.content_media(
    id,content_id,owner_id,bucket_id,storage_path,filename,media_type,size_bytes,sha256,status,scan_status,
    storage_provider,domain,purpose,resource_id,tenant_id,session_id,provider_public_id,
    provider_resource_type,provider_delivery_type,upload_expires_at,upload_idempotency_key,
    provider_metadata,provider_tags,derivatives
  ) values(
    p_media_id,p_content_id,p_owner_id,'cloudinary',p_public_id,p_filename,p_media_type,p_size_bytes,p_sha256,
    'uploading','pending','cloudinary',p_domain,p_purpose,p_resource_id,p_tenant_id,p_session_id,p_public_id,
    p_resource_type,p_delivery_type,p_upload_expires_at,p_idempotency_key,'{}'::jsonb,'{}'::text[],'[]'::jsonb
  ) returning * into v_media;
  return jsonb_build_object('media',to_jsonb(v_media),'idempotent_replay',false);
end;
$function$;

create or replace function public.complete_cloudinary_content_media_upload(
  p_media_id uuid,p_owner_id uuid,p_asset_id text,p_public_id text,p_resource_type text,p_delivery_type text,
  p_batch_id text,p_version bigint,p_format text,p_width integer,p_height integer,p_duration numeric,
  p_bytes bigint,p_tags text[],p_provider_metadata jsonb
) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare v_media public.content_media%rowtype;
begin
  select * into v_media from public.content_media where id=p_media_id and owner_id=p_owner_id for update;
  if not found then raise exception 'MEDIA_NOT_FOUND' using errcode='P0002'; end if;
  if v_media.storage_provider='cloudinary' and v_media.status in ('processing','ready')
     and v_media.provider_asset_id=p_asset_id and v_media.provider_public_id=p_public_id then
    return jsonb_build_object('media',to_jsonb(v_media),'idempotent_replay',true);
  end if;
  if v_media.storage_provider<>'cloudinary' or v_media.status<>'uploading'
     or v_media.upload_expires_at is null or v_media.upload_expires_at<=now()
     or v_media.provider_public_id is distinct from p_public_id
     or v_media.provider_resource_type is distinct from p_resource_type
     or v_media.provider_delivery_type is distinct from p_delivery_type
     or p_delivery_type is distinct from 'authenticated'
     or coalesce(p_asset_id,'')='' or p_version is null or p_version<=0
     or coalesce(p_format,'')='' or p_bytes is null or p_bytes<>v_media.size_bytes
     or jsonb_typeof(coalesce(p_provider_metadata,'{}'::jsonb))<>'object'
     or (v_media.media_type like 'image/%' and (p_width is null or p_height is null or p_width*p_height>25000000)) then
    raise exception 'CLOUDINARY_UPLOAD_COMPLETION_INVALID' using errcode='23514';
  end if;
  update public.content_media set provider_asset_id=p_asset_id,provider_batch_id=nullif(p_batch_id,''),
    provider_version=p_version,provider_format=lower(p_format),provider_width=p_width,provider_height=p_height,
    provider_duration=p_duration,provider_bytes=p_bytes,provider_tags=coalesce(p_tags,'{}'::text[]),
    provider_metadata=coalesce(p_provider_metadata,'{}'::jsonb),upload_completed_at=now(),status='uploaded'
  where id=p_media_id;
  select * into v_media from public.content_media where id=p_media_id;
  return jsonb_build_object('media',to_jsonb(v_media),'idempotent_replay',false);
end;
$function$;

create or replace function public.complete_cloudinary_content_provider_job(
  p_job_id uuid,p_media_id uuid,p_provider text,p_provider_asset_id text,p_provider_public_id text,
  p_provider_event_id text,p_payload_sha256 text,p_derivatives jsonb,p_scan_status text,p_scan_receipt jsonb
) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare v_media public.content_media%rowtype;
begin
  if jsonb_typeof(p_scan_receipt)<>'object' or coalesce(p_scan_receipt->>'scanner_id','')=''
     or coalesce(p_scan_receipt->>'contract_version','') not in ('allpha.local-clamav.v1','allpha.document-scan.v1')
     or coalesce(p_scan_receipt->>'sha256','')='' then
    return jsonb_build_object('outcome','scan_receipt_invalid');
  end if;
  update public.content_media set scan_receipt=p_scan_receipt
  where id=p_media_id and storage_provider='cloudinary' and status='processing'
    and provider_asset_id=p_provider_asset_id and provider_public_id=p_provider_public_id
    and sha256=p_scan_receipt->>'sha256' returning * into v_media;
  if not found then return jsonb_build_object('outcome','media_identity_mismatch'); end if;
  return public.complete_content_provider_job(
    p_job_id,p_media_id,p_provider,p_provider_asset_id,p_provider_public_id,
    p_provider_event_id,p_payload_sha256,p_derivatives,p_scan_status
  );
end;
$function$;


create or replace function public.request_cloudinary_content_media_delete(
  p_media_id uuid, p_owner_id uuid
) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare
  v_media public.content_media%rowtype;
  v_job public.content_lifecycle_jobs%rowtype;
begin
  select * into v_media
  from public.content_media
  where id=p_media_id and owner_id=p_owner_id
  for update;
  if not found then
    return jsonb_build_object('outcome','media_not_found');
  end if;
  if v_media.storage_provider<>'cloudinary' then
    return jsonb_build_object('outcome','legacy_provider_requires_domain_delete');
  end if;
  if v_media.domain<>'content' or v_media.content_id is null then
    return jsonb_build_object('outcome','domain_delete_not_supported');
  end if;
  if v_media.provider_delete_state='deleted' then
    return jsonb_build_object('outcome','already_deleted','media',to_jsonb(v_media));
  end if;
  if v_media.provider_delete_state in ('queued','deleting') then
    return jsonb_build_object('outcome','already_queued','media',to_jsonb(v_media));
  end if;
  if exists(
    select 1 from public.content_retention_holds h
    where h.content_id=v_media.content_id and h.released_at is null
  ) then
    return jsonb_build_object('outcome','legal_hold');
  end if;
  if exists(
    select 1 from public.content_items c
    where c.id=v_media.content_id and c.status not in ('draft','failed','deleted')
  ) then
    return jsonb_build_object('outcome','media_in_use');
  end if;
  if v_media.provider_public_id is null or v_media.provider_resource_type is null or v_media.provider_resource_type not in ('image','video','raw') then
    return jsonb_build_object('outcome','provider_identity_missing');
  end if;

  update public.content_media
  set status='deleting',provider_delete_state='queued'
  where id=v_media.id
  returning * into v_media;

  insert into public.content_lifecycle_jobs(
    job_type,content_id,media_id,owner_id,idempotency_key,payload,
    domain,resource_id,purpose,tenant_id,session_id
  )
  values(
    'provider_cleanup',v_media.content_id,v_media.id,v_media.owner_id,
    'provider-cleanup:media-delete:'||v_media.id::text,
    jsonb_build_object(
      'provider','cloudinary','action','delete_media','media_id',v_media.id,
      'provider_public_id',v_media.provider_public_id,
      'resource_type',v_media.provider_resource_type
    ),
    v_media.domain,v_media.resource_id,v_media.purpose,v_media.tenant_id,v_media.session_id
  )
  on conflict(idempotency_key) do nothing;

  select * into v_job from public.content_lifecycle_jobs
  where idempotency_key='provider-cleanup:media-delete:'||v_media.id::text
  for update;
  if not found then
    raise exception 'CLOUDINARY_MEDIA_DELETE_JOB_NOT_PERSISTED' using errcode='40001';
  end if;
  if v_job.status in ('dead','failed','cancelled') then
    update public.content_lifecycle_jobs
    set status='pending',attempts=0,run_at=now(),lease_token=null,lease_expires_at=null,
      completed_at=null,last_error_code=null,updated_at=now()
    where id=v_job.id returning * into v_job;
  end if;
  return jsonb_build_object('outcome','queued','media',to_jsonb(v_media),'job_id',v_job.id);
end;
$function$;

create or replace function public.complete_cloudinary_media_delete_job(
  p_job_id uuid,p_lease_token uuid,p_media_id uuid
) returns text
language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare
  v_job public.content_lifecycle_jobs%rowtype;
  v_media public.content_media%rowtype;
begin
  select * into v_job from public.content_lifecycle_jobs
  where id=p_job_id and status='processing' and lease_token=p_lease_token
    and lease_expires_at>now() and job_type='provider_cleanup'
    and media_id=p_media_id and payload->>'action'='delete_media'
  for update;
  if not found then return 'lease_lost'; end if;

  update public.content_media
  set status='deleted',provider_delete_state='deleted',provider_deleted_at=coalesce(provider_deleted_at,now()),updated_at=now()
  where id=p_media_id and owner_id=v_job.owner_id and status='deleting'
    and storage_provider='cloudinary'
    and provider_public_id=v_job.payload->>'provider_public_id'
  returning * into v_media;
  if not found then return 'media_not_deleting'; end if;

  update public.content_lifecycle_jobs
  set status='succeeded',lease_token=null,lease_expires_at=null,
    completed_at=now(),updated_at=now(),last_error_code=null
  where id=p_job_id;
  insert into public.content_lifecycle_events(event_key,event_type,content_id,media_id,owner_id,payload)
  values(
    'media.provider_deleted:'||p_media_id::text,
    'media.provider_deleted',v_media.content_id,v_media.id,v_media.owner_id,
    jsonb_build_object('provider','cloudinary','provider_public_id',v_media.provider_public_id)
  )
  on conflict(event_key) do nothing;
  return 'succeeded';
end;
$function$;

create or replace function public.fail_cloudinary_media_delete_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text
) returns text
language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare
  v_job public.content_lifecycle_jobs%rowtype;
  v_state text;
begin
  select * into v_job from public.content_lifecycle_jobs
  where id=p_job_id and status='processing' and lease_token=p_lease_token
    and lease_expires_at>now() and job_type='provider_cleanup'
    and payload->>'action'='delete_media'
  for update;
  if not found then return 'lease_lost'; end if;

  update public.content_lifecycle_jobs
  set status=case when attempts>=max_attempts then 'dead' else 'pending' end,
    run_at=case when attempts>=max_attempts then run_at
      else now()+make_interval(secs=>least(3600,(power(2,least(attempts,10))::integer)*5)) end,
    lease_token=null,lease_expires_at=null,
    last_error_code=left(coalesce(p_error_code,'CLOUDINARY_DELETE_FAILED'),80),
    updated_at=now()
  where id=p_job_id returning status into v_state;

  if v_state='dead' then
    update public.content_media set provider_delete_state='failed'
    where id=v_job.media_id and status='deleting' and provider_delete_state<>'deleted';
  end if;
  return coalesce(v_state,'lease_lost');
end;
$function$;

create or replace function public.cloudinary_media_schema_readiness()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,public,storage
as $function$
declare
  v_missing_columns text[];
  v_missing_tables text[];
  v_missing_rpcs text[];
begin
  select array_agg(req.table_name||'.'||req.column_name order by req.table_name,req.column_name)
  into v_missing_columns
  from (values
    ('content_media','id'),('content_media','owner_id'),('content_media','content_id'),
    ('content_media','bucket_id'),('content_media','storage_path'),('content_media','filename'),
    ('content_media','media_type'),('content_media','size_bytes'),('content_media','sha256'),
    ('content_media','status'),('content_media','storage_provider'),('content_media','domain'),
    ('content_media','purpose'),('content_media','resource_id'),('content_media','tenant_id'),
    ('content_media','session_id'),('content_media','provider_asset_id'),
    ('content_media','provider_public_id'),('content_media','provider_batch_id'),
    ('content_media','provider_resource_type'),('content_media','provider_delivery_type'),
    ('content_media','provider_version'),('content_media','provider_format'),
    ('content_media','provider_width'),('content_media','provider_height'),
    ('content_media','provider_duration'),('content_media','provider_bytes'),
    ('content_media','provider_tags'),('content_media','provider_metadata'),
    ('content_media','upload_expires_at'),('content_media','upload_completed_at'),
    ('content_media','upload_idempotency_key'),('content_media','provider_deleted_at'),
    ('content_media','provider_delete_state'),('content_media','provider_callback_verified_at'),
    ('content_media','scan_receipt'),('content_media','derivatives'),
    ('content_media','processing_version'),('content_media','processing_attempt'),
    ('content_media','updated_at'),
    ('content_lifecycle_jobs','id'),('content_lifecycle_jobs','job_type'),
    ('content_lifecycle_jobs','status'),('content_lifecycle_jobs','payload'),
    ('content_lifecycle_jobs','media_id'),('content_lifecycle_jobs','lease_token'),
    ('content_lifecycle_jobs','lease_expires_at'),('content_lifecycle_jobs','attempts'),
    ('content_lifecycle_jobs','max_attempts'),('content_lifecycle_jobs','run_at'),
    ('content_lifecycle_jobs','idempotency_key'),('content_lifecycle_jobs','updated_at'),
    ('content_lifecycle_events','event_key'),('content_lifecycle_events','event_type'),
    ('content_lifecycle_events','media_id'),('content_lifecycle_events','owner_id'),
    ('content_lifecycle_events','payload')
  ) as req(table_name,column_name)
  where not exists(
    select 1 from information_schema.columns c
    where c.table_schema='public' and c.table_name=req.table_name and c.column_name=req.column_name
  );

  select array_agg(req.table_name order by req.table_name)
  into v_missing_tables
  from (values
    ('content_media'),('content_lifecycle_jobs'),('content_lifecycle_events'),
    ('content_provider_callbacks')
  ) as req(table_name)
  where to_regclass('public.'||req.table_name) is null;

  select array_agg(req.signature order by req.signature)
  into v_missing_rpcs
  from (values
    ('public.claim_content_lifecycle_jobs(text,integer,integer,text)'),
    ('public.complete_content_subtitle_job(uuid,uuid,uuid,jsonb,integer)'),
    ('public.reserve_cloudinary_media_upload(uuid,uuid,uuid,text,text,uuid,uuid,uuid,text,text,bigint,text,text,text,text,timestamptz,text)'),
    ('public.complete_cloudinary_content_media_upload(uuid,uuid,text,text,text,text,text,bigint,text,integer,integer,numeric,bigint,text[],jsonb)'),
    ('public.complete_cloudinary_content_provider_job(uuid,uuid,text,text,text,text,text,jsonb,text,jsonb)'),
    ('public.request_cloudinary_content_media_delete(uuid,uuid)'),
    ('public.complete_cloudinary_media_delete_job(uuid,uuid,uuid)'),
    ('public.fail_cloudinary_media_delete_job(uuid,uuid,text)')
  ) as req(signature)
  where to_regprocedure(req.signature) is null;

  return jsonb_build_object(
    'contract_version',1,
    'ready',coalesce(cardinality(v_missing_columns),0)=0
      and coalesce(cardinality(v_missing_tables),0)=0
      and coalesce(cardinality(v_missing_rpcs),0)=0,
    'missing_columns',coalesce(to_jsonb(v_missing_columns),'[]'::jsonb),
    'missing_tables',coalesce(to_jsonb(v_missing_tables),'[]'::jsonb),
    'missing_rpcs',coalesce(to_jsonb(v_missing_rpcs),'[]'::jsonb)
  );
end;
$function$;

revoke all on function public.cloudinary_media_schema_readiness() from public,anon,authenticated;
grant execute on function public.cloudinary_media_schema_readiness() to service_role;

update storage.buckets
set allowed_mime_types=array(
  select distinct mime from unnest(coalesce(allowed_mime_types,array[]::text[]) || array['text/vtt','application/x-subrip']) as mime
)
where id='content-media';

revoke all on function public.reserve_cloudinary_media_upload(uuid,uuid,uuid,text,text,uuid,uuid,uuid,text,text,bigint,text,text,text,text,timestamptz,text) from public,anon,authenticated;
revoke all on function public.complete_cloudinary_content_media_upload(uuid,uuid,text,text,text,text,text,bigint,text,integer,integer,numeric,bigint,text[],jsonb) from public,anon,authenticated;
revoke all on function public.complete_cloudinary_content_provider_job(uuid,uuid,text,text,text,text,text,jsonb,text,jsonb) from public,anon,authenticated;

revoke all on function public.request_cloudinary_content_media_delete(uuid,uuid) from public,anon,authenticated;
revoke all on function public.complete_cloudinary_media_delete_job(uuid,uuid,uuid) from public,anon,authenticated;
revoke all on function public.fail_cloudinary_media_delete_job(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.request_cloudinary_content_media_delete(uuid,uuid) to service_role;
grant execute on function public.complete_cloudinary_media_delete_job(uuid,uuid,uuid) to service_role;
grant execute on function public.fail_cloudinary_media_delete_job(uuid,uuid,text) to service_role;
revoke all on function public.complete_content_subtitle_job(uuid,uuid,uuid,jsonb,integer) from public,anon,authenticated;
revoke all on function public.enqueue_content_media_processing() from public,anon,authenticated;
revoke all on function public.claim_content_lifecycle_jobs(text,integer,integer,text) from public,anon,authenticated;
grant execute on function public.reserve_cloudinary_media_upload(uuid,uuid,uuid,text,text,uuid,uuid,uuid,text,text,bigint,text,text,text,text,timestamptz,text) to service_role;
grant execute on function public.complete_cloudinary_content_media_upload(uuid,uuid,text,text,text,text,text,bigint,text,integer,integer,numeric,bigint,text[],jsonb) to service_role;
grant execute on function public.complete_cloudinary_content_provider_job(uuid,uuid,text,text,text,text,text,jsonb,text,jsonb) to service_role;
grant execute on function public.complete_content_subtitle_job(uuid,uuid,uuid,jsonb,integer) to service_role;
grant execute on function public.claim_content_lifecycle_jobs(text,integer,integer,text) to service_role;

comment on table public.content_media is
 'Canonical Allpha media registry. Supabase stores metadata and authorization; storage_provider selects private legacy Supabase or authenticated Cloudinary binary.';
commit;
