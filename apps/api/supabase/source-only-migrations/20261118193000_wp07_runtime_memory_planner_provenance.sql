-- WP-07: retain non-content Memory provenance on durable planner reservations.
-- Depends on 20261116200000_wp07_durable_model_tool_plans.sql and the source-only
-- Memory Coordinator lifecycle/search migrations. Does not duplicate Memory tables/RPCs.
begin;

alter table public.agent_runtime_tool_plans
  add column if not exists memory_context_refs jsonb not null default '[]'::jsonb,
  add column if not exists memory_context_sha256 text not null
    default '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945';

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname='agent_runtime_tool_plans_memory_refs_object_check'
      and conrelid='public.agent_runtime_tool_plans'::regclass
  ) then
    alter table public.agent_runtime_tool_plans
      add constraint agent_runtime_tool_plans_memory_refs_object_check
      check (jsonb_typeof(memory_context_refs)='array');
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='agent_runtime_tool_plans_memory_digest_check'
      and conrelid='public.agent_runtime_tool_plans'::regclass
  ) then
    alter table public.agent_runtime_tool_plans
      add constraint agent_runtime_tool_plans_memory_digest_check
      check (memory_context_sha256 ~ '^[0-9a-f]{64}$');
  end if;
end
$$;

comment on column public.agent_runtime_tool_plans.memory_context_refs is
  'Non-content provenance references for owner-consented Memory items used by the planner.';
comment on column public.agent_runtime_tool_plans.memory_context_sha256 is
  'Digest of the exact bounded Memory prompt context; raw Memory text is not copied into planner provenance.';

commit;
