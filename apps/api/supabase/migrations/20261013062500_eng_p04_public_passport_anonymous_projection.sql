-- ENG-P04 acceptance fix: allow anonymous reads of the strictly limited public Agent Passport projection.
-- Public table reads are column-limited and row-limited by RLS; private persona/boundaries remain inaccessible to anon.
drop policy if exists ai_agents_select_public_anon on public.ai_agents;
create policy ai_agents_select_public_anon on public.ai_agents
for select to anon
using (visibility = 'public' and status = 'active');

revoke all on public.ai_agents from anon;
grant select (id, handle, display_name, description, avatar_url, disclosure, visibility, status, created_at)
on public.ai_agents to anon;
