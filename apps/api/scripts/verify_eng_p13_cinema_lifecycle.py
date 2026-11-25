"""ENG-P13 disposable PostgreSQL 17 verification for Cinema assets, playback and subtitles."""
from __future__ import annotations

from pathlib import Path
import hashlib
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
ASSET_MIGRATION = ROOT / "apps/api/supabase/source-only-migrations/20261120100000_wp11_cinema_production_workspace.sql"
PLAYBACK_MIGRATION = ROOT / "apps/api/supabase/migrations/20261125010000_eng_p13_cinema_playback_watchlist_lifecycle.sql"
SUBTITLE_MIGRATION = ROOT / "apps/api/supabase/migrations/20261125020000_eng_p13_subtitle_media_processing.sql"
CLOUDINARY_MEDIA_MIGRATION = ROOT / "apps/api/supabase/source-only-migrations/20261125190000_eng_p13_cloudinary_media_registry.sql"
NAME = "allpha-p13-cinema-" + uuid.uuid4().hex[:8]
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "99999999-9999-4999-8999-999999999999"
TITLE = "22222222-2222-4222-8222-222222222222"
EPISODE = "33333333-3333-4333-8333-333333333333"
VIDEO_MEDIA = "44444444-4444-4444-8444-444444444444"
IMAGE_MEDIA = "55555555-5555-4555-8555-555555555555"
ENTITLEMENT = "66666666-6666-4666-8666-666666666666"
SESSION = "77777777-7777-4777-8777-777777777777"
HEARTBEAT_EVENT = "88888888-8888-4888-8888-888888888888"
FINISH_EVENT = "99999999-9999-4999-8999-999999999998"
SUBTITLE_MEDIA = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DELETE_CONTENT = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
CLOUDINARY_DELETE_MEDIA = "ffffffff-ffff-4fff-8fff-ffffffffffff"
LEGACY_DELETE_MEDIA = "abababab-abab-4bab-8bab-abababababab"
CLOUDINARY_DELETE_SHA = "f" * 64
UNAUTHORIZED_PROFILE_MEDIA = "12121212-1212-4121-8121-121212121212"
INVALID_SUBTITLE_MEDIA = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CLOUDINARY_IMAGE_MEDIA = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
CLOUDINARY_SUBTITLE_MEDIA = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
CLOUDINARY_IMAGE_SHA = "d" * 64
CLOUDINARY_SUBTITLE_SHA = "e" * 64
SUBTITLE_BYTES = b"WEBVTT" + bytes([10,10]) + b"00:00:00.000 --> 00:00:02.000" + bytes([10]) + b"Hello" + bytes([10])
SUBTITLE_SHA = hashlib.sha256(SUBTITLE_BYTES).hexdigest()
TOKEN_HASH = "a" * 64


def run(args: list[str], sql: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, input=sql, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stdout + "\n" + result.stderr)
    return result


def psql(sql: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = run(
        ["docker", "exec", "-i", NAME, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        sql,
        check=False,
    )
    if check and result.returncode:
        logs = run(["docker", "logs", NAME], check=False)
        raise RuntimeError(result.stdout + "\n" + result.stderr + "\nPostgreSQL logs:\n" + logs.stdout + logs.stderr)
    return result


def main() -> None:
    for migration in (ASSET_MIGRATION, PLAYBACK_MIGRATION, SUBTITLE_MIGRATION, CLOUDINARY_MEDIA_MIGRATION):
        if not migration.is_file():
            raise RuntimeError(f"Missing Cinema migration: {migration}")
    run(["docker", "run", "-d", "--rm", "--name", NAME, "-e", "POSTGRES_PASSWORD=ci-only", "postgres:17-alpine"])
    try:
        ready = False
        streak = 0
        for _ in range(90):
            probe = run(["docker", "exec", NAME, "psql", "-X", "-A", "-t", "-U", "postgres", "-d", "postgres", "-c", "select 1"], check=False)
            if probe.returncode == 0:
                streak += 1
                if streak >= 3:
                    ready = True
                    break
            else:
                streak = 0
            time.sleep(1)
        if not ready:
            raise RuntimeError("PostgreSQL 17 did not reach stable SQL readiness")

        psql("""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create schema storage;
create schema extensions;
create extension if not exists pgcrypto with schema extensions;
create function auth.uid() returns uuid language sql stable as $uid$
 select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$uid$;
create table auth.users(id uuid primary key);
create table public.content_items(
 id uuid primary key, owner_id uuid not null references auth.users(id), status text not null default 'draft'
);
create table public.profiles(id uuid primary key references auth.users(id));
create table public.content_retention_holds(
 id uuid primary key default gen_random_uuid(), content_id uuid not null, released_at timestamptz
);
create table public.ai_agents(id uuid primary key, created_by uuid not null);
create table public.agent_runtime_tasks(id uuid primary key, owner_user_id uuid not null);
create table public.conversations(id uuid primary key);
create table public.conversation_participants(conversation_id uuid not null, user_id uuid);
create table public.community_posts(id uuid primary key, community_id uuid not null, author_id uuid not null);
create table public.community_memberships(community_id uuid not null, user_id uuid not null, status text not null);
create table public.cinema_titles(
 id uuid primary key, owner_id uuid not null references auth.users(id) on delete cascade,
 title text not null, status text not null default 'draft', moderation_status text not null default 'pending',
 rights_status text not null default 'pending', version integer not null default 1,
 credits jsonb not null default '[]'::jsonb,
 unique(id,owner_id)
);
create table public.cinema_episodes(
 id uuid primary key, title_id uuid not null references public.cinema_titles(id) on delete cascade,
 owner_id uuid not null references auth.users(id), episode_number integer not null, title text not null,
 unique(title_id,episode_number)
);
create table public.playback_entitlements(
 id uuid primary key, owner_user_id uuid not null references auth.users(id) on delete cascade,
 status text not null default 'active'
);
create table public.content_media(
 id uuid primary key, content_id uuid not null, owner_id uuid not null references auth.users(id),
 bucket_id text not null, storage_path text not null, filename text not null,
 media_type text not null constraint content_media_media_type_check check(media_type in (
  'image/jpeg','image/png','image/webp','video/mp4','video/webm',
  'audio/mpeg','audio/mp4','audio/aac','audio/ogg','audio/wav','audio/webm'
 )),
 size_bytes bigint not null check(size_bytes>0), sha256 text not null,
 status text not null default 'uploaded' check(status in ('uploaded','processing','ready','failed')),
 scan_status text not null default 'pending' check(scan_status in ('pending','clean','failed')),
 processed_at timestamptz, processing_attempt integer not null default 0,
 processing_version integer not null default 0, derivatives jsonb not null default '[]'::jsonb,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.content_lifecycle_jobs(
 id uuid primary key default gen_random_uuid(),
 job_type text not null constraint content_lifecycle_jobs_job_type_check
  check(job_type in ('image_process','media_transcode','scheduled_publish','retention_purge','provider_cleanup','provider_callback')),
 content_id uuid not null, media_id uuid references public.content_media(id) on delete cascade,
 owner_id uuid not null references auth.users(id), idempotency_key text not null unique,
 payload jsonb not null default '{}'::jsonb, run_at timestamptz not null default now(),
 attempts integer not null default 0, max_attempts integer not null default 5,
 status text not null default 'pending' check(status in ('pending','processing','succeeded','failed','cancelled')),
 lease_token uuid, lease_expires_at timestamptz, created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(), completed_at timestamptz, last_error_code text
);
create table public.content_lifecycle_events(
 id uuid primary key default gen_random_uuid(), event_key text not null unique,
 event_type text not null, content_id uuid not null, media_id uuid references public.content_media(id),
 owner_id uuid not null references auth.users(id), payload jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now()
);
create table storage.buckets(id text primary key, allowed_mime_types text[] not null default '{}');
insert into storage.buckets(id,allowed_mime_types) values('content-media',array['image/jpeg','image/png','image/webp','video/mp4','video/webm']);
grant usage on schema public,auth,storage,extensions to anon,authenticated,service_role;
""")

        # Validate the source-only Creator Asset Library DDL in disposable PostgreSQL only.
        psql(ASSET_MIGRATION.read_text(encoding="utf-8"))
        psql(PLAYBACK_MIGRATION.read_text(encoding="utf-8"))
        psql(SUBTITLE_MIGRATION.read_text(encoding="utf-8"))
        psql(CLOUDINARY_MEDIA_MIGRATION.read_text(encoding="utf-8"))

        psql(f"""
insert into auth.users(id) values('{OWNER}'),('{OTHER}');
insert into public.cinema_titles(id,owner_id,title,status,moderation_status,rights_status)
 values('{TITLE}','{OWNER}','CI Cinema Title','published','approved','cleared');
insert into public.cinema_episodes(id,title_id,owner_id,episode_number,title)
 values('{EPISODE}','{TITLE}','{OWNER}',1,'Episode 1');
insert into public.profiles(id) values('{OWNER}');
insert into public.content_items(id,owner_id,status) values('{DELETE_CONTENT}','{OWNER}','draft');
insert into public.playback_entitlements(id,owner_user_id,status)
 values('{ENTITLEMENT}','{OWNER}','active');
insert into public.content_media(
 id,content_id,owner_id,bucket_id,storage_path,filename,media_type,size_bytes,sha256,status,scan_status,
 processed_at,processing_version,derivatives
) values(
 '{VIDEO_MEDIA}','aaaaaaaa-0000-4000-8000-000000000001','{OWNER}','content-media','ci/video/master.mp4',
 'master.mp4','video/mp4',1024,repeat('b',64),'ready','clean',now(),1,'[{{"kind":"hls_manifest"}}]'::jsonb
);
insert into public.cinema_assets(title_id,owner_id,media_id,asset_role,display_name,created_by)
 values('{TITLE}','{OWNER}','{VIDEO_MEDIA}','trailer','CI Trailer','{OWNER}');
insert into public.cinema_playback_sessions(
 id,owner_user_id,title_id,episode_id,media_id,entitlement_id,access_policy_version,
 session_token_hash,status,duration_seconds,last_position_seconds,max_position_seconds,
 idempotency_key,expires_at
) values(
 '{SESSION}','{OWNER}','{TITLE}','{EPISODE}','{VIDEO_MEDIA}','{ENTITLEMENT}','ci-policy-v1',
 '{TOKEN_HASH}','active',600,0,0,'ci-session-idempotency',now()+interval '1 hour'
);
insert into public.cinema_watchlist_items(owner_user_id,title_id) values('{OWNER}','{TITLE}');
""")

        psql(f"""
set role service_role;
do $do$
declare v_result jsonb;
begin
 v_result:=public.cinema_record_playback_heartbeat('{SESSION}','{OWNER}','{TOKEN_HASH}','{HEARTBEAT_EVENT}',120);
 if v_result->>'duplicate'<>'false' or (v_result->>'last_position_seconds')::integer<>120 then
  raise exception 'first playback heartbeat did not advance progress';
 end if;
 v_result:=public.cinema_record_playback_heartbeat('{SESSION}','{OWNER}','{TOKEN_HASH}','{HEARTBEAT_EVENT}',120);
 if v_result->>'duplicate'<>'true' then raise exception 'heartbeat retry was not idempotent'; end if;
 v_result:=public.cinema_finish_playback_session('{SESSION}','{OWNER}','{TOKEN_HASH}','{FINISH_EVENT}',300);
 if v_result->>'status'<>'completed' or v_result->>'duplicate'<>'false' then
  raise exception 'playback finish did not complete session';
 end if;
 v_result:=public.cinema_finish_playback_session('{SESSION}','{OWNER}','{TOKEN_HASH}','{FINISH_EVENT}',300);
 if v_result->>'duplicate'<>'true' then raise exception 'finish retry was not idempotent'; end if;
end
$do$;
reset role;
do $do$
begin
 if not exists(select 1 from public.cinema_playback_sessions where id='{SESSION}' and status='completed'
  and last_position_seconds=300 and max_position_seconds=300) then
  raise exception 'playback session progress was not persisted';
 end if;
 if (select count(*) from public.cinema_playback_session_events where session_id='{SESSION}')<>2 then
  raise exception 'playback event receipts are not idempotent';
 end if;
 if not exists(select 1 from public.cinema_watchlist_items where owner_user_id='{OWNER}' and title_id='{TITLE}') then
  raise exception 'watchlist item was not persisted';
 end if;
 if not exists(select 1 from public.cinema_assets where title_id='{TITLE}' and media_id='{VIDEO_MEDIA}' and asset_role='trailer') then
  raise exception 'Creator Asset Library did not persist the title media link';
 end if;
 if not exists(select 1 from public.cinema_titles where id='{TITLE}' and production_document->>'schema_version'='1') then
  raise exception 'Creator production document default is missing';
 end if;
 if not (select relrowsecurity from pg_class where oid='public.cinema_playback_sessions'::regclass)
  or not (select relrowsecurity from pg_class where oid='public.cinema_watchlist_items'::regclass)
  or not (select relrowsecurity from pg_class where oid='public.cinema_assets'::regclass) then
  raise exception 'Cinema private tables must have RLS enabled';
 end if;
 if has_table_privilege('anon','public.cinema_playback_sessions','select')
  or has_table_privilege('authenticated','public.cinema_watchlist_items','select')
  or has_table_privilege('anon','public.cinema_assets','insert') then
  raise exception 'Cinema private tables must not grant direct client access';
 end if;
 if has_function_privilege('authenticated','public.cinema_record_playback_heartbeat(uuid,uuid,text,uuid,integer)','execute')
  or has_function_privilege('anon','public.complete_content_subtitle_job(uuid,uuid,uuid,jsonb,integer)','execute') then
  raise exception 'Cinema lifecycle RPCs must be service-role only';
 end if;
end
$do$;
""")

        unauthorized = psql(f"""
set role service_role;
select public.cinema_record_playback_heartbeat('{SESSION}','{OTHER}','{TOKEN_HASH}','cccccccc-cccc-4ccc-8ccc-cccccccccccc',121);
""", check=False)
        if unauthorized.returncode == 0 or "playback session not found" not in unauthorized.stderr:
            raise RuntimeError("cross-owner playback heartbeat was not rejected")

        conflict = psql(f"""
set role service_role;
select public.cinema_record_playback_heartbeat('{SESSION}','{OWNER}','{TOKEN_HASH}','{HEARTBEAT_EVENT}',121);
""", check=False)
        if conflict.returncode == 0 or "playback event idempotency conflict" not in conflict.stderr:
            raise RuntimeError("conflicting playback event replay was not rejected")

        duplicate_watchlist = psql(f"""
insert into public.cinema_watchlist_items(owner_user_id,title_id) values('{OWNER}','{TITLE}');
""", check=False)
        if duplicate_watchlist.returncode == 0 or "cinema_watchlist_owner_title_uq" not in duplicate_watchlist.stderr:
            raise RuntimeError("duplicate owner watchlist entry was not rejected")

        psql(f"""
create trigger content_media_enqueue_lifecycle_job
after insert or update of status on public.content_media
for each row execute function public.enqueue_content_media_processing();
""")
        psql(f"""
set role service_role;
do $do$
declare v_result jsonb; v_media_id uuid:='{CLOUDINARY_IMAGE_MEDIA}'; v_public_id text:='allpha/{CLOUDINARY_IMAGE_MEDIA}';
begin
 v_result:=public.reserve_cloudinary_media_upload(
  v_media_id,null,'{OWNER}','profile','avatar','{OWNER}',null,null,'avatar.jpg','image/jpeg',
  1024,'{CLOUDINARY_IMAGE_SHA}',v_public_id,'image','authenticated',now()+interval '5 minutes',
  'ci-cloudinary-image:{CLOUDINARY_IMAGE_MEDIA}'
 );
 if v_result->>'idempotent_replay'<>'false' then raise exception 'first Cloudinary reserve unexpectedly replayed'; end if;
 v_result:=public.reserve_cloudinary_media_upload(
  v_media_id,null,'{OWNER}','profile','avatar','{OWNER}',null,null,'avatar.jpg','image/jpeg',
  1024,'{CLOUDINARY_IMAGE_SHA}',v_public_id,'image','authenticated',now()+interval '5 minutes',
  'ci-cloudinary-image:{CLOUDINARY_IMAGE_MEDIA}'
 );
 if v_result->>'idempotent_replay'<>'true' then raise exception 'Cloudinary upload intent retry was not idempotent'; end if;
 v_result:=public.complete_cloudinary_content_media_upload(
  v_media_id,'{OWNER}','ci-cloudinary-asset-image',v_public_id,'image','authenticated','ci-batch-image',
  1,'jpg',32,32,null,1024,array['allpha'],'{{"source":"ci"}}'::jsonb
 );
 if v_result->'media'->>'status'<>'processing' then raise exception 'Cloudinary image upload did not enter provider lifecycle: %',v_result; end if;
 v_result:=public.complete_cloudinary_content_media_upload(
  v_media_id,'{OWNER}','ci-cloudinary-asset-image',v_public_id,'image','authenticated','ci-batch-image',
  1,'jpg',32,32,null,1024,array['allpha'],'{{"source":"ci"}}'::jsonb
 );
 if v_result->>'idempotent_replay'<>'true' then raise exception 'Cloudinary completion retry was not idempotent'; end if;
end
$do$;
reset role;
""")
        psql(f"""
do $do$
declare v_media_id uuid:='{CLOUDINARY_IMAGE_MEDIA}';
begin
 if not exists(select 1 from public.content_lifecycle_jobs where media_id=v_media_id and job_type='media_transcode' and status='awaiting_provider') then
  raise exception 'Cloudinary eager job was not fenced awaiting provider callback';
 end if;
 update public.content_lifecycle_jobs set status='succeeded' where media_id=v_media_id and job_type='media_transcode';
 update public.content_media set status='ready',scan_status='clean',processed_at=now(),processing_version=1,
  provider_callback_verified_at=now(),
  scan_receipt='{{"scanner_id":"ci-scanner","contract_version":"allpha.document-scan.v1","sha256":"{CLOUDINARY_IMAGE_SHA}","engine_version":"ci-engine","signature_version":"ci-signatures"}}'::jsonb,
  derivatives='[{{"kind":"display","provider":"cloudinary"}},{{"kind":"thumbnail","provider":"cloudinary"}}]'::jsonb
 where id=v_media_id;
 if exists(select 1 from public.content_lifecycle_jobs where media_id=v_media_id and job_type='provider_cleanup') then
  raise exception 'canonical Cloudinary asset was incorrectly queued for cleanup';
 end if;
end
$do$;
""")

        psql(f"""
set role service_role;
do $do$
declare v_result jsonb; v_media_id uuid:='{CLOUDINARY_SUBTITLE_MEDIA}'; v_public_id text:='allpha/{CLOUDINARY_SUBTITLE_MEDIA}';
begin
 v_result:=public.reserve_cloudinary_media_upload(
  v_media_id,null,'{OWNER}','cinema','cinema_asset','{EPISODE}',null,null,'captions.vtt','text/vtt',
  128,'{CLOUDINARY_SUBTITLE_SHA}',v_public_id,'raw','authenticated',now()+interval '5 minutes',
  'ci-cloudinary-subtitle:{CLOUDINARY_SUBTITLE_MEDIA}'
 );
 v_result:=public.complete_cloudinary_content_media_upload(
  v_media_id,'{OWNER}','ci-cloudinary-asset-subtitle',v_public_id,'raw','authenticated',null,
  1,'vtt',null,null,null,128,array['allpha'],'{{"source":"ci"}}'::jsonb
 );
 if v_result->'media'->>'status'<>'processing' then raise exception 'Cloudinary subtitle did not enter validation lifecycle: %',v_result; end if;
end
$do$;
reset role;
""")
        psql(f"""
do $do$
begin
 if not exists(select 1 from public.content_lifecycle_jobs where media_id='{CLOUDINARY_SUBTITLE_MEDIA}' and job_type='subtitle_validate' and status='pending') then
  raise exception 'Cloudinary subtitle validation job was not queued';
 end if;
end
$do$;
""")

        psql(f"""
set role service_role;
do $do$
declare v_result jsonb; v_media_id uuid:='{CLOUDINARY_DELETE_MEDIA}'; v_public_id text:='allpha/{CLOUDINARY_DELETE_MEDIA}';
begin
 v_result:=public.reserve_cloudinary_media_upload(
  v_media_id,'{DELETE_CONTENT}','{OWNER}','content','attachment',null,null,null,'delete.jpg','image/jpeg',512,
  '{CLOUDINARY_DELETE_SHA}',v_public_id,'image','authenticated',now()+interval '5 minutes',
  'ci-cloudinary-delete:{CLOUDINARY_DELETE_MEDIA}'
 );
 if v_result->>'idempotent_replay'<>'false' then raise exception 'delete fixture reserve unexpectedly replayed'; end if;
 v_result:=public.request_cloudinary_content_media_delete(v_media_id,'{OWNER}');
 if v_result->>'outcome'<>'media_state_invalid' then raise exception 'incomplete upload intent must not be deleted: %',v_result; end if;
 v_result:=public.complete_cloudinary_content_media_upload(
  v_media_id,'{OWNER}','ci-cloudinary-asset-delete',v_public_id,'image','authenticated','ci-batch-delete',
  1,'jpg',32,32,null,512,array['allpha'],'{{"source":"ci"}}'::jsonb
 );
 if v_result->'media'->>'status'<>'processing' then raise exception 'delete fixture upload did not enter provider lifecycle: %',v_result; end if;
end
$do$;
reset role;
-- Disposable PostgreSQL fixture setup only: emulate the already-scanned ready state.
update public.content_lifecycle_jobs
set status='succeeded',completed_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
where media_id='{CLOUDINARY_DELETE_MEDIA}'::uuid
  and job_type='media_transcode' and status in ('pending','awaiting_provider','retry_wait');
update public.content_media
set status='ready',scan_status='clean',processed_at=now(),processing_version=1,
 provider_callback_verified_at=now(),
 scan_receipt='{{"scanner_id":"ci-scanner","contract_version":"allpha.document-scan.v1","sha256":"{CLOUDINARY_DELETE_SHA}","engine_version":"ci-engine","signature_version":"ci-signatures"}}'::jsonb,
 derivatives='[{{"kind":"display","provider":"cloudinary"}},{{"kind":"thumbnail","provider":"cloudinary"}}]'::jsonb
where id='{CLOUDINARY_DELETE_MEDIA}'::uuid;
set role service_role;
do $do$
declare v_result jsonb;
begin
 v_result:=public.request_cloudinary_content_media_delete('{CLOUDINARY_DELETE_MEDIA}','{OWNER}');
 if v_result->>'outcome'<>'queued' then raise exception 'Cloudinary media deletion was not queued: %',v_result; end if;
 v_result:=public.request_cloudinary_content_media_delete('{CLOUDINARY_DELETE_MEDIA}','{OWNER}');
 if v_result->>'outcome'<>'already_queued' then raise exception 'Cloudinary media deletion request was not idempotent: %',v_result; end if;
end
$do$;
do $do$
declare v_job public.content_lifecycle_jobs%rowtype; v_result text;
begin
 select * into v_job from public.claim_content_lifecycle_jobs('ci-delete-worker',10,60,'provider_cleanup')
 where media_id='{CLOUDINARY_DELETE_MEDIA}'::uuid;
 if not found then raise exception 'Cloudinary media deletion job was not claimed'; end if;
 v_result:=public.complete_cloudinary_media_delete_job(v_job.id,v_job.lease_token,'{CLOUDINARY_DELETE_MEDIA}');
 if v_result<>'succeeded' then raise exception 'Cloudinary media deletion job did not complete: %',v_result; end if;
end
$do$;
reset role;
do $do$
begin
 if not exists(select 1 from public.content_media where id='{CLOUDINARY_DELETE_MEDIA}'
  and status='deleted' and provider_delete_state='deleted' and provider_deleted_at is not null) then
  raise exception 'Cloudinary media deletion did not persist its terminal tombstone';
 end if;
 if not exists(select 1 from public.content_lifecycle_jobs where media_id='{CLOUDINARY_DELETE_MEDIA}'
  and job_type='provider_cleanup' and status='succeeded') then
  raise exception 'Cloudinary media deletion job was not completed';
 end if;
end
$do$;
""")

        unauthorized_profile = psql(f"""
set role service_role;
select public.reserve_cloudinary_media_upload(
 '{UNAUTHORIZED_PROFILE_MEDIA}',null,'{OWNER}','profile','avatar','{OTHER}',null,null,'avatar.jpg','image/jpeg',
 512,'{'a' * 64}','allpha/{UNAUTHORIZED_PROFILE_MEDIA}','image','authenticated',now()+interval '5 minutes',
 'ci-cloudinary-unauthorized:{UNAUTHORIZED_PROFILE_MEDIA}'
);
""", check=False)
        if unauthorized_profile.returncode == 0 or "MEDIA_RESOURCE_ACCESS_DENIED" not in unauthorized_profile.stderr:
            raise RuntimeError("cross-owner profile media reservation was not rejected")

        psql("""
do $do$
declare v jsonb;
begin
 v:=public.cloudinary_media_schema_readiness();
 if v->>'contract_version'<>'1' or not (v ? 'ready') then
  raise exception 'Cloudinary media schema readiness contract is malformed: %',v;
 end if;
end
$do$;
""")
        psql(f"""
insert into public.content_media(
 id,content_id,owner_id,bucket_id,storage_path,filename,media_type,size_bytes,sha256,status,scan_status
) values(
 '{LEGACY_DELETE_MEDIA}','{DELETE_CONTENT}','{OWNER}','content-media','ci/legacy/delete.jpg',
 'legacy-delete.jpg','image/jpeg',512,repeat('d',64),'uploaded','clean'
);
set role service_role;
do $do$
declare v_result jsonb; v_job public.content_lifecycle_jobs%rowtype; v_done text;
begin
 v_result:=public.request_cloudinary_content_media_delete('{LEGACY_DELETE_MEDIA}','{OWNER}');
 if v_result->>'outcome'<>'queued' then raise exception 'Legacy Supabase media deletion was not queued: %',v_result; end if;
 select * into v_job from public.claim_content_lifecycle_jobs('ci-legacy-delete-worker',10,60,'provider_cleanup')
 where media_id='{LEGACY_DELETE_MEDIA}'::uuid;
 if not found then raise exception 'Legacy Supabase media deletion job was not claimed'; end if;
 v_done:=public.complete_legacy_content_media_delete_job(v_job.id,v_job.lease_token,'{LEGACY_DELETE_MEDIA}');
 if v_done<>'succeeded' then raise exception 'Legacy Supabase media deletion did not complete: %',v_done; end if;
end
$do$;
reset role;
do $do$
begin
 if not exists(select 1 from public.content_media where id='{LEGACY_DELETE_MEDIA}'
  and storage_provider='supabase' and status='deleted'
  and provider_delete_state='deleted' and provider_deleted_at is not null) then
  raise exception 'Legacy Supabase media deletion did not persist its terminal tombstone';
 end if;
end
$do$;
""")
        psql(f"""
insert into public.content_media(
 id,content_id,owner_id,bucket_id,storage_path,filename,media_type,size_bytes,sha256,status,scan_status
) values(
 '{SUBTITLE_MEDIA}','bbbbbbbb-0000-4000-8000-000000000002','{OWNER}','content-media','ci/subtitles/id.vtt',
 'id.vtt','text/vtt',128,encode(extensions.digest(convert_to('WEBVTT' || chr(10) || chr(10) || '00:00:00.000 --> 00:00:02.000' || chr(10) || 'Hello' || chr(10),'UTF8'),'sha256'),'hex'),
 'uploaded','pending'
);
insert into public.content_media(
 id,content_id,owner_id,bucket_id,storage_path,filename,media_type,size_bytes,sha256,status,scan_status
) values(
 '{INVALID_SUBTITLE_MEDIA}','cccccccc-0000-4000-8000-000000000003','{OWNER}','content-media','ci/subtitles/bad.vtt',
 'bad.vtt','text/vtt',32,repeat('c',64),'uploaded','pending'
);
""")
        psql(f"""
set role service_role;
do $do$
declare v_job public.content_lifecycle_jobs%rowtype; v_receipt jsonb; v_result jsonb; v_sha text;
 v_valid_found boolean:=false; v_invalid_found boolean:=false;
begin
 for v_job in select * from public.claim_content_lifecycle_jobs('ci-subtitle-worker',10,60,'subtitle_validate')
 loop
  if v_job.media_id='{SUBTITLE_MEDIA}'::uuid then
   v_sha := '{SUBTITLE_SHA}';
   v_receipt:=jsonb_build_object(
    'scanner_id','clamav-local','contract_version','allpha.local-clamav.v1',
    'sha256',v_sha,'engine_version','ci-clamav-engine','signature_version','ci-signature-set',
    'validation',jsonb_build_object('sha256',v_sha,'format','webvtt','cue_count','1')
   );
   v_result:=public.complete_content_subtitle_job(v_job.id,v_job.lease_token,'{SUBTITLE_MEDIA}',v_receipt,1);
   if v_result->>'outcome'<>'completed' then raise exception 'subtitle job did not complete: %',v_result; end if;
   v_valid_found:=true;
  elsif v_job.media_id='{INVALID_SUBTITLE_MEDIA}'::uuid then
   v_sha := repeat('c',64);
   v_receipt:=jsonb_build_object(
    'scanner_id','untrusted-scanner','contract_version','allpha.local-clamav.v1',
    'sha256',v_sha,'engine_version','ci-clamav-engine','signature_version','ci-signature-set',
    'validation',jsonb_build_object('sha256',v_sha,'format','webvtt','cue_count','1')
   );
   v_result:=public.complete_content_subtitle_job(v_job.id,v_job.lease_token,'{INVALID_SUBTITLE_MEDIA}',v_receipt,1);
   if v_result->>'outcome'<>'scan_receipt_invalid' then raise exception 'invalid scanner receipt was not rejected'; end if;
   v_invalid_found:=true;
  elsif v_job.media_id='{CLOUDINARY_SUBTITLE_MEDIA}'::uuid then
   v_sha := '{CLOUDINARY_SUBTITLE_SHA}';
   v_receipt:=jsonb_build_object(
    'scanner_id','ci-remote-document-scan','contract_version','allpha.document-scan.v1',
    'sha256',v_sha,'engine_version','remote-engine-v1','signature_version','remote-signatures-v1',
    'validation',jsonb_build_object('sha256',v_sha,'format','webvtt','cue_count','1')
   );
   v_result:=public.complete_content_subtitle_job(v_job.id,v_job.lease_token,'{CLOUDINARY_SUBTITLE_MEDIA}',v_receipt,1);
   if v_result->>'outcome'<>'completed' then raise exception 'remote scanner receipt did not complete Cloudinary subtitle: %',v_result; end if;
  end if;
 end loop;
 if not v_valid_found or not v_invalid_found then raise exception 'subtitle jobs were not both claimed and verified'; end if;
end
$do$;
reset role;
do $do$
begin
 if not exists(select 1 from public.content_media where id='{SUBTITLE_MEDIA}' and status='ready'
  and scan_status='clean' and processed_at is not null and media_type='text/vtt') then
  raise exception 'validated subtitle media was not marked ready';
 end if;
 if not exists(select 1 from public.content_lifecycle_jobs where media_id='{SUBTITLE_MEDIA}' and job_type='subtitle_validate' and status='succeeded') then
  raise exception 'subtitle lifecycle job was not completed';
 end if;
 if not exists(select 1 from public.content_lifecycle_jobs where media_id='{INVALID_SUBTITLE_MEDIA}' and job_type='subtitle_validate' and status='processing') then
  raise exception 'invalid scanner receipt must not complete subtitle job';
 end if;
 if not exists(select 1 from public.content_media where id='{CLOUDINARY_SUBTITLE_MEDIA}' and status='ready'
  and storage_provider='cloudinary' and scan_receipt->>'contract_version'='allpha.document-scan.v1') then
  raise exception 'Cloudinary subtitle did not persist remote scanner provenance';
 end if;
 if not exists(select 1 from public.content_lifecycle_jobs where media_id='{CLOUDINARY_SUBTITLE_MEDIA}' and job_type='subtitle_validate' and status='succeeded') then
  raise exception 'Cloudinary subtitle lifecycle did not complete';
 end if;
 if has_function_privilege('authenticated','public.reserve_cloudinary_media_upload(uuid,uuid,uuid,text,text,uuid,uuid,uuid,text,text,bigint,text,text,text,text,timestamptz,text)','execute')
  or has_function_privilege('anon','public.complete_cloudinary_content_media_upload(uuid,uuid,text,text,text,text,text,bigint,text,integer,integer,numeric,bigint,text[],jsonb)','execute') then
  raise exception 'Cloudinary upload RPC privileges are not restricted';
 end if;
 if not exists(select 1 from storage.buckets where id='content-media' and allowed_mime_types @> array['text/vtt','application/x-subrip']) then
  raise exception 'subtitle MIME types were not enabled in the private media bucket';
 end if;
end
$do$;
""")
        print("PASS: ENG-P13 PostgreSQL 17 Creator Asset Library, Cloudinary canonical media registry, domain ownership, idempotent upload/deletion lifecycle, provider-pending jobs, no premature asset cleanup, remote/local subtitle scanner receipts, owner-scoped playback and service-role-only RPCs.")
    finally:
        run(["docker", "rm", "-f", NAME], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: ENG-P13 Cinema lifecycle verification: {exc}", file=sys.stderr)
        raise
