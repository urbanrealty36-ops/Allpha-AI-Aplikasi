-- ENG-P13: secure subtitle media upload and validation using the canonical content lifecycle queue.
begin;

alter table public.content_media drop constraint if exists content_media_media_type_check;
alter table public.content_media add constraint content_media_media_type_check check (media_type in (
 'image/jpeg','image/png','image/webp','video/mp4','video/webm',
 'audio/mpeg','audio/mp4','audio/aac','audio/ogg','audio/wav','audio/webm',
 'text/vtt','application/x-subrip'
));

update storage.buckets
set allowed_mime_types = array(
 select distinct mime from unnest(coalesce(allowed_mime_types, array[]::text[]) || array['text/vtt','application/x-subrip']) as mime
)
where id='content-media';

alter table public.content_lifecycle_jobs drop constraint if exists content_lifecycle_jobs_job_type_check;
alter table public.content_lifecycle_jobs add constraint content_lifecycle_jobs_job_type_check
 check (job_type in ('image_process','media_transcode','subtitle_validate','scheduled_publish','retention_purge','provider_cleanup','provider_callback'));

create or replace function public.enqueue_content_media_processing()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare v_job_type text; v_attempt integer;
begin
 if new.status='uploaded' and (tg_op='INSERT' or old.status is distinct from new.status) then
  v_attempt:=coalesce(new.processing_attempt,0)+1;
  v_job_type:=case
   when new.media_type like 'image/%' then 'image_process'
   when new.media_type in ('text/vtt','application/x-subrip') then 'subtitle_validate'
   else 'media_transcode'
  end;
  insert into public.content_lifecycle_jobs(job_type,content_id,media_id,owner_id,idempotency_key,payload)
  values(v_job_type,new.content_id,new.id,new.owner_id,'media:'||new.id::text||':v'||v_attempt::text,
   jsonb_build_object('bucket_id',new.bucket_id,'storage_path',new.storage_path,'media_type',new.media_type,
    'sha256',new.sha256,'size_bytes',new.size_bytes,'processing_attempt',v_attempt))
  on conflict(idempotency_key) do nothing;
  update public.content_media set status='processing',processing_attempt=v_attempt where id=new.id and status='uploaded';
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
 update public.content_lifecycle_jobs j set status='processing',attempts=j.attempts+1,
  lease_token=gen_random_uuid(),lease_expires_at=now()+make_interval(secs=>greatest(15,least(p_lease_seconds,300))),
  updated_at=now()
 from candidates c where j.id=c.id returning j.*;
end;
$function$;

create or replace function public.complete_content_subtitle_job(
 p_job_id uuid,p_lease_token uuid,p_media_id uuid,p_scan_receipt jsonb,p_processing_version integer default 1
) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $function$
declare v_job public.content_lifecycle_jobs%rowtype; v_media public.content_media%rowtype; v_cues integer;
begin
 select * into v_job from public.content_lifecycle_jobs
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
  and job_type='subtitle_validate' and media_id=p_media_id for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 select * into v_media from public.content_media
 where id=p_media_id and status='processing' and media_type in ('text/vtt','application/x-subrip') for update;
 if not found then return jsonb_build_object('outcome','media_not_processing'); end if;
 if jsonb_typeof(p_scan_receipt)<>'object'
    or coalesce(p_scan_receipt->>'scanner_id','')<>'clamav-local'
    or coalesce(p_scan_receipt->>'contract_version','')<>'allpha.local-clamav.v1'
    or coalesce(p_scan_receipt->>'sha256','')<>v_media.sha256
    or coalesce(p_scan_receipt->>'engine_version','')=''
    or coalesce(p_scan_receipt->>'signature_version','')=''
    or jsonb_typeof(p_scan_receipt->'validation')<>'object'
    or coalesce(p_scan_receipt->'validation'->>'sha256','')<>v_media.sha256
    or coalesce(p_scan_receipt->'validation'->>'format','') not in ('webvtt','subrip')
    or coalesce(p_scan_receipt->'validation'->>'cue_count','') !~ '^[1-9][0-9]*$' then
  return jsonb_build_object('outcome','scan_receipt_invalid');
 end if;
 v_cues:=(p_scan_receipt->'validation'->>'cue_count')::integer;
 if v_cues<1 or v_cues>100000 then return jsonb_build_object('outcome','subtitle_cue_count_invalid'); end if;
 update public.content_media set status='ready',scan_status='clean',processed_at=now(),
  processing_version=greatest(1,processing_version+1),derivatives='[]'::jsonb
 where id=p_media_id returning * into v_media;
 update public.content_lifecycle_jobs set status='succeeded',lease_token=null,lease_expires_at=null,
  completed_at=now(),updated_at=now(),last_error_code=null where id=p_job_id;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,media_id,owner_id,payload)
 values('subtitle-validated:'||p_media_id::text||':v1','media.subtitle_validated',v_media.content_id,
  v_media.id,v_media.owner_id,p_scan_receipt)
 on conflict(event_key) do nothing;
 return jsonb_build_object('outcome','completed','media',to_jsonb(v_media),'cue_count',v_cues);
end;
$function$;

revoke all on function public.enqueue_content_media_processing() from public,anon,authenticated;
revoke all on function public.claim_content_lifecycle_jobs(text,integer,integer,text) from public,anon,authenticated;
revoke all on function public.complete_content_subtitle_job(uuid,uuid,uuid,jsonb,integer) from public,anon,authenticated;
grant execute on function public.claim_content_lifecycle_jobs(text,integer,integer,text) to service_role;
grant execute on function public.complete_content_subtitle_job(uuid,uuid,uuid,jsonb,integer) to service_role;

comment on function public.complete_content_subtitle_job(uuid,uuid,uuid,jsonb,integer) is
 'Marks VTT/SRT media ready only after a clean pinned ClamAV receipt and structural subtitle validation.';
commit;
