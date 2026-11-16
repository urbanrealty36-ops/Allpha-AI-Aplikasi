-- WP-07: one explicit Memory proposal per owner Agent generation job.
-- Source-only migration: do not apply to the connected production database in this work session.
begin;

create unique index if not exists agent_memory_generation_job_source_uidx
  on public.agent_memory_items (
    owner_user_id,
    agent_id,
    (source_ref->>'generation_job_id')
  )
  where source_ref->>'kind' = 'agent_generation_job'
    and source_ref ? 'generation_job_id';

comment on index public.agent_memory_generation_job_source_uidx is
  'Idempotency guard for explicit owner Memory proposals originating from one generation job.';

commit;
