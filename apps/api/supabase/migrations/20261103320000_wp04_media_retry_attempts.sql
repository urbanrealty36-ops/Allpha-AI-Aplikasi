alter table public.content_media add column if not exists processing_attempt integer not null default 0 check (processing_attempt>=0);
create or replace function public.enqueue_content_media_processing()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job_type text;v_attempt integer;
begin
 if new.status='uploaded' and (tg_op='INSERT' or old.status is distinct from new.status) then
  v_attempt:=coalesce(new.processing_attempt,0)+1;
  v_job_type:=case when new.media_type like 'image/%' then 'image_process' else 'media_transcode' end;
  insert into public.content_lifecycle_jobs(job_type,content_id,media_id,owner_id,idempotency_key,payload)
  values(v_job_type,new.content_id,new.id,new.owner_id,'media:'||new.id::text||':v'||v_attempt::text,
   jsonb_build_object('bucket_id',new.bucket_id,'storage_path',new.storage_path,'media_type',new.media_type,'sha256',new.sha256,'size_bytes',new.size_bytes,'processing_attempt',v_attempt))
  on conflict(idempotency_key) do nothing;
  update public.content_media set status='processing',processing_attempt=v_attempt where id=new.id and status='uploaded';
 end if;
 return new;
end;
$$;
revoke all on function public.enqueue_content_media_processing() from public,anon,authenticated;
