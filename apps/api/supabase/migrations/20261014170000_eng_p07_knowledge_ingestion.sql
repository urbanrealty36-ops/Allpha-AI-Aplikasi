-- ENG-P07 knowledge ingestion; source-only until approved isolated staging validation.
create table if not exists public.agent_knowledge_sources (
 id uuid primary key default gen_random_uuid(),
 agent_id uuid not null references public.ai_agents(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade,
 filename text not null check(length(filename) between 1 and 255),
 media_type text not null,
 size_bytes bigint not null check(size_bytes between 1 and 15728640),
 sha256 text not null check(sha256 ~ '^[0-9a-f]{64}$'),
 storage_path text not null unique,
 source_version integer not null default 1 check(source_version > 0),
 status text not null default 'quarantined' check(status in ('quarantined','processing','failed','indexed_pending_embeddings','ready','deleting')),
 processing_stage text not null default 'awaiting_malware_scan',
 error_code text,
 provenance jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists agent_knowledge_sources_owner_agent_created_idx on public.agent_knowledge_sources(owner_id,agent_id,created_at desc);
create table if not exists public.agent_knowledge_jobs (
 id uuid primary key default gen_random_uuid(),
 source_id uuid not null references public.agent_knowledge_sources(id) on delete cascade,
 agent_id uuid not null references public.ai_agents(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade,
 status text not null default 'queued' check(status in ('queued','processing','succeeded','failed','cancelled')),
 stage text not null,
 attempt integer not null default 0 check(attempt >= 0),
 progress integer not null default 0 check(progress between 0 and 100),
 error_code text,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists agent_knowledge_jobs_owner_source_created_idx on public.agent_knowledge_jobs(owner_id,source_id,created_at desc);
create table if not exists public.agent_knowledge_chunks (
 id uuid primary key default gen_random_uuid(),
 source_id uuid not null references public.agent_knowledge_sources(id) on delete cascade,
 agent_id uuid not null references public.ai_agents(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade,
 chunk_index integer not null check(chunk_index >= 0),
 content text not null check(length(content) between 1 and 1800),
 source_location jsonb not null,
 source_version integer not null check(source_version > 0),
 content_sha256 text not null check(content_sha256 ~ '^[0-9a-f]{64}$'),
 created_at timestamptz not null default now(),
 unique(source_id,source_version,chunk_index)
);
create index if not exists agent_knowledge_chunks_owner_source_idx on public.agent_knowledge_chunks(owner_id,source_id,chunk_index);
alter table public.agent_knowledge_sources enable row level security;
alter table public.agent_knowledge_jobs enable row level security;
alter table public.agent_knowledge_chunks enable row level security;
drop policy if exists agent_knowledge_sources_owner_select on public.agent_knowledge_sources;
create policy agent_knowledge_sources_owner_select on public.agent_knowledge_sources for select to authenticated using(owner_id=(select auth.uid()));
drop policy if exists agent_knowledge_sources_owner_insert on public.agent_knowledge_sources;
create policy agent_knowledge_sources_owner_insert on public.agent_knowledge_sources for insert to authenticated with check(owner_id=(select auth.uid()) and exists(select 1 from public.agent_ownerships o where o.agent_id=agent_knowledge_sources.agent_id and o.owner_user_id=(select auth.uid()) and o.status='active'));
drop policy if exists agent_knowledge_sources_owner_update on public.agent_knowledge_sources;
create policy agent_knowledge_sources_owner_update on public.agent_knowledge_sources for update to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
drop policy if exists agent_knowledge_sources_owner_delete on public.agent_knowledge_sources;
create policy agent_knowledge_sources_owner_delete on public.agent_knowledge_sources for delete to authenticated using(owner_id=(select auth.uid()));
drop policy if exists agent_knowledge_jobs_owner_select on public.agent_knowledge_jobs;
create policy agent_knowledge_jobs_owner_select on public.agent_knowledge_jobs for select to authenticated using(owner_id=(select auth.uid()));
drop policy if exists agent_knowledge_jobs_owner_insert on public.agent_knowledge_jobs;
create policy agent_knowledge_jobs_owner_insert on public.agent_knowledge_jobs for insert to authenticated with check(owner_id=(select auth.uid()));
drop policy if exists agent_knowledge_jobs_owner_update on public.agent_knowledge_jobs;
create policy agent_knowledge_jobs_owner_update on public.agent_knowledge_jobs for update to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
drop policy if exists agent_knowledge_chunks_owner_select on public.agent_knowledge_chunks;
create policy agent_knowledge_chunks_owner_select on public.agent_knowledge_chunks for select to authenticated using(owner_id=(select auth.uid()));
drop policy if exists agent_knowledge_chunks_owner_insert on public.agent_knowledge_chunks;
create policy agent_knowledge_chunks_owner_insert on public.agent_knowledge_chunks for insert to authenticated with check(owner_id=(select auth.uid()));
drop policy if exists agent_knowledge_chunks_owner_delete on public.agent_knowledge_chunks;
create policy agent_knowledge_chunks_owner_delete on public.agent_knowledge_chunks for delete to authenticated using(owner_id=(select auth.uid()));
revoke all on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks from anon,public;
grant select on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks to authenticated;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('agent-knowledge','agent-knowledge',false,15728640,array['application/pdf','text/markdown','text/plain','application/vnd.openxmlformats-officedocument.wordprocessingml.document'])
on conflict(id) do update set public=false,file_size_limit=15728640,allowed_mime_types=excluded.allowed_mime_types;
drop policy if exists agent_knowledge_storage_owner_select on storage.objects;
create policy agent_knowledge_storage_owner_select on storage.objects for select to authenticated using(bucket_id='agent-knowledge' and (storage.foldername(name))[1]=(select auth.uid())::text and exists(select 1 from public.agent_knowledge_sources s where s.owner_id=(select auth.uid()) and s.storage_path=storage.objects.name));
drop policy if exists agent_knowledge_storage_owner_insert on storage.objects;
create policy agent_knowledge_storage_owner_insert on storage.objects for insert to authenticated with check(bucket_id='agent-knowledge' and (storage.foldername(name))[1]=(select auth.uid())::text and exists(select 1 from public.agent_knowledge_sources s where s.owner_id=(select auth.uid()) and s.storage_path=storage.objects.name and s.status='quarantined'));
drop policy if exists agent_knowledge_storage_owner_delete on storage.objects;
create policy agent_knowledge_storage_owner_delete on storage.objects for delete to authenticated using(bucket_id='agent-knowledge' and (storage.foldername(name))[1]=(select auth.uid())::text and exists(select 1 from public.agent_knowledge_sources s where s.owner_id=(select auth.uid()) and s.storage_path=storage.objects.name));
