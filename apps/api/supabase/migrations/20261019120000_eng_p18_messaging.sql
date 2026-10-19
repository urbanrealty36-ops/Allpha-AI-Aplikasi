-- ENG-P18 canonical human/Agent messaging, membership, delivery and Realtime.
create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('human','agent')),
  title text check (title is null or length(title) <= 120),
  created_by uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_message_at timestamptz
);
create table if not exists public.conversation_participants (
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  agent_id uuid references public.ai_agents(id) on delete cascade,
  participant_type text not null check (participant_type in ('human','agent')),
  joined_at timestamptz not null default now(),
  last_read_at timestamptz,
  constraint conversation_participant_identity check (
    (participant_type='human' and user_id is not null and agent_id is null) or
    (participant_type='agent' and agent_id is not null and user_id is null)
  ),
  constraint conversation_participants_unique_user unique (conversation_id,user_id),
  constraint conversation_participants_unique_agent unique (conversation_id,agent_id)
);
create index if not exists conversation_participants_user_joined_idx on public.conversation_participants(user_id,joined_at desc) where user_id is not null;
create index if not exists conversation_participants_agent_idx on public.conversation_participants(agent_id) where agent_id is not null;
create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  sender_type text not null check (sender_type in ('human','agent')),
  sender_user_id uuid references auth.users(id) on delete cascade,
  sender_agent_id uuid references public.ai_agents(id) on delete cascade,
  body text not null check (length(trim(body)) between 1 and 10000),
  client_message_id uuid not null,
  delivery_status text not null default 'sent' check (delivery_status in ('sent','delivered','read')),
  created_at timestamptz not null default now(),
  delivered_at timestamptz,
  read_at timestamptz,
  constraint message_sender_identity check (
    (sender_type='human' and sender_user_id is not null and sender_agent_id is null) or
    (sender_type='agent' and sender_agent_id is not null and sender_user_id is null)
  ),
  constraint messages_idempotent_client_id unique (conversation_id,sender_user_id,client_message_id)
);
create index if not exists messages_conversation_created_idx on public.messages(conversation_id,created_at desc);
create index if not exists messages_delivery_idx on public.messages(conversation_id,delivery_status,created_at desc);
alter table public.conversations enable row level security;
alter table public.conversation_participants enable row level security;
alter table public.messages enable row level security;
-- Business writes are server-owned through the authenticated FastAPI layer.
revoke all on public.conversations, public.conversation_participants, public.messages from anon, authenticated;
grant select,insert,update,delete on public.conversations, public.conversation_participants, public.messages to service_role;
do $$ begin
  alter publication supabase_realtime add table public.conversations;
exception when duplicate_object then null; end $$;
do $$ begin
  alter publication supabase_realtime add table public.conversation_participants;
exception when duplicate_object then null; end $$;
do $$ begin
  alter publication supabase_realtime add table public.messages;
exception when duplicate_object then null; end $$;
