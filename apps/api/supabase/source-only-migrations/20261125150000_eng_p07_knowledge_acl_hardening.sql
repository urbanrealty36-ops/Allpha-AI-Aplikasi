-- ENG-P07 forward-only ACL hardening.
-- The live catalog showed authenticated had TRUNCATE, REFERENCES and TRIGGER
-- table privileges even after lifecycle DML was removed. TRUNCATE bypasses RLS.
-- Keep owner-scoped reads through RLS; all lifecycle writes remain FastAPI/service-role only.
begin;

revoke all privileges on table
  public.agent_knowledge_sources,
  public.agent_knowledge_jobs,
  public.agent_knowledge_chunks
from anon, public, authenticated;

grant select on table
  public.agent_knowledge_sources,
  public.agent_knowledge_jobs,
  public.agent_knowledge_chunks
to authenticated;

commit;
