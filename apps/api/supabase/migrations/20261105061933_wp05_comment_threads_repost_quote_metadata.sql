-- WP-05 social interaction completion: threaded replies, quote/repost metadata,
-- and private per-user notification broadcasts. The FastAPI API remains the only
-- business-write boundary; this migration does not grant clients table access.

begin;

-- Threaded comments are scoped to the same parent content. Composite FK prevents
-- cross-content parent references even if a caller bypasses API validation.
alter table public.content_comments
  add column if not exists parent_comment_id uuid;

create unique index if not exists content_comments_id_content_id_uidx
  on public.content_comments (id, content_id);

alter table public.content_comments
  drop constraint if exists content_comments_parent_same_content_fkey;
alter table public.content_comments
  add constraint content_comments_parent_same_content_fkey
  foreign key (parent_comment_id, content_id)
  references public.content_comments (id, content_id)
  on delete cascade;

alter table public.content_comments
  drop constraint if exists content_comments_parent_not_self_check;
alter table public.content_comments
  add constraint content_comments_parent_not_self_check
  check (parent_comment_id is null or parent_comment_id <> id);

create index if not exists content_comments_parent_created_idx
  on public.content_comments (content_id, parent_comment_id, created_at asc)
  where status = 'visible';

-- A repost is an attributed share activity; a quote is the same activity plus
-- the republisher's own text. The original content remains the canonical source.
alter table public.content_shares
  add column if not exists quote_body text;

alter table public.content_shares
  drop constraint if exists content_shares_share_target_check;
alter table public.content_shares
  add constraint content_shares_share_target_check
  check (share_target = any (array[
    'copy_link'::text, 'native_share'::text, 'external'::text,
    'repost'::text, 'quote'::text
  ]));

alter table public.content_shares
  drop constraint if exists content_shares_quote_body_check;
alter table public.content_shares
  add constraint content_shares_quote_body_check
  check (
    (share_target = 'quote' and quote_body is not null
      and char_length(btrim(quote_body)) between 1 and 2000)
    or
    (share_target <> 'quote' and quote_body is null)
  );

create index if not exists content_shares_reposts_content_created_idx
  on public.content_shares (content_id, created_at desc)
  where share_target in ('repost', 'quote');

-- Realtime delivery is exposed through the authenticated FastAPI notification
-- update stream. The managed realtime.messages table is not modified because
-- the project migration role is not its owner; client roles retain no direct
-- SELECT access to the notifications table.

comment on column public.content_comments.parent_comment_id is
  'Optional parent comment; composite FK enforces same content thread.';
comment on column public.content_shares.quote_body is
  'Republisher-authored text for quote shares; original content remains content_id.';

commit;

-- Rollback guidance (manual, only after product data has been reconciled):
-- 1. Preserve/export rows whose share_target is repost/quote and quote_body values.
-- 2. Re-add the original share_target check for copy_link/native_share/external.
-- 3. Drop the repost index, quote_body check/column, comment thread index,
--    same-content FK, self-parent check, composite unique index, and parent_comment_id.
-- This migration creates no trigger, function, or policy on managed Realtime tables.
