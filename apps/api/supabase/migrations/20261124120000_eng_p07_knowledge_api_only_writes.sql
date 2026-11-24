-- ENG-P07: all Knowledge lifecycle mutations must pass through FastAPI and service workers.
revoke insert,update,delete on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks from public,anon,authenticated;
grant select on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks to authenticated;
grant all on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks to service_role;

drop policy if exists agent_knowledge_sources_owner_insert on public.agent_knowledge_sources;
drop policy if exists agent_knowledge_sources_owner_update on public.agent_knowledge_sources;
drop policy if exists agent_knowledge_sources_owner_delete on public.agent_knowledge_sources;
drop policy if exists agent_knowledge_jobs_owner_insert on public.agent_knowledge_jobs;
drop policy if exists agent_knowledge_jobs_owner_update on public.agent_knowledge_jobs;
drop policy if exists agent_knowledge_chunks_owner_insert on public.agent_knowledge_chunks;
drop policy if exists agent_knowledge_chunks_owner_delete on public.agent_knowledge_chunks;

-- Private originals are accessed only through FastAPI after ownership checks.
-- Direct client Storage access would bypass the upload hash and lifecycle checks.
drop policy if exists agent_knowledge_storage_owner_select on storage.objects;
drop policy if exists agent_knowledge_storage_owner_insert on storage.objects;
drop policy if exists agent_knowledge_storage_owner_delete on storage.objects;

comment on table public.agent_knowledge_sources is
  'Knowledge source lifecycle is server-owned; authenticated users may read only their own rows through RLS.';
comment on table public.agent_knowledge_jobs is
  'Knowledge jobs are service-owned; clients cannot enqueue, mutate or finalize processing state directly.';
comment on table public.agent_knowledge_chunks is
  'Knowledge chunks are service-owned; only the ingestion/indexing workers may write or delete chunks.';

notify pgrst, 'reload schema';
