-- ENG-P08: Conversation Memory consent is a policy over the canonical Messaging store.
-- Messages remain in Messaging; this does not create or copy a second conversation store.
begin;

alter table public.agent_memory_policies
  drop constraint if exists agent_memory_policies_memory_type_check;
alter table public.agent_memory_policies
  add constraint agent_memory_policies_memory_type_check
  check (memory_type = any (array[
    'conversation'::text,
    'working'::text,
    'episodic'::text,
    'semantic'::text,
    'procedural'::text,
    'long_term'::text
  ]));

comment on constraint agent_memory_policies_memory_type_check on public.agent_memory_policies is
  'Conversation policy grants bounded access to the canonical Messaging store; conversation messages are not copied into agent_memory_items.';

commit;
