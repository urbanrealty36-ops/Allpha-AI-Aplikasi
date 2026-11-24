-- ENG-P06: keep the public Skill projection behind the canonical FastAPI boundary.
-- The projection is intentionally read by the server using service_role; clients
-- must not query the view directly or bypass the allow-listed response contract.
alter view public.agent_skill_publications set (security_invoker = true);

revoke all on public.agent_skill_publications from public, anon, authenticated;
grant select on public.agent_skill_publications to service_role;

comment on view public.agent_skill_publications is
  'Public Skill publication projection. Service-role only; public consumers use the canonical FastAPI endpoint.';
