-- ENG-P07 full-text indexing for private knowledge chunks.
-- Existing owner-scoped RLS remains authoritative for every query.
alter table public.agent_knowledge_chunks add column if not exists search_vector tsvector generated always as (to_tsvector('simple'::regconfig, content)) stored;
create index if not exists agent_knowledge_chunks_search_vector_idx on public.agent_knowledge_chunks using gin(search_vector);
